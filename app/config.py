"""Sur Music website configuration — every secret comes from environment variables, never from source files."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _bool(name, default=False):
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    ENV = os.environ.get("MISH_ENV", "production")
    SECRET_KEY = os.environ.get("SECRET_KEY", "")

    # Public URL used for canonical links, sitemap and social tags (no trailing slash).
    SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")

    # Database: sqlite:///path/to/file.db  or  postgresql://user:pass@host:5432/db
    DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'surmusic.db'}")

    # Private storage for uploaded software and images (never inside /static).
    # 1 on free hosting without a permanent disk (Render free): app files must be links, not uploads
    EPHEMERAL_STORAGE = os.environ.get("EPHEMERAL_STORAGE", "0") == "1"
    # Low-database mode (app/lowdb.py): keeps a free Neon database asleep. On by default on free hosting.
    LOW_DB_MODE = _bool("LOW_DB_MODE", EPHEMERAL_STORAGE)
    LOW_DB_FLUSH_SECONDS = _int("LOW_DB_FLUSH_SECONDS", 900)
    LOW_DB_IDLE_FLUSH_SECONDS = _int("LOW_DB_IDLE_FLUSH_SECONDS", 600)
    STORAGE_DIR = os.environ.get("STORAGE_DIR", str(BASE_DIR / "data" / "storage"))

    MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 200)
    MAX_IMAGE_MB = _int("MAX_IMAGE_MB", 5)
    MAX_CONTENT_LENGTH = (MAX_UPLOAD_MB + 10) * 1024 * 1024

    # Cookies
    SESSION_COOKIE_NAME = "surmusic_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", True)
    # "Remember me" sessions last this many days; others end when the browser closes.
    PERMANENT_SESSION_LIFETIME = _int("REMEMBER_DAYS", 30) * 86400
    ADMIN_SESSION_HOURS = _int("ADMIN_SESSION_HOURS", 8)

    # Radio Browser (open station directory) — fetched on the server and cached.
    RADIO_API_SERVERS = [s.strip() for s in os.environ.get(
        "RADIO_API_SERVERS", "de1,nl1,at1,fi1").split(",") if s.strip()]
    RADIO_CACHE_MINUTES = _int("RADIO_CACHE_MINUTES", 30)
    RADIO_TIMEOUT = _int("RADIO_TIMEOUT", 8)
    # Visitor location (see app/geo.py). GEOIP_DB is built with `flask --app wsgi import-geoip`.
    GEOIP_DB = os.environ.get("GEOIP_DB", str(BASE_DIR / "data" / "geoip.sqlite"))
    TRUST_CF_HEADERS = _bool("TRUST_CF_HEADERS", False)
    # City-level locations: the free DB-IP "IP to City Lite" .mmdb is downloaded automatically every month
    # (about 120 MB) unless GEOIP_AUTO=0. Licence CC BY 4.0, credited in the footer.
    GEOIP_MMDB = os.environ.get("GEOIP_MMDB", os.path.join(os.path.dirname(GEOIP_DB), "dbip-city-lite.mmdb"))
    GEOIP_AUTO = _bool("GEOIP_AUTO", True)
    GEOIP_URL = os.environ.get("GEOIP_URL", "https://download.db-ip.com/free/dbip-city-lite-{month}.mmdb.gz")
    PAGEVIEW_DAYS = _int("PAGEVIEW_DAYS", 180)
    EVENT_DAYS = _int("EVENT_DAYS", 365)
    # Development/testing only: serve built-in demo stations instead of calling Radio Browser.
    RADIO_DEMO = _bool("RADIO_DEMO", False)

    # Optional malware scanning through a ClamAV daemon (clamd).
    CLAMAV_HOST = os.environ.get("CLAMAV_HOST", "")
    CLAMAV_PORT = _int("CLAMAV_PORT", 3310)
    CLAMAV_REQUIRED = _bool("CLAMAV_REQUIRED", False)

    # Optional SMTP for contact-form email delivery.
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = _int("SMTP_PORT", 587)
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "")
    SMTP_TLS = _bool("SMTP_TLS", True)

    # Number of reverse proxies in front of the app (Caddy/Render = 1) for client IPs.
    TRUSTED_PROXIES = _int("TRUSTED_PROXIES", 1)

    TESTING = False
