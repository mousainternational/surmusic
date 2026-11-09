"""2-step sign-in (authenticator app codes)."""
import base64
import re
import time

from conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login, post

from app import twofa


def test_rfc6238_reference_code():
    """RFC 6238 test vector (SHA-1): secret '12345678901234567890', time 59 s → 94287082 → last 6 digits."""
    secret = base64.b32encode(b"12345678901234567890").decode()
    assert twofa.code_at(secret, 59 // 30) == "287082"
    assert twofa.code_at(secret, 1111111109 // 30) == "081804"
    assert twofa.check_code(secret, "287 082", 0, now=59) == 1
    assert twofa.check_code(secret, "287082", 1, now=59) is None          # same step never accepted twice
    assert twofa.check_code(secret, "000000", 0, now=59) is None


def _secret_from(html):
    return re.search(r"Key: <code[^>]*>([A-Z2-7 ]+)</code>", html).group(1).replace(" ", "")


def _code(secret, offset=0):
    return twofa.code_at(secret, twofa.current_step() + offset)


def test_turn_on_sign_in_with_code_recovery_and_reset(client, app):
    login(client)
    acct = client.get("/account").get_data(as_text=True)
    assert "Turn on 2-step sign-in" in acct
    assert "Protect the admin panel" in client.get("/admin/").get_data(as_text=True)
    post(client, "/account/two-step", {"action": "start"}, page="/account/two-step")
    page = client.get("/account/two-step").get_data(as_text=True)
    assert 'id="qr"' in page and "otpauth://totp/Sur%20Music" in page and "js/vendor/qrcode.js" in page
    secret = _secret_from(page)
    r = post(client, "/account/two-step", {"action": "confirm", "code": "000000"}, page="/account/two-step",
             follow_redirects=True)
    assert b"That code is not right" in r.data
    r = post(client, "/account/two-step", {"action": "confirm", "code": _code(secret)}, page="/account/two-step")
    html = r.get_data(as_text=True)
    block = re.search(r'<pre class="recovery" id="recovery-codes">(.*?)</pre>', html, re.S).group(1)
    codes = re.findall(r"\b[a-z2-9]{5}-[a-z2-9]{5}\b", block)
    assert len(codes) == 10 and "shown <strong>only now</strong>" in html
    assert "Protect the admin panel" not in client.get("/admin/").get_data(as_text=True)
    # the stored secret is encrypted
    from app.db import Database
    db = Database(app.config["DATABASE_URL"])
    assert secret not in str(db.one("SELECT secret FROM user_2fa")["secret"])
    db.close()

    # new device: password alone is not enough
    other = app.test_client()
    r = login(other)
    assert r.status_code == 302 and r.headers["Location"].endswith("/login/code")
    assert other.get("/admin/").status_code in (302, 403)
    r = post(other, "/login/code", {"code": "123456"}, page="/login/code")
    assert r.status_code == 401 and b"not right" in r.data
    time.sleep(0)  # (codes from the same step were used during setup; use the next step)
    r = post(other, "/login/code", {"code": _code(secret, 1)}, page="/login/code")
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/")
    assert other.get("/admin/").status_code == 200

    # recovery code works once
    third = app.test_client()
    login(third)
    r = post(third, "/login/code", {"code": codes[0].upper()}, page="/login/code")
    assert r.status_code == 302
    fourth = app.test_client()
    login(fourth)
    assert post(fourth, "/login/code", {"code": codes[0]}, page="/login/code").status_code == 401

    # an administrator can switch it off for an account (e.g. lost phone)
    uid = re.search(r'/admin/users/(\d+)/reset_2fa', client.get("/admin/users").get_data(as_text=True)).group(1)
    post(client, f"/admin/users/{uid}/reset_2fa", page="/admin/users")
    fifth = app.test_client()
    r = login(fifth)
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/")


def test_code_step_expires_and_needs_password_first(client, app):
    assert client.get("/login/code").status_code == 302           # no password yet → back to sign-in
    r = post(client, "/login/code", {"code": "123456"}, page="/login")
    assert r.status_code in (302, 400)


def _turn_on(client):
    login(client)
    post(client, "/account/two-step", {"action": "start"}, page="/account/two-step")
    secret = _secret_from(client.get("/account/two-step").get_data(as_text=True))
    post(client, "/account/two-step", {"action": "confirm", "code": _code(secret)}, page="/account/two-step")
    return secret


def test_password_change_needs_the_authenticator_code_when_two_step_is_on(client, app):
    secret = _turn_on(client)
    new = "a-brand-new-password-77"
    form = {"action": "password", "current": ADMIN_PASSWORD, "new": new, "again": new}
    assert 'name="code"' in client.get("/account").get_data(as_text=True)
    r = post(client, "/account", dict(form, code="000000"), page="/account", follow_redirects=True)
    assert b"authenticator app is not correct" in r.data
    r = post(client, "/account", dict(form, code=_code(secret, 1)), page="/account", follow_redirects=True)
    assert b"Password changed" in r.data
    with app.app_context():
        mails = app.config.get("SENT_MAIL", [])
    assert any("Your password was changed" in m["Subject"] for m in mails) or not mails  # email when set up


def test_reset_link_alone_is_not_enough_when_two_step_is_on(client, app):
    secret = _turn_on(client)
    from app.auth import _pw_fingerprint, _signer
    from app.db import Database
    db = Database(app.config["DATABASE_URL"])
    row = db.one("SELECT * FROM users WHERE email = ?", (ADMIN_EMAIL,))
    db.close()
    with app.app_context():
        token = _signer("reset").dumps({"uid": row["id"], "fp": _pw_fingerprint(row["password_hash"])})
    page = client.get(f"/reset/{token}").get_data(as_text=True)
    assert 'name="code"' in page
    new = "reset-by-email-only-123"
    r = post(client, f"/reset/{token}", {"password": new, "password2": new, "code": "000000"}, page=f"/reset/{token}")
    assert r.status_code == 400 and b"authenticator app is not correct" in r.data
    r = post(client, f"/reset/{token}", {"password": new, "password2": new, "code": _code(secret, 1)},
             page=f"/reset/{token}")
    assert r.status_code in (302, 303)
