"""Approximate visitor location (country / region / city) — no outside service is called.

Sources, in order:
1. Cloudflare visitor-location headers (when TRUST_CF_HEADERS=1 and the site is behind Cloudflare, or when a
   visitor arrives through a Cloudflare Tunnel running on this computer).
2. The free DB-IP "IP to City Lite" database in MaxMind DB format (.mmdb). The site downloads it by itself
   every month (GEOIP_AUTO=1, the default) and reads it with the bundled MaxMind reader (app/vendor).
3. Optionally a SQLite copy built from the DB-IP CSV with `flask --app wsgi import-geoip …` (older method).
   Data licence: CC BY 4.0 — "IP Geolocation by DB-IP" (https://db-ip.com), credited in the footer.

Only the derived location is stored; the raw IP address never is.
"""
import csv
import gzip
import io
import ipaddress
import os
import sqlite3
import threading
from functools import lru_cache

from flask import current_app, request

try:
    from babel import Locale
    _TERRITORIES = Locale("en").territories
except Exception:  # pragma: no cover - Babel missing
    _TERRITORIES = {}

_local = threading.local()


def country_name(code):
    if not code:
        return ""
    return _TERRITORIES.get(code.upper(), code.upper())


def flag(code):
    if not code or len(code) != 2 or not code.isalpha():
        return "🌐"
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code.upper())


def _hex(ip):
    """Fixed-width hex key so IPv4 and IPv6 sort correctly as text."""
    addr = ipaddress.ip_address(ip)
    if addr.version == 4:
        addr = ipaddress.IPv6Address("::ffff:" + str(addr))
    return format(int(addr), "032x")


def db_path():
    return current_app.config.get("GEOIP_DB", "")


def mmdb_path():
    return current_app.config.get("GEOIP_MMDB", "")


def available():
    return any(p and os.path.isfile(p) for p in (mmdb_path(), db_path()))


# ---------------------------------------------------------------- MaxMind DB (.mmdb) reader

_readers = {}
_readers_lock = threading.Lock()


def _mmdb_reader(path):
    """Shared memory-mapped reader, reopened when the file is replaced by a newer month."""
    from .vendor import maxminddb
    mtime = os.path.getmtime(path)
    with _readers_lock:
        cur = _readers.get(path)
        if cur and cur[0] == mtime:
            return cur[1]
        if cur:
            try:
                cur[1].close()
            except Exception:  # pragma: no cover
                pass
        reader = maxminddb.open_database(path, maxminddb.MODE_MMAP)
        _readers[path] = (mtime, reader)
        return reader


def _close_readers(path):
    with _readers_lock:
        cur = _readers.pop(path, None)
    if cur:
        try:
            cur[1].close()
        except Exception:  # pragma: no cover
            pass


def _names(obj):
    return ((obj or {}).get("names") or {}).get("en", "") if isinstance(obj, dict) else ""


@lru_cache(maxsize=8192)
def _lookup_mmdb(path, ip, mtime):
    try:
        rec = _mmdb_reader(path).get(ip)
    except Exception:
        return None
    if not isinstance(rec, dict):
        return None
    country = ((rec.get("country") or rec.get("registered_country") or {}).get("iso_code") or "").upper()[:2]
    subs = rec.get("subdivisions") or []
    region = _names(subs[0]) if subs else ""
    city = _names(rec.get("city"))
    if not (country or city):
        return None
    return {"country": country, "region": region[:80], "city": city[:80]}


def _trust_cf_headers():
    if current_app.config.get("TRUST_CF_HEADERS"):
        return True
    from .security import behind_cloudflare, via_local_tunnel
    return behind_cloudflare() or via_local_tunnel()


def _conn(path):
    c = getattr(_local, "conn", None)
    if c is None or getattr(_local, "path", None) != path:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        _local.conn, _local.path = c, path
    return c


