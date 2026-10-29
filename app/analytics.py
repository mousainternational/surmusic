"""Privacy-friendly visitor analytics for the admin panel.

* Location (best available source first):
    1. the local DB-IP geolocation database, if installed (city + country — see app/geo.py),
    2. Cloudflare's visitor-location headers, when TRUST_CF_HEADERS=1,
    3. the browser's time zone — country only (Asia/Karachi covers all of Pakistan, so no city).
  No IP address is stored.
* visitor_id is a keyed hash of IP + browser + today's date: it counts unique visitors per day
  but cannot be turned back into an IP address and changes every day.
"""
import hashlib
import hmac
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from flask import current_app, request, session

from . import geo, lowdb
from .db import get_db, utcnow
from .security import client_ip

_TZ = json.loads((Path(__file__).parent / "data" / "timezones.json").read_text(encoding="utf-8"))
BOT_RE = re.compile(r"bot|crawl|spider|slurp|headless|lighthouse|preview|facebookexternalhit|curl|wget|python-requests",
                    re.I)
KINDS = {
    "page_view": "Page view", "play": "Played a station", "signup": "Signed up", "login": "Signed in",
    "login_failed": "Failed sign-in", "logout": "Signed out", "password_reset": "Reset password",
    "account_deleted": "Deleted account", "download": "Downloaded app", "contact": "Sent a message",
    "favorite": "Saved a favourite", "listened": "Listened", "affiliate_click": "Opened a partner offer",
}
LIVE_SECONDS = 150


def country_name(code):
    if not code:
        return "Unknown"
    name = geo.country_name(code)            # standard English names (Babel), e.g. "United Kingdom"
    return name if name and name != code.upper() else (_TZ["countries"].get(code) or code)


def flag(code):
    if not code or len(code) != 2 or not code.isalpha():
        return "🌐"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


def location_from_tz(tz):
    """'Asia/Karachi' → ('PK', ''). Country only: one time zone covers many cities."""
    if not isinstance(tz, str) or len(tz) > 64:
        return "", ""
    return _TZ["zones"].get(tz, ""), ""


def parse_ua(ua):
    ua = ua or ""
    if re.search(r"iPad|Tablet|Nexus 7|Nexus 10|SM-T|Kindle", ua):
        device = "Tablet"
    elif re.search(r"Mobi|Android|iPhone|iPod", ua):
        device = "Mobile"
    else:
        device = "Desktop"
    for name, pat in (("Edge", r"Edg/"), ("Opera", r"OPR/|Opera"), ("Samsung Internet", r"SamsungBrowser"),
                      ("UC Browser", r"UCBrowser"), ("Firefox", r"Firefox/|FxiOS"), ("Chrome", r"Chrome/|CriOS"),
                      ("Safari", r"Safari/")):
        if re.search(pat, ua):
            browser = name
            break
    else:
        browser = "Other"
    for name, pat in (("Android", r"Android"), ("iOS", r"iPhone|iPad|iPod"), ("Windows", r"Windows"),
                      ("ChromeOS", r"CrOS"), ("macOS", r"Mac OS X|Macintosh"), ("Linux", r"Linux")):
        if re.search(pat, ua):
            os_name = name
            break
    else:
        os_name = "Other"
    return device, browser, os_name


def is_bot():
    return bool(BOT_RE.search(request.headers.get("User-Agent", "")))


def visitor_id():
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = current_app.config["SECRET_KEY"].encode()
    raw = f"{day}|{client_ip()}|{request.headers.get('User-Agent', '')}".encode()
    return hmac.new(key, raw, hashlib.sha256).hexdigest()[:20]


def _location():
    """(country code, city or region) for the current request."""
    loc = geo.lookup(client_ip())
    if loc["country"]:
        return loc["country"], (loc["city"] or loc["region"])[:60]
    return session.get("geo_c", ""), ""


def remember_timezone(tz):
    code, city = location_from_tz(tz)
    if code:
        session["geo_c"], session["geo_r"] = code, city
    return code, city


