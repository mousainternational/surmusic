"""Today's headlines by section (world, countries, business, sport ...), kept up to date by itself.

The text of public news feeds (headline and source name only, no outside links) is read every 30 minutes in the
background; visitors read the saved copy only (memory, then the database copy), so the page is always instant.
"""
import os
import threading
import time

from . import headlines

_TOP = "https://news.google.com/rss/headlines/section/topic/{}?hl=en-US&gl=US&ceid=US:en"
_COUNTRY = "https://news.google.com/rss?hl=en-{cc}&gl={cc}&ceid={cc}:en"
SECTIONS = [("World", _TOP.format("WORLD")), ("Pakistan", _COUNTRY.format(cc="PK")), ("India", _COUNTRY.format(cc="IN")),
            ("United States", _COUNTRY.format(cc="US")), ("United Kingdom", _COUNTRY.format(cc="GB")), ("Business", _TOP.format("BUSINESS")),
            ("Technology", _TOP.format("TECHNOLOGY")), ("Sports", _TOP.format("SPORTS")), ("Science", _TOP.format("SCIENCE")),
            ("Health", _TOP.format("HEALTH")), ("Entertainment", _TOP.format("ENTERTAINMENT"))]
TTL = 1800
_lock = threading.Lock()
_DATA = {"t": 0.0, "sections": {}}
_THREAD = {"pid": None}


def refresh_all(fetch=None, pause=0.5):
    """Reads every section once; a section that fails keeps its old headlines. Returns how many sections have headlines."""
    fetch = fetch or (lambda url: headlines._fetch(url, limit=8, strict=True))
    for name, url in SECTIONS:
        try:
            items = [{"t": x["t"], "s": x.get("s", "")} for x in fetch(url)][:8]
        except Exception:
            continue
        if len(items) >= 3:
            with _lock:
                _DATA["sections"][name] = items
                _DATA["t"] = time.time()
        if pause:
            time.sleep(pause)
    with _lock:
        return len(_DATA["sections"])


def get():
    with _lock:
        return {"t": _DATA["t"], "sections": dict(_DATA["sections"])}


def load_saved(data):
    if not isinstance(data, dict) or not isinstance(data.get("sections"), dict):
        return
    with _lock:
        if not _DATA["sections"]:
            _DATA["sections"] = {k: v for k, v in data["sections"].items() if isinstance(v, list) and v}
            _DATA["t"] = float(data.get("t") or 0)


def start(app, keep, peek):
    if app.config.get("TESTING") or app.config.get("RADIO_DEMO") or _THREAD["pid"] == os.getpid():
        return None
    _THREAD["pid"] = os.getpid()

    def run():
        time.sleep(25)
        while True:
            try:
                with app.app_context():
                    if not _DATA["sections"]:
                        load_saved(peek("keep:today"))
                    if refresh_all():
                        keep("keep:today", get())
            except Exception:
                pass
            time.sleep(TTL if _DATA["sections"] else 120)
    t = threading.Thread(target=run, daemon=True, name="today-news")
    t.start()
    return t