@lru_cache(maxsize=4096)
def _lookup_db(path, ip, mtime):
    try:
        key = _hex(ip)
    except ValueError:
        return None
    try:
        row = _conn(path).execute(
            "SELECT end_hex, country, region, city FROM ranges WHERE start_hex <= ? "
            "ORDER BY start_hex DESC LIMIT 1", (key,)).fetchone()
    except sqlite3.Error:
        return None
    if row and row[0] >= key:
        return {"country": row[1] or "", "region": row[2] or "", "city": row[3] or ""}
    return None


def lookup(ip):
    """Return {'country', 'region', 'city'} (any may be '')."""
    loc = {"country": "", "region": "", "city": ""}
    if _trust_cf_headers():
        cc = (request.headers.get("CF-IPCountry") or "").upper()
        if len(cc) == 2 and cc.isalpha() and cc not in ("XX", "T1"):
            loc = {"country": cc, "region": (request.headers.get("CF-Region") or "")[:80],
                   "city": (request.headers.get("CF-IPCity") or "")[:80]}
    if not loc["city"]:
        found = None
        mp, dp = mmdb_path(), db_path()
        if mp and os.path.isfile(mp):
            found = _lookup_mmdb(mp, ip, os.path.getmtime(mp))
        if not found and dp and os.path.isfile(dp):
            found = _lookup_db(dp, ip, os.path.getmtime(dp))
        # the database adds city/region; if Cloudflare named another country, keep Cloudflare's country only
        if found and (not loc["country"] or loc["country"] == found["country"]):
            loc = {"country": found["country"] or loc["country"], "region": found["region"], "city": found["city"]}
    if loc["country"] or loc["city"]:
        return loc
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_loopback or addr.is_private or addr.is_link_local:
            return {"country": "", "region": "", "city": "Local network"}
    except ValueError:
        pass
    return {"country": "", "region": "", "city": ""}


def place(country, region="", city=""):
    """Human-readable place, e.g. 'Lahore, Punjab, Pakistan'."""
    parts = [p for p in (city, region if region != city else "", country_name(country)) if p]
    return ", ".join(parts) or "Unknown"


# ---------------------------------------------------------------- importer

def _is_ip(text):
    try:
        ipaddress.ip_address(text)
        return True
    except ValueError:
        return False


def import_csv(src, dest, progress=None):
    """Build the lookup database from a DB-IP Lite CSV (.csv or .csv.gz). Returns rows imported.

    Supported layouts (DB-IP documentation):
      City Lite:    ip_start, ip_end, continent, country, stateprov, city, latitude, longitude
      Country Lite: ip_start, ip_end, country
    """
    opener = gzip.open if src.endswith(".gz") else open
    tmp = dest + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    con.execute("CREATE TABLE ranges (start_hex TEXT PRIMARY KEY, end_hex TEXT NOT NULL, country TEXT, "
                "region TEXT, city TEXT) WITHOUT ROWID")
    count, batch = 0, []
    with opener(src, "rb") as raw:
        reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline=""))
        for row in reader:
            if len(row) < 3 or not _is_ip(row[0]) or not _is_ip(row[1]):
                continue  # header or malformed line
            if len(row) >= 6:
                country, region, city = row[3], row[4], row[5]
            else:
                country, region, city = row[2], "", ""
            batch.append((_hex(row[0]), _hex(row[1]), country[:2].upper(), region[:80], city[:80]))
            if len(batch) >= 50000:
                con.executemany("INSERT OR REPLACE INTO ranges VALUES (?, ?, ?, ?, ?)", batch)
                count += len(batch)
                batch = []
                if progress:
                    progress(count)
    if batch:
        con.executemany("INSERT OR REPLACE INTO ranges VALUES (?, ?, ?, ?, ?)", batch)
        count += len(batch)
    con.commit()
    con.execute("VACUUM")
    con.close()
    if count == 0:
        os.remove(tmp)
        raise ValueError("No IP ranges found. Use the DB-IP 'IP to City Lite' or 'IP to Country Lite' CSV file.")
    os.replace(tmp, dest)
    _lookup_db.cache_clear()
    return count


# ---------------------------------------------------------------- monthly automatic download

