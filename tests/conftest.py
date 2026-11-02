import io
import re
import zipfile

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.db import Database, utcnow

ADMIN_EMAIL = "owner@example.com"
ADMIN_PASSWORD = "correct-horse-battery-staple"
USER_PASSWORD = "listen-to-ghazals-42"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-that-is-long-enough-0123456789")
    app = create_app({
        "TESTING": True,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
        "STORAGE_DIR": str(tmp_path / "storage"),
        "SITE_URL": "https://surmusic.example",
        "SESSION_COOKIE_SECURE": False,
        "RATE_LIMITS_DISABLED": True,
        "TRUSTED_PROXIES": 0,
        "RADIO_DEMO": True,
        "MAX_UPLOAD_MB": 2,
        "SMTP_HOST": "", "SMTP_FROM": "",
    })
    db = Database(app.config["DATABASE_URL"])
    db.insert("users", {"email": ADMIN_EMAIL, "password_hash": generate_password_hash(ADMIN_PASSWORD, method="scrypt"),
                        "display_name": "Owner", "role": "admin", "is_active": 1, "email_verified": 1,
                        "created_at": utcnow()})
    db.commit()
    db.close()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def csrf(client, path="/login"):
    html = client.get(path).get_data(as_text=True)
    m = re.search(r'name="csrf-token" content="([^"]+)"', html)
    return m.group(1) if m else None


def post(client, path, data=None, page="/login", **kw):
    data = dict(data or {})
    data.setdefault("_csrf", csrf(client, page))
    return client.post(path, data=data, **kw)


def api(client, method, path, json_body=None, page="/", headers=None, environ_base=None):
    token = csrf(client, page)
    extra = {"environ_base": environ_base} if environ_base else {}
    return client.open(path, method=method, json=json_body, headers=dict(headers or {}, **{"X-CSRF-Token": token}),
                       **extra)


def login(client, email=ADMIN_EMAIL, password=ADMIN_PASSWORD, remember=False):
    data = {"email": email, "password": password}
    if remember:
        data["remember"] = "1"
    return post(client, "/login", data)


def signup(client, email="sara@example.com", password=USER_PASSWORD, name="Sara"):
    return post(client, "/signup", {"email": email, "password": password, "password2": password,
                                     "display_name": name, "agree": "1"}, page="/signup")


def apk_bytes():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("AndroidManifest.xml", "<manifest/>")
    return buf.getvalue()


def png_bytes(size=(64, 64)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, (255, 61, 134)).save(buf, "PNG")
    return buf.getvalue()


STATION = {"uuid": "abc-123", "name": "Lahore Sur FM", "url": "https://stream.example.com/lahore",
           "favicon": "https://example.com/logo.png", "country": "Pakistan", "tags": "urdu, pop", "bitrate": 128}
