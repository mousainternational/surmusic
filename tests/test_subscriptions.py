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
        return self.client.post("/api/app/status", json={"token": self.token or "x" * 30, "install": install or self.install,
                                                         "device": "OPPO A57", "os": "13"})


def status(buyer, install):
    buyer.install = install
    if buyer.token is None or install != buyer.login_install:
        buyer.login(install)
        buyer.login_install = install
    return buyer.status(install)


def set_trial_days(app, days):
    db = Database(app.config["DATABASE_URL"])
    db.execute("DELETE FROM settings WHERE key = 'app_trial_days'")
    db.execute("INSERT INTO settings (key, value) VALUES ('app_trial_days', ?)", (str(days),))
    db.commit(); db.close()


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
    set_trial_days(app, 0)                                                                   # no free trial in this flow
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
    set_trial_days(app, 0)
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


def test_admin_sees_which_phone_an_account_is_tied_to(app):
    buyer = paying_user(app)
    owner = app.test_client(); login(owner)
    post(owner, "/admin/subscriptions/grant", {"email": "buyer@example.com", "days": "30"}, page="/admin/subscriptions")
    assert status(buyer, PHONE_A).status_code == 200
    page = owner.get("/admin/subscriptions").get_data(as_text=True)
    assert "OPPO A57" in page and "Android 13" in page and "buyer@example.com" in page
    import hashlib
    assert hashlib.sha256(PHONE_A.encode()).hexdigest()[:8] in page          # only a short fingerprint is shown


# ---------------------------------------------------------------- free trial

def test_new_phone_gets_a_free_trial_then_must_pay(app):
    set_trial_days(app, 7)
    buyer = paying_user(app)
    first = status(buyer, PHONE_A)
    assert first.status_code == 200 and first.get_json()["reason"] == "trial" and first.get_json()["trial"] is True
    assert first.get_json()["until"]
    assert status(buyer, PHONE_A).get_json()["reason"] == "trial"                       # still running the next day

    db = Database(app.config["DATABASE_URL"])                                           # 8 days later the trial is over
    old = (datetime.now(timezone.utc) - timedelta(days=8)).replace(microsecond=0).isoformat()
    db.execute("UPDATE app_trials SET started_at = ?", (old,)); db.commit(); db.close()
    over = status(buyer, PHONE_A)
    assert over.status_code == 403 and over.get_json()["reason"] == "subscribe" and over.get_json()["trial"] is False


def test_reinstall_or_another_account_on_the_same_phone_does_not_restart_the_trial(app):
    set_trial_days(app, 7)
    buyer = paying_user(app)
    assert status(buyer, PHONE_A).status_code == 200
    db = Database(app.config["DATABASE_URL"])
    old = (datetime.now(timezone.utc) - timedelta(days=8)).replace(microsecond=0).isoformat()
    db.execute("UPDATE app_trials SET started_at = ?", (old,)); db.commit(); db.close()
    assert status(buyer, PHONE_A).status_code == 403
    # a brand-new account on the same phone (same phone ID) gets no second trial
    signup(app.test_client(), "second@example.com")
    again = Phone(app.test_client(), "second@example.com", install=PHONE_A)
    again.login()
    assert again.status().status_code == 403 and again.status().get_json()["reason"] == "subscribe"


def test_trial_days_are_set_by_the_owner_and_zero_means_no_trial(app):
    owner = app.test_client(); login(owner)
    assert "Free trial" in owner.get("/admin/subscriptions").get_data(as_text=True)
    assert post(owner, "/admin/subscriptions/trial", {"days": "3"}, page="/admin/subscriptions").status_code == 302
    buyer = paying_user(app)
    assert status(buyer, PHONE_A).get_json()["reason"] == "trial"
    db = Database(app.config["DATABASE_URL"])
    row = db.one("SELECT started_at FROM app_trials"); db.close()
    assert row["started_at"]
    assert post(owner, "/admin/subscriptions/trial", {"days": "999"}, page="/admin/subscriptions").status_code == 302   # refused, not saved
    assert post(owner, "/admin/subscriptions/trial", {"days": "0"}, page="/admin/subscriptions").status_code == 302
    other = Phone(app.test_client(), "x@example.com")
    signup(app.test_client(), "x@example.com"); other.login(install="phone-c-" + "3" * 16)
    assert other.status().status_code == 403                                             # trial off: pay first


def test_someone_who_already_paid_gets_no_new_trial(app):
    set_trial_days(app, 7)
    buyer = paying_user(app)
    db = Database(app.config["DATABASE_URL"])
    uid = db.one("SELECT id FROM users WHERE email = ?", ("buyer@example.com",))["id"]
    db.insert("app_subscriptions", {"user_id": uid, "status": "active", "method": "granted", "reference": "admin",
                                    "created_at": "2024-01-01T00:00:00+00:00", "expires_at": "2024-12-31T00:00:00+00:00"})
    db.commit(); db.close()
    r = status(buyer, PHONE_A)
    assert r.status_code == 403 and r.get_json()["reason"] == "subscribe"              # last year's customer must renew


def test_subscribe_page_shows_the_trial_end(app):
    set_trial_days(app, 7)
    buyer = paying_user(app)
    assert status(buyer, PHONE_A).status_code == 200
    html = buyer.web.get("/app/subscribe").get_data(as_text=True)
    assert "free trial is running" in html