import gzip as _gzip  # noqa: E402
import json as _json  # noqa: E402
import time as _time  # noqa: E402
from datetime import datetime as _dt, timedelta as _td, timezone as _tz  # noqa: E402

FRESH_DAYS = 32
MAX_DOWNLOAD = 1024 * 1024 * 1024        # refuse anything over 1 GB


def status_path(dest):
    return dest + ".status.json"


def read_status(dest):
    try:
        with open(status_path(dest), encoding="utf-8") as fh:
            return _json.load(fh)
    except (OSError, ValueError):
        return {}


def _write_status(dest, **data):
    data["at"] = _dt.now(_tz.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        with open(status_path(dest), "w", encoding="utf-8") as fh:
            _json.dump(data, fh)
    except OSError:  # pragma: no cover
        pass


def _months(now=None):
    now = now or _dt.now(_tz.utc)
    prev = now.replace(day=1) - _td(days=1)
    return [now.strftime("%Y-%m"), prev.strftime("%Y-%m")]


def is_fresh(dest):
    return os.path.isfile(dest) and (_time.time() - os.path.getmtime(dest)) < FRESH_DAYS * 86400


def update_mmdb(dest, url_template, log=None, opener=None):
    """Download the newest DB-IP City Lite .mmdb if ours is missing or older than a month.
    Returns 'fresh', 'busy', 'updated' or 'failed'. Safe to call from several processes at once."""
    import urllib.request
    from .vendor import maxminddb
    if is_fresh(dest):
        return "fresh"
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    lock = dest + ".lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        if _time.time() - os.path.getmtime(lock) < 3 * 3600:
            return "busy"
        os.remove(lock)
        return update_mmdb(dest, url_template, log, opener)
    part = dest + ".part"
    errors = []
    try:
        _write_status(dest, state="downloading")
        for month in _months():
            url = url_template.format(month=month)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "SurMusic/1.1 (+geoip monthly update)"})
                with (opener or urllib.request.urlopen)(req, timeout=120) as resp, open(part, "wb") as out:
                    src = _gzip.GzipFile(fileobj=resp) if url.endswith(".gz") else resp
                    total = 0
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > MAX_DOWNLOAD:
                            raise ValueError("download too large")
                        out.write(chunk)
                check = maxminddb.open_database(part, maxminddb.MODE_FILE)   # must be a valid database
                try:
                    kind = check.metadata().database_type
                    check.get("8.8.8.8")
                finally:
                    check.close()
                _close_readers(dest)
                for attempt in range(10):          # Windows: a reader may still hold the old file briefly
                    try:
                        os.replace(part, dest)
                        break
                    except PermissionError:
                        _close_readers(dest)
                        _time.sleep(0.5)
                else:
                    raise OSError("could not replace the old database file")
                _lookup_mmdb.cache_clear()
                _write_status(dest, state="ready", month=month, kind=kind)
                if log:
                    log.info("Visitor city database updated (DB-IP %s, %s).", month, kind)
                return "updated"
            except Exception as exc:  # try last month's file next
                errors.append(f"{month}: {exc}")
        _write_status(dest, state="failed", error="; ".join(errors)[:500])
        if log:
            log.warning("Visitor city database could not be downloaded: %s", "; ".join(errors))
        return "failed"
    finally:
        for f in (part, lock):
            try:
                os.remove(f)
            except OSError:
                pass


def start_auto_update(app):
    """Background thread: check at start and then once a day. Never blocks the website."""
    cfg = app.config
    if not cfg.get("GEOIP_AUTO") or cfg.get("TESTING") or not cfg.get("GEOIP_MMDB"):
        return None

    def loop():
        while True:
            try:
                result = update_mmdb(cfg["GEOIP_MMDB"], cfg["GEOIP_URL"], app.logger)
            except Exception:  # pragma: no cover
                app.logger.exception("Visitor city database update failed")
                result = "failed"
            _time.sleep(3 * 3600 if result in ("failed", "busy") else 24 * 3600)

    t = threading.Thread(target=loop, name="geoip-update", daemon=True)
    t.start()
    return t

