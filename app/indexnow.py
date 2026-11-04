"""IndexNow: tells Bing, Yahoo, Yandex and others about our key pages once after each new version.

(Google does not use IndexNow — for Google use Search Console and the sitemap.)
The key is public by design: IndexNow checks that https://<site>/<key>.txt shows the same key.
"""
import hashlib
import json
import logging
import threading
import urllib.request

from .db import Database, utcnow

log = logging.getLogger(__name__)
KEY_PAGES = ["/", "/genre/naat", "/genre/quran", "/genre/qawwali", "/genre/islamic", "/genre/sufi", "/genre/ghazal",
             "/country/pakistan", "/country/india", "/country/saudi-arabia", "/radio-stations", "/download",
             "/trending", "/live-news", "/blog"]


def key_for(secret):
    return hashlib.sha256(("indexnow:" + secret).encode()).hexdigest()[:32]


def _marker(version):
    a, b, c = (version.split(".") + ["0", "0"])[:3]
    return 1_000_000 + int(a) * 10000 + int(b) * 100 + int(c)


def _run(app):
    site = app.config["SITE_URL"]
    marker = _marker(app.config.get("APP_VERSION", "0.0.0"))
    db = Database(app.config["DATABASE_URL"])
    try:
        if db.scalar("SELECT COUNT(*) FROM schema_migrations WHERE version = ?", (marker,)):
            return
        db.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (marker, utcnow()))
        db.commit()
    finally:
        db.close()
    host = site.split("://", 1)[-1]
    key = key_for(app.config["SECRET_KEY"])
    body = json.dumps({"host": host, "key": key, "keyLocation": f"{site}/{key}.txt",
                       "urlList": [site + p for p in KEY_PAGES]}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            log.info("IndexNow sent %d pages, answer %s", len(KEY_PAGES), r.status)
    except Exception as exc:  # never break the site for this
        log.info("IndexNow not sent: %s", exc)


def start(app):
    """Background, once per new version, only on the real https site."""
    site = app.config["SITE_URL"]
    if app.config.get("TESTING") or not site.startswith("https://") or "localhost" in site:
        return
    threading.Thread(target=_run, args=(app,), daemon=True).start()
