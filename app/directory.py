# © 2026 Mousa International Software House. All rights reserved.
"""World station directory: the most-listened stations on Radio Browser that play in a browser (https, not HLS).

Every one of them gets its own real page (/station/<id>/<name>) and is listed in /sitemap-stations-N.xml.
Fetched in the background once a week, one page at a time. Kept in its OWN small SQLite file on the
permanent disk (STORAGE_DIR/directory.sqlite) — never in the main database — so station pages and
sitemaps never cost database network transfer (a free hosted database has a monthly transfer limit).
"""
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
EVERY_DAYS = 7


def _path(app):
    return os.path.join(app.config["STORAGE_DIR"], "directory.sqlite")


def _open(app):
    conn = sqlite3.connect(_path(app), timeout=15)
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


def save_chunk(app, n, stations):
    with _open(app) as conn:
        conn.execute("DELETE FROM stations WHERE chunk = ?", (n,))
        conn.executemany("INSERT OR REPLACE INTO stations (uuid, chunk, body) VALUES (?, ?, ?)",
                         ((st["uuid"], n, json.dumps(st)) for st in stations if st.get("uuid")))


def _get(conn, key):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return datetime.fromisoformat(row[0]) if row else None


def _set(conn, key):
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, datetime.now(timezone.utc).isoformat()))


def refresh(app, pause=4.0):
    from . import radio
    now = datetime.now(timezone.utc)
    with app.app_context():
        try:
            with _open(app) as conn:
                done, lock = _get(conn, "done"), _get(conn, "lock")
                if lock and lock > now - timedelta(hours=2):
                    return                                   # another worker is fetching right now
                if done and done > now - timedelta(days=EVERY_DAYS):
                    return
                _set(conn, "lock")
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
                save_chunk(app, i, stations)
                total += len(stations)
                del raw, stations
                time.sleep(pause)                            # gentle on Radio Browser and on our small server
            with _open(app) as conn:
                _set(conn, "done")
                conn.execute("DELETE FROM meta WHERE key = 'lock'")
            log.info("Station directory saved: %d stations", total)
        except Exception as exc:                              # never break the site for this
            log.info("Station directory not refreshed: %s", exc)


def start(app):
    """Background loop: check every 6 hours, fetch when a week old. Not in tests or on a local copy."""
    site = app.config.get("SITE_URL", "")
    if app.config.get("TESTING") or app.config.get("RADIO_DEMO") or not site.startswith("https://") or "localhost" in site:
        return

    def loop():
        time.sleep(90)                                        # let the site start first
        while True:
            refresh(app)
            time.sleep(6 * 3600)

    threading.Thread(target=loop, name="station-directory", daemon=True).start()
