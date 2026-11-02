import re

from conftest import ADMIN_EMAIL, STATION, USER_PASSWORD, api, login, post, signup


def test_signup_validation(client):
    r = post(client, "/signup", {"email": "bad", "password": "short", "password2": "short"}, page="/signup")
    assert r.status_code == 400
    html = r.get_data(as_text=True)
    assert "valid email" in html and "at least 10 characters" in html and "accept the Terms" in html
    r = post(client, "/signup", {"email": "a@example.com", "password": "pakistan123", "password2": "pakistan123",
                                 "agree": "1"}, page="/signup")
    assert b"too easy to guess" in r.data
    r = post(client, "/signup", {"email": "a@example.com", "password": USER_PASSWORD, "password2": "different-one-1",
                                 "agree": "1"}, page="/signup")
    assert b"do not match" in r.data


def test_signup_logs_in_and_duplicate_rejected(client, app):
    r = signup(client)
    assert r.status_code == 302
    assert client.get("/account").status_code == 200
    assert client.get("/api/me").get_json()["user"]["name"] == "Sara"
    other = app.test_client()
    r = signup(other)
    assert r.status_code == 400 and b"already exists" in r.data


def test_login_logout_and_errors(client, app):
    signup(app.test_client())
    r = login(client, "sara@example.com", "wrong-password-here")
    assert r.status_code == 401 and b"Incorrect email or password" in r.data
    r = login(client, "sara@example.com", USER_PASSWORD)
    assert r.status_code == 302
    assert client.get("/account").status_code == 200
    post(client, "/logout", page="/account")
    assert client.get("/account").status_code == 302


def test_lockout(client, app):
    signup(app.test_client())
    for _ in range(5):
        login(client, "sara@example.com", "wrong-password-here")
    r = login(client, "sara@example.com", USER_PASSWORD)
    assert b"temporarily locked" in r.data


def test_login_rate_limit(client, app):
    app.config["RATE_LIMITS_DISABLED"] = False
    for _ in range(20):
        login(client, "nobody@example.com", "x")
    assert b"Too many sign-in attempts" in login(client).data


def test_remember_me_session(client, app):
    signup(app.test_client())
    login(client, "sara@example.com", USER_PASSWORD, remember=True)
    cookie = client.get_cookie("surmusic_session")
    assert cookie is not None and cookie.expires is not None
    c2 = app.test_client()
    login(c2, "sara@example.com", USER_PASSWORD)
    assert c2.get_cookie("surmusic_session").expires is None  # browser-session cookie


def test_password_reset_flow(client, app):
    signup(app.test_client())
    # without SMTP the site is honest about it
    r = post(client, "/forgot", {"email": "sara@example.com"}, page="/forgot", follow_redirects=True)
    assert b"not switched on yet" in r.data
    app.config.update(SMTP_HOST="smtp.example.com", SMTP_FROM="noreply@surmusic.example", SENT_MAIL=[])
    r = post(client, "/forgot", {"email": "nobody@example.com"}, page="/forgot", follow_redirects=True)
    assert b"If an account exists" in r.data and app.config["SENT_MAIL"] == []
    post(client, "/forgot", {"email": "sara@example.com"}, page="/forgot")
    mail = app.config["SENT_MAIL"][-1]
    link = re.search(r"https://surmusic\.example(/reset/\S+)", mail.get_content()).group(1)
    r = post(client, link, {"password": "a-brand-new-password", "password2": "a-brand-new-password"}, page=link)
    assert r.status_code == 302
    assert login(client, "sara@example.com", USER_PASSWORD).status_code == 401
    assert login(app.test_client(), "sara@example.com", "a-brand-new-password").status_code == 302
    r = client.get(link, follow_redirects=True)  # single use
    assert b"already used" in r.data