def record(kind, user_id=None, path="", detail="", referrer=""):
    """Store one analytics event (skipped for bots)."""
    if kind not in KINDS or is_bot():
        return
    device, browser, os_name = parse_ua(request.headers.get("User-Agent", ""))
    code, city = _location()
    vid = visitor_id()
    sql = ("INSERT INTO events (kind, visitor_id, user_id, path, referrer, country, region, device, browser, os, "
           "detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
    params = (kind, vid, user_id, path[:200], referrer[:120], code, city[:60], device, browser, os_name,
              detail[:200], utcnow())
    if lowdb.enabled():
        lowdb.saw_visitor(vid)
        lowdb.defer(sql, params)
        return
    db = get_db()
    db.execute(sql, params)
    db.commit()


def referrer_domain(ref):
    try:
        host = urlparse(ref or "").netloc.lower()
    except ValueError:
        return ""
    if not host or host == request.host:
        return ""
    return host[4:] if host.startswith("www.") else host


def close_session(row, extra=30):
    """A listening session ended: store how long it lasted as a 'listened' event.
    `extra` covers the time after the last check-in (about half a minute when the tab just vanished)."""
    try:
        secs = (datetime.fromisoformat(row["last_seen"]) - datetime.fromisoformat(row["started_at"])).total_seconds()
    except (TypeError, ValueError):
        return
    secs = max(0, int(secs)) + extra
    if secs < 45:
        return
    mins = max(1, round(secs / 60))
    sql = ("INSERT INTO events (kind, visitor_id, user_id, path, referrer, country, region, device, browser, os, "
           "detail, created_at) VALUES ('listened', ?, ?, '', '', ?, ?, ?, ?, '', ?, ?)")
    params = (row["session_key"][1:] if row["session_key"].startswith("v") else "", row["user_id"],
              row["country"], row["region"], row["device"], row["browser"],
              f"{row['station_name']} · {mins} min"[:200], row["last_seen"])
    if lowdb.enabled():
        lowdb.defer(sql, params)
    else:
        get_db().execute(sql, params)


_close = close_session


def heartbeat(user_id, station_name, category):
    """Mark this browser as listening right now."""
    if is_bot():
        return
    device, browser, _ = parse_ua(request.headers.get("User-Agent", ""))
    code, city = _location()
    key = f"u{user_id}" if user_id else f"v{visitor_id()}"
    now = utcnow()
    if lowdb.enabled():
        lowdb.saw_visitor(visitor_id())
        st = lowdb.state()
        with st.lock:
            row = st.live.get(key)
            same = row and row["station_name"] == station_name and row["_seen"] > time.time() - LIVE_SECONDS
            if row and not same:
                st.live.pop(key, None)
            st.live[key] = {"session_key": key, "user_id": user_id, "station_name": station_name[:120],
                            "category": category[:20], "country": code, "region": city[:60], "device": device,
                            "browser": browser, "started_at": row["started_at"] if same else now, "last_seen": now,
                            "_seen": time.time()}
        if row and not same:
            close_session(row)
        return
    db = get_db()
    row = db.one("SELECT * FROM live_sessions WHERE session_key = ?", (key,))
    same = row and row["station_name"] == station_name and \
        datetime.fromisoformat(row["last_seen"]) > datetime.now(timezone.utc) - timedelta(seconds=LIVE_SECONDS)
    if row and not same:
        _close(row)
    started = row["started_at"] if same else now
    db.execute("DELETE FROM live_sessions WHERE session_key = ?", (key,))
    db.execute("INSERT INTO live_sessions (session_key, user_id, station_name, category, country, region, device, "
               "browser, started_at, last_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
               (key, user_id, station_name[:120], category[:20], code, city[:60], device, browser, started, now))
    db.commit()


def stop_listening(user_id):
    key = f"u{user_id}" if user_id else f"v{visitor_id()}"
    if lowdb.enabled():
        st = lowdb.state()
        with st.lock:
            row = st.live.pop(key, None)
        if row:
            last = datetime.fromisoformat(row["last_seen"])
            row["last_seen"] = min(datetime.now(timezone.utc), last + timedelta(seconds=60)).replace(
                microsecond=0).isoformat()
            close_session(row, extra=0)
        return
    db = get_db()
    row = db.one("SELECT * FROM live_sessions WHERE session_key = ?", (key,))
    if row:
        # Stopped now — but never count more than one minute past the last check-in.
        last = datetime.fromisoformat(row["last_seen"])
        row["last_seen"] = min(datetime.now(timezone.utc), last + timedelta(seconds=60)).replace(
            microsecond=0).isoformat()
        _close(row, extra=0)
    db.execute("DELETE FROM live_sessions WHERE session_key = ?", (key,))
    db.commit()


def _sum_minutes(rows):
    total = 0
    for r in rows:
        m = re.search(r"(\d+) min$", r["detail"] or "")
        if m:
            total += int(m.group(1))
    return total


def _minutes_since(since):
    return _sum_minutes(get_db().all("SELECT detail FROM events WHERE kind = 'listened' AND created_at >= ?", (since,)))


def listening_minutes(user_id):
    """Total minutes from 'listened' events (detail ends with '· N min')."""
    return _sum_minutes(get_db().all("SELECT detail FROM events WHERE user_id = ? AND kind = 'listened'", (user_id,)))


# ---------------------------------------------------------------- admin queries

def _since(days=0, minutes=0):
    return (datetime.now(timezone.utc) - timedelta(days=days, minutes=minutes)).replace(microsecond=0).isoformat()


def live_now():
    if lowdb.enabled():
        return _live_now_memory()
    db = get_db()
    cutoff = _since(minutes=LIVE_SECONDS / 60)
    for stale in db.all("SELECT * FROM live_sessions WHERE last_seen < ?", (cutoff,)):
        _close(stale)  # tab closed without saying goodbye: record what we know
    db.execute("DELETE FROM live_sessions WHERE last_seen < ?", (cutoff,))
    db.commit()
    listeners = db.all("SELECT l.*, u.email, u.display_name FROM live_sessions l LEFT JOIN users u ON u.id = l.user_id "
                       "WHERE l.last_seen >= ? ORDER BY l.started_at", (cutoff,))
    online = db.scalar("SELECT COUNT(DISTINCT visitor_id) FROM events WHERE created_at >= ?", (_since(minutes=5),))
    now = datetime.now(timezone.utc)
    for r in listeners:
        r["country_name"] = country_name(r["country"])
        r["flag"] = flag(r["country"])
        try:
            r["minutes"] = max(0, int((now - datetime.fromisoformat(r["started_at"])).total_seconds() // 60))
        except ValueError:
            r["minutes"] = 0
    return {"listeners": listeners, "online": online or 0}


def summary(days):
    db = get_db()
    since = _since(days=days)

    def count(kind, distinct=False):
        col = "COUNT(DISTINCT visitor_id)" if distinct else "COUNT(*)"
        return db.scalar(f"SELECT {col} FROM events WHERE kind = ? AND created_at >= ?", (kind, since)) or 0

    totals = {
        "visitors": db.scalar("SELECT COUNT(DISTINCT visitor_id) FROM events WHERE created_at >= ?", (since,)) or 0,
        "page_views": count("page_view"),
        "plays": count("play"),
        "listeners": count("play", distinct=True),
        "signups": count("signup"),
        "logins": count("login"),
        "failed_logins": count("login_failed"),
        "downloads": count("download"),
        "listen_minutes": _minutes_since(since),
    }

    def top(col, kind=None, limit=10, where=""):
        extra = " AND kind = ?" if kind else ""
        params = [since] + ([kind] if kind else [])
        return db.all(f"SELECT {col} AS label, COUNT(DISTINCT visitor_id) AS visitors, COUNT(*) AS n FROM events "
                      f"WHERE created_at >= ?{extra}{where} AND {col} <> '' GROUP BY {col} ORDER BY visitors DESC, n DESC "
                      f"LIMIT {int(limit)}", params)

    countries = top("country")
    for c in countries:
        c["name"], c["flag"] = country_name(c["label"]), flag(c["label"])
    cities = db.all("SELECT country, region, COUNT(DISTINCT visitor_id) AS visitors, COUNT(*) AS n FROM events "
                    "WHERE created_at >= ? AND region <> '' GROUP BY country, region ORDER BY visitors DESC, n DESC "
                    "LIMIT 15", (since,))
    for c in cities:
        c["flag"], c["country_name"] = flag(c["country"]), country_name(c["country"])
    by_day = {r["day"]: r for r in db.all(
        "SELECT SUBSTR(created_at, 1, 10) AS day, COUNT(DISTINCT visitor_id) AS visitors, "
        "SUM(CASE WHEN kind = 'page_view' THEN 1 ELSE 0 END) AS views, "
        "SUM(CASE WHEN kind = 'play' THEN 1 ELSE 0 END) AS plays, "
        "SUM(CASE WHEN kind = 'signup' THEN 1 ELSE 0 END) AS signups "
        "FROM events WHERE created_at >= ? GROUP BY SUBSTR(created_at, 1, 10)", (since,))}
    today = datetime.now(timezone.utc).date()
    days_list = []
    for i in range(min(days, 60) - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        r = by_day.get(d) or {}
        days_list.append({"day": d, "visitors": r.get("visitors") or 0, "views": r.get("views") or 0,
                          "plays": r.get("plays") or 0, "signups": r.get("signups") or 0})
    stations = db.all("SELECT detail AS label, COUNT(*) AS n, COUNT(DISTINCT visitor_id) AS visitors FROM events "
                      "WHERE kind = 'play' AND created_at >= ? AND detail <> '' GROUP BY detail ORDER BY n DESC LIMIT 10",
                      (since,))
    return {
        "totals": totals, "days": days_list,
        "peak": max([d["visitors"] for d in days_list] + [d["plays"] for d in days_list] + [1]),
        "countries": countries, "cities": cities,
        "pages": top("path", "page_view"), "referrers": top("referrer", "page_view"),
        "devices": top("device"), "browsers": top("browser"), "systems": top("os"),
        "stations": stations,
    }


def recent(kind=None, user_id=None, limit=100, offset=0):
    db = get_db()
    where, params = [], []
    if kind in KINDS:
        where.append("e.kind = ?")
        params.append(kind)
    if user_id:
        where.append("e.user_id = ?")
        params.append(user_id)
    w = ("WHERE " + " AND ".join(where)) if where else ""
    rows = db.all(f"SELECT e.*, u.email, u.display_name FROM events e LEFT JOIN users u ON u.id = e.user_id {w} "
                  f"ORDER BY e.id DESC LIMIT {int(limit)} OFFSET {int(offset)}", params)
    for r in rows:
        r["label"] = KINDS.get(r["kind"], r["kind"])
        r["flag"], r["country_name"] = flag(r["country"]), country_name(r["country"]) if r["country"] else ""
    return rows


def user_locations(user_ids):
    """Most recent known location per user (for the Users table)."""
    if not user_ids:
        return {}
    db = get_db()
    out = {}
    for uid in user_ids:
        r = db.one("SELECT country, region, created_at FROM events WHERE user_id = ? AND country <> '' "
                   "ORDER BY id DESC LIMIT 1", (uid,))
        if r:
            out[uid] = {"flag": flag(r["country"]), "place": ", ".join(x for x in (r["region"], country_name(r["country"])) if x)}
    return out


def purge_old():
    """Retention: page views PAGEVIEW_DAYS (default 180), everything else EVENT_DAYS (default 365)."""
    db = get_db()
    db.execute("DELETE FROM events WHERE kind = 'page_view' AND created_at < ?",
               (_since(days=current_app.config.get("PAGEVIEW_DAYS", 180)),))
    db.execute("DELETE FROM events WHERE created_at < ?", (_since(days=current_app.config.get("EVENT_DAYS", 365)),))
    db.commit()


def _live_now_memory():
    lowdb._sweep(current_app._get_current_object())
    st = lowdb.state()
    with st.lock:
        listeners = sorted((dict(v) for v in st.live.values()), key=lambda r: r["started_at"])
    ids = sorted({r["user_id"] for r in listeners if r["user_id"]})
    people = {}
    if ids:
        marks = ", ".join("?" for _ in ids)
        people = {r["id"]: r for r in get_db().all(f"SELECT id, email, display_name FROM users WHERE id IN ({marks})", ids)}
    now = datetime.now(timezone.utc)
    for r in listeners:
        r.pop("_seen", None)
        p = people.get(r["user_id"]) or {}
        r["email"], r["display_name"] = p.get("email"), p.get("display_name")
        r["country_name"] = country_name(r["country"])
        r["flag"] = flag(r["country"])
        try:
            r["minutes"] = max(0, int((now - datetime.fromisoformat(r["started_at"])).total_seconds() // 60))
        except ValueError:
            r["minutes"] = 0
    return {"listeners": listeners, "online": lowdb.online_visitors()}

