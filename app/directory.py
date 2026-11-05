# © 2026 Mousa International Software House. All rights reserved.
"""World station directory: the most-listened stations on Radio Browser that play in a browser (https, not HLS).

Every one of them gets its own real page (/station/<id>/<name>) and is listed in /sitemap-stations-N.xml,
so people searching a station's name can find it on Sur Music. Fetched in the background once a week,
one small page at a time (never while a visitor waits), and kept in the station_cache table as "dir:N".
"""
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

PAGES = 16            # 16 x 2,500 = up to 40,000 directory entries (before removing http and HLS streams)
PER_PAGE = 2500
EVERY_DAYS = 7
KEY = "dir:{}"


def chunk_keys(db):
    """The saved directory chunks, in order: ['dir:0', 'dir:1', ...]."""
    rows = db.all("SELECT cache_key FROM station_cache WHERE cache_key LIKE ?", ("dir:%",))
    keys = [r["cache_key"] for r in rows if r["cache_key"][4:].isdigit()]
    return sorted(keys, key=lambda k: int(k[4:]))


def _due(db):
    row = db.one("SELECT fetched_at FROM station_cache WHERE cache_key = ?", (KEY.format(0),))
    lock = db.one("SELECT fetched_at FROM station_cache WHERE cache_key = ?", ("dir-lock",))
    now = datetime.now(timezone.utc)
    if lock and datetime.fromisoformat(lock["fetched_at"]) > now - timedelta(hours=2):
        return False                                  # another worker is fetching right now
    return not row or datetime.fromisoformat(row["fetched_at"]) < now - timedelta(days=EVERY_DAYS)


def refresh(app, pause=4.0):
    from . import radio
    from .db import Database, utcnow
    with app.app_context():
        db = Database(app.config["DATABASE_URL"])
        try:
            if not _due(db):
                return
            db.execute("DELETE FROM station_cache WHERE cache_key = ?", ("dir-lock",))
            db.execute("INSERT INTO station_cache (cache_key, body, fetched_at) VALUES (?, ?, ?)", ("dir-lock", "1", utcnow()))
            db.commit()
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
                for st in stations:                      # only what a station page needs: smaller rows
                    st.pop("tags_full", None)
                db.execute("DELETE FROM station_cache WHERE cache_key = ?", (KEY.format(i),))
                db.execute("INSERT INTO station_cache (cache_key, body, fetched_at) VALUES (?, ?, ?)",
                           (KEY.format(i), json.dumps(stations), utcnow()))
                db.commit()
                total += len(stations)
                del raw, stations
                time.sleep(pause)                        # gentle on Radio Browser and on our small server
            log.info("Station directory saved: %d stations", total)
        except Exception as exc:                          # never break the site for this
            db.rollback()
            log.info("Station directory not refreshed: %s", exc)
        finally:
            db.close()


def start(app):
    """Background loop: check every 6 hours, fetch when a week old. Not in tests or on a local copy."""
    site = app.config.get("SITE_URL", "")
    if app.config.get("TESTING") or app.config.get("RADIO_DEMO") or not site.startswith("https://") or "localhost" in site:
        return

    def loop():
        time.sleep(90)                                    # let the site start first
        while True:
            refresh(app)
            time.sleep(6 * 3600)

    threading.Thread(target=loop, name="station-directory", daemon=True).start()
