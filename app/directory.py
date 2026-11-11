# © 2026 Mousa International Software House. All rights reserved.
"""World station directory: the most-listened stations on Radio Browser that play in a browser (https, not HLS).

Every one of them gets its own real page (/station/<id>/<name>) and is listed in /sitemap-stations-N.xml.
Kept in its OWN SQLite file (STORAGE_DIR/directory.sqlite) — never in the main database — so station pages
and sitemaps never cost database network transfer (a free hosted database has a monthly transfer limit).

Hosting without a permanent disk (Render free) loses that file at every restart. So a compressed copy is kept
IN THE CODE (app/data/directory.jsonl.gz, rebuilt weekly by tools/build_directory.py on GitHub, not on our
server). At start the file is rebuilt from that copy line by line (little memory, no internet). The server
itself fetches from Radio Browser only when there is no copy, or on a permanent disk once a week.
A new list is always built in a separate file and replaces the old one only when complete.
"""
import gzip
import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

PAGES = 16            # 16 x 2,500 = up to 40,000 directory entries (before removing http and HLS streams)
PER_PAGE = 2500
EVERY_DAYS = 7          # only used when this server fetches the list itself (permanent disk)


BUNDLE = os.path.join(os.path.dirname(__file__), "data", "directory.jsonl.gz")


def _path(app):
    return os.path.join(app.config["STORAGE_DIR"], "directory.sqlite")


def _open(app, path=None):
    conn = sqlite3.connect(path or _path(app), timeout=15)
    conn.execute("CREATE TABLE IF NOT EXISTS stations (uuid TEXT PRIMARY KEY, chunk INTEGER NOT NULL, body TEXT NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS stations_chunk ON stations (chunk)")
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    return conn


def _app():
    from flask import current_app
    return current_app._get_current_object()


def chunks(app=None):
    """Chunk numbers that have stations, in order: [0, 1, ...]."""
    app = app or _app()
    if not os.path.exists(_path(app)):
        return []
    with _open(app) as conn:
        return [r[0] for r in conn.execute("SELECT DISTINCT chunk FROM stations ORDER BY chunk")]


def chunk_stations(n, app=None):
    app = app or _app()
    if not os.path.exists(_path(app)):
        return []
    with _open(app) as conn:
        return [json.loads(r[0]) for r in conn.execute("SELECT body FROM stations WHERE chunk = ? ORDER BY rowid", (n,))]


def find(uuid, app=None):
    """One station by id, or None (a local file lookup: fast, no database traffic)."""
    app = app or _app()
    if not os.path.exists(_path(app)):
        return None
    with _open(app) as conn:
        row = conn.execute("SELECT body FROM stations WHERE uuid = ?", (uuid,)).fetchone()
    return json.loads(row[0]) if row else None


def save_chunk(app, n, stations, path=None):
    conn = _open(app, path)
    try:
        with conn:
            conn.execute("DELETE FROM stations WHERE chunk = ?", (n,))
            conn.executemany("INSERT OR REPLACE INTO stations (uuid, chunk, body) VALUES (?, ?, ?)",
                             [(st["uuid"], n, json.dumps(st)) for st in stations if st.get("uuid")])
    finally:
        conn.close()


def count(app=None):
    app = app or _app()
    if not os.path.exists(_path(app)):
        return 0
    conn = _open(app)
    try:
        return conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0]
    finally:
        conn.close()


_FIRST = "lower(substr(ltrim(json_extract(body, '$.name')), 1, 1))"


def by_letter(letter, limit=200, offset=0, app=None):
    """(stations, total) whose name starts with this letter ('0' = anything else), most listened first."""
    app = app or _app()
    if not os.path.exists(_path(app)):
        return [], 0
    where = f"{_FIRST} = ?" if letter != "0" else f"NOT ({_FIRST} BETWEEN 'a' AND 'z')"
    args = (letter,) if letter != "0" else ()
    conn = _open(app)
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM stations WHERE {where}", args).fetchone()[0]
        rows = conn.execute(f"SELECT body FROM stations WHERE {where} "
                            f"ORDER BY json_extract(body, '$.clicks') DESC LIMIT ? OFFSET ?",
                            args + (int(limit), int(offset))).fetchall()
    finally:
        conn.close()
    return [json.loads(r[0]) for r in rows], total


def letter_counts(app=None):
    """{letter: number of stations} for the A–Z pages ('0' = numbers and other characters)."""
    app = app or _app()
    if not os.path.exists(_path(app)):
        return {}
    conn = _open(app)
    try:
        rows = conn.execute(f"SELECT CASE WHEN {_FIRST} BETWEEN 'a' AND 'z' THEN {_FIRST} ELSE '0' END AS k, "
                            f"COUNT(*) FROM stations GROUP BY k").fetchall()
    finally:
        conn.close()
    return {k: n for k, n in rows}