def test_email_verification_required(client, app):
    app.config.update(SMTP_HOST="smtp.example.com", SMTP_FROM="noreply@surmusic.example", SENT_MAIL=[])
    login(client)
    post(client, "/admin/settings?section=accounts", {"signup_enabled": "1", "require_email_verification": "1"},
         page="/admin/settings")
    post(client, "/logout", page="/")
    u = app.test_client()
    r = signup(u)
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert login(u, "sara@example.com", USER_PASSWORD).status_code == 401
    link = re.search(r"https://surmusic\.example(/verify/\S+)", app.config["SENT_MAIL"][-1].get_content()).group(1)
    u.get(link)
    assert login(u, "sara@example.com", USER_PASSWORD).status_code == 302


def test_change_password_signs_out_other_devices(client, app):
    signup(client)
    other = app.test_client()
    login(other, "sara@example.com", USER_PASSWORD)
    post(client, "/account", {"action": "password", "current": USER_PASSWORD, "new": "new-strong-pass-9",
                              "again": "new-strong-pass-9"}, page="/account")
    assert client.get("/account").status_code == 200
    assert other.get("/account").status_code == 302


def test_delete_account_and_export(client):
    signup(client)
    api(client, "POST", "/api/favorites", {"station": STATION})
    data = client.get("/account/export").get_json()
    assert data["account"]["email"] == "sara@example.com" and data["favorites"][0]["name"] == "Lahore Sur FM"
    r = post(client, "/account/delete", {"password": "wrong-pass-123"}, page="/account", follow_redirects=True)
    assert b"was not deleted" in r.data
    r = post(client, "/account/delete", {"password": USER_PASSWORD}, page="/account", follow_redirects=True)
    assert b"were deleted" in r.data
    assert login(client, "sara@example.com", USER_PASSWORD).status_code == 401


def test_favorites_api(client, app):
    anon = app.test_client()
    assert api(anon, "POST", "/api/favorites", {"station": STATION}).status_code == 401
    signup(client)
    r = api(client, "POST", "/api/favorites", {"station": STATION})
    assert r.status_code == 200 and r.get_json()["favorites"][0]["uuid"] == "abc-123"
    assert api(client, "POST", "/api/favorites", {"station": dict(STATION, url="javascript:alert(1)")}).status_code == 400
    assert client.get("/api/me").get_json()["favorites"] == ["abc-123"]
    assert b"Lahore Sur FM" in client.get("/favorites").data
    assert api(client, "DELETE", "/api/favorites/abc-123").status_code == 200
    assert client.get("/api/me").get_json()["favorites"] == []
    r = api(client, "POST", "/api/favorites/import", {"stations": [STATION, dict(STATION, uuid="z", url="http://x")]})
    assert r.get_json()["added"] == 1
    assert client.post("/api/favorites", json={"station": STATION}).status_code == 403  # CSRF


def test_history_recorded_for_members(client):
    signup(client)
    api(client, "POST", "/api/play", {"station": STATION, "category": "lollywood"})
    assert b"Recently played" in client.get("/account").data


def test_admin_area_requires_admin(client, app):
    assert client.get("/admin/").status_code == 302
    signup(client)
    assert client.get("/admin/").status_code == 403
    assert client.get("/admin/users").status_code == 403
    a = app.test_client()
    login(a)
    for p in ["/admin/", "/admin/users", "/admin/ads", "/admin/stations", "/admin/apps", "/admin/donations",
              "/admin/messages", "/admin/settings", "/admin/settings?section=seo", "/admin/backup", "/admin/audit"]:
        r = a.get(p)
        assert r.status_code == 200, p
        assert r.headers["X-Robots-Tag"] == "noindex, nofollow"


def test_admin_suspend_user(client, app):
    signup(client)
    a = app.test_client()
    login(a)
    post(a, "/admin/users/2/suspend", page="/admin/users")
    assert client.get("/account").status_code == 302  # signed out immediately
    assert b"suspended" in login(client, "sara@example.com", USER_PASSWORD).data
    post(a, "/admin/users/1/delete", page="/admin/users")
    assert login(app.test_client(), ADMIN_EMAIL, "correct-horse-battery-staple").status_code == 302
