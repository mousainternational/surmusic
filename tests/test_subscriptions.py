"""App subscription: pay -> owner approves -> one phone per account."""
from datetime import datetime, timedelta, timezone

from conftest import USER_PASSWORD, login, post, signup
from app.db import Database

PHONE_A, PHONE_B = "phone-a-" + "1" * 16, "phone-b-" + "2" * 16


class Phone:
    """The Android app: signs in with e-mail + password, then asks with its token (no browser cookies)."""
    def __init__(self, client, email, password=USER_PASSWORD, install=PHONE_A):
        self.client, self.email, self.password, self.install, self.token = client, email, password, install, None

    def login(self, install=None):
        self.install = install or self.install
        r = self.client.post("/api/app/login", json={"email": self.email, "password": self.password, "install": self.install})
        if r.status_code == 200:
            self.token = r.get_json()["token"]
        return r

    def status(self, install=None):
        return self.client.post("/api/app/status", json={"token": self.token or "x" * 30, "install": install or self.install})


def status(buyer, install):
    buyer.install = install
    if buyer.token is None or install != buyer.login_install:
        buyer.login(install)
        buyer.login_install = install
    return buyer.status(install)


def paying_user(app):
    web = app.test_client()                      # the person's browser on the website
    signup(web, "buyer@example.com")
    p = Phone(app.test_client(), "buyer@example.com")
    p.web, p.login_install = web, None
    return p


def test_login_rules(client, app):
    signup(app.test_client(), "buyer@example.com")
    ok = lambda **kw: client.post("/api/app/login", json=dict({"email": "buyer@example.com", "password": USER_PASSWORD, "install": PHONE_A}, **kw))
    assert ok().status_code == 200 and ok().get_json()["token"]
    assert ok(password="wrong-password-123").get_json()["reason"] == "wrong"
    assert client.post("/api/app/login", data={"email": "buyer@example.com", "password": USER_PASSWORD, "install": PHONE_A}).status_code == 400
    assert client.post("/api/app/status", json={"token": "x" * 30, "install": PHONE_A}).status_code == 401
    assert client.post("/api/app/status", data={"token": "x" * 30, "install": PHONE_A}).status_code == 400   # a web form cannot ask


def test_token_is_useless_on_another_phone(app):
    p = paying_user(app); p.login()
    stolen = app.test_client().post("/api/app/status", json={"token": p.token, "install": PHONE_B})
    assert stolen.status_code == 401


def test_not_subscribed_then_approved_then_one_phone(app):
    buyer = paying_user(app)
    r = status(buyer, PHONE_A)
    assert r.status_code == 403 and r.get_json()["reason"] == "subscribe"

    # pay -> request (no payment methods are set up in the test site, so insert the request the way the form does)
    db = Database(app.config["DATABASE_URL"])
    uid = db.one("SELECT id FROM users WHERE email = ?", ("buyer@example.com",))["id"]
    sid = db.insert("app_subscriptions", {"user_id": uid, "status": "pending", "method": "jazzcash", "reference": "TX12345",
                                          "created_at": "2026-11-02T10:00:00+00:00"})
    db.commit(); db.close()
    assert status(buyer, PHONE_A).status_code == 403                                         # pending is not active

    owner = app.test_client(); login(owner)
    page = owner.get("/admin/subscriptions").get_data(as_text=True)
    assert "buyer@example.com" in page and "TX12345" in page
    assert post(owner, f"/admin/subscriptions/{sid}/approve", page="/admin/subscriptions").status_code == 302

    ok = status(buyer, PHONE_A)
    assert ok.status_code == 200 and ok.get_json()["ok"] and ok.get_json()["until"]
    assert status(buyer, PHONE_A).status_code == 200                                         # same phone again
    other = status(buyer, PHONE_B)                                                           # an APK shared to another phone
    assert other.status_code == 403 and other.get_json()["reason"] == "other_device"

    db = Database(app.config["DATABASE_URL"])                                                # silent for 8 days: it may move
    old = (datetime.now(timezone.utc) - timedelta(days=8)).replace(microsecond=0).isoformat()
    db.execute("UPDATE app_devices SET last_seen = ?", (old,)); db.commit(); db.close()
    assert status(buyer, PHONE_B).status_code == 200 and status(buyer, PHONE_A).status_code == 403

    assert post(owner, "/admin/subscriptions/reset-device", {"user_id": str(uid)}, page="/admin/subscriptions").status_code == 302
    assert status(buyer, PHONE_A).status_code == 200                                         # released: first phone in wins

    assert post(owner, f"/admin/subscriptions/{sid}/revoke", page="/admin/subscriptions").status_code == 302
    assert status(buyer, PHONE_A).get_json()["reason"] == "subscribe"


def test_expired_subscription_is_refused(app):
    buyer = paying_user(app)
    db = Database(app.config["DATABASE_URL"])
    uid = db.one("SELECT id FROM users WHERE email = ?", ("buyer@example.com",))["id"]
    db.insert("app_subscriptions", {"user_id": uid, "status": "active", "method": "granted", "reference": "admin",
                                    "created_at": "2025-01-01T00:00:00+00:00", "expires_at": "2025-12-31T00:00:00+00:00"})
    db.commit(); db.close()
    assert status(buyer, PHONE_A).get_json()["reason"] == "subscribe"


def test_admin_can_grant_and_admin_uses_app_free(app):
    buyer = paying_user(app)
    owner = app.test_client(); login(owner)
    boss = Phone(app.test_client(), "owner@example.com", password="correct-horse-battery-staple")
    assert boss.login().status_code == 200 and boss.status().status_code == 200               # the owner is never locked out
    assert post(owner, "/admin/subscriptions/grant", {"email": "buyer@example.com", "days": "30"},
                page="/admin/subscriptions").status_code == 302
    assert status(buyer, PHONE_A).status_code == 200


def test_subscribe_page_needs_login_and_is_private(client, app):
    r = client.get("/app/subscribe")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    buyer = paying_user(app)
    html = buyer.web.get("/app/subscribe").get_data(as_text=True)
    assert "$5 per year" in html and "noindex" in html
    assert "/app/subscribe" not in client.get("/sitemap.xml").get_data(as_text=True)


def test_regular_user_cannot_open_admin_subscriptions(app):
    buyer = paying_user(app)
    assert buyer.web.get("/admin/subscriptions").status_code == 403
    assert buyer.web.post("/admin/subscriptions/1/approve").status_code in (400, 403)