def _swap_in(app, tmp):
    """Replace the live file with a finished new one in one step (readers see the old or the new, never half)."""
    final = _path(app)
    for ext in ("-wal", "-shm"):
        try:
            os.remove(tmp + ext)
        except OSError:
            pass
    os.replace(tmp, final)


def load_bundle(app, bundle=None):
    """Build directory.sqlite from the copy in the code. Streams line by line. Returns the number of stations."""
    bundle = bundle or BUNDLE
    if not os.path.exists(bundle):
        return 0
    tmp = _path(app) + ".new"
    if os.path.exists(tmp):
        os.remove(tmp)
    conn = _open(app, tmp)
    total = 0
    try:
        batch = []
        with gzip.open(bundle, "rt", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                st = row.get("s") if isinstance(row, dict) else None
                if isinstance(st, dict) and st.get("uuid"):
                    batch.append((st["uuid"], int(row.get("c", 0)), json.dumps(st)))
                if len(batch) >= 1000:
                    conn.executemany("INSERT OR REPLACE INTO stations (uuid, chunk, body) VALUES (?, ?, ?)", batch)
                    total += len(batch)
                    batch = []
        if batch:
            conn.executemany("INSERT OR REPLACE INTO stations (uuid, chunk, body) VALUES (?, ?, ?)", batch)
            total += len(batch)
        _set(conn, "done")
        conn.commit()
    except Exception:
        conn.close()
        os.remove(tmp)
        raise
    conn.close()
    if total:
        _swap_in(app, tmp)
    else:
        os.remove(tmp)
    return total


def _get(conn, key):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return datetime.fromisoformat(row[0]) if row else None


def _set(conn, key):
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, datetime.now(timezone.utc).isoformat()))


def refresh(app, pause=4.0):
    """Fetch the list from Radio Browser into a NEW file; it replaces the old one only when complete."""
    from . import radio
    now = datetime.now(timezone.utc)
    with app.app_context():
        tmp = _path(app) + ".new"
        try:
            if os.path.exists(_path(app)):
                with _open(app) as conn:
                    done, lock = _get(conn, "done"), _get(conn, "lock")
                    if lock and lock > now - timedelta(hours=2):
                        return                               # another worker is fetching right now
                    if done and done > now - timedelta(days=EVERY_DAYS):
                        return
                    _set(conn, "lock")
            if os.path.exists(tmp):
                os.remove(tmp)
            total = 0
            for i in range(PAGES):
                try:
                    raw = radio._fetch_json(f"/json/stations/search?is_https=true&hidebroken=true&order=clickcount"
                                            f"&reverse=true&limit={PER_PAGE}&offset={i * PER_PAGE}")
                except radio.RadioError:
                    break
                if not isinstance(raw, list) or not raw:
                    break
                stations = radio.normalize(raw)
                save_chunk(app, i, stations, path=tmp)
                total += len(stations)
                del raw, stations
                time.sleep(pause)                            # gentle on Radio Browser and on our small server
            old = count(app)
            if total and (total >= 1000 or total >= old // 2):  # a real list (not a half-failed fetch): swap in
                with _open(app, tmp) as conn:
                    _set(conn, "done")
                _swap_in(app, tmp)
                log.info("Station directory saved: %d stations", total)
            else:                                            # failed or tiny: keep the old list
                if os.path.exists(tmp):
                    os.remove(tmp)
                if os.path.exists(_path(app)):
                    with _open(app) as conn:
                        conn.execute("DELETE FROM meta WHERE key = 'lock'")
                log.info("Station directory not replaced (only %d stations fetched); old list kept", total)
        except Exception as exc:                              # never break the site for this
            log.info("Station directory not refreshed: %s", exc)


def start(app):
    """At start: fill the list from the copy in the code if it is missing. Then, only with a permanent disk (or
    DIRECTORY_FETCH=1, or no copy in the code), check every 6 hours and fetch when a week old."""
    if app.config.get("TESTING") or app.config.get("RADIO_DEMO"):
        return
    try:
        if not os.path.exists(_path(app)) or not count(app):
            n = load_bundle(app)
            if n:
                log.info("Station directory loaded from the copy in the code: %d stations", n)
    except Exception as exc:                                  # never block the start
        log.info("Station directory copy not loaded: %s", exc)
    site = app.config.get("SITE_URL", "")
    if not site.startswith("https://") or "localhost" in site:
        return
    fetch = os.environ.get("DIRECTORY_FETCH")
    if fetch == "0":
        return
    if fetch != "1" and os.path.exists(BUNDLE) and not app.config.get("STORAGE_PERSISTENT", True):
        return                                                # no disk: the weekly copy comes with the code

    def loop():
        time.sleep(90)                                        # let the site start first
        while True:
            refresh(app)
            time.sleep(6 * 3600)

    threading.Thread(target=loop, name="station-directory", daemon=True).start()
