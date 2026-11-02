"""E-mail through Brevo's web API (the free host blocks SMTP ports)."""
import io
import json
import urllib.error

from conftest import USER_PASSWORD, post, signup
from app import mailer


class FakeReply(io.BytesIO):
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_brevo_request_is_correct_and_key_is_only_a_header(app, monkeypatch):
    app.config.update(BREVO_API_KEY="xkeysib-test-key", MAIL_FROM_EMAIL="noreply@surmusicradio.com", MAIL_FROM_NAME="Sur Music")
    seen = {}

    def fake_urlopen(req, timeout=0):
        seen.update(url=req.full_url, headers={k.lower(): v for k, v in req.header_items()}, body=json.loads(req.data))
        return FakeReply(b"{}")
    monkeypatch.setattr(mailer.urllib.request, "urlopen", fake_urlopen)
    with app.app_context():
        assert mailer._send_brevo(app.config, "customer@example.com", "Hello", "Body text", "mousainternational@gmail.com") == "sent"
    assert seen["url"] == "https://api.brevo.com/v3/smtp/email"
    assert seen["headers"]["api-key"] == "xkeysib-test-key" and seen["headers"]["content-type"] == "application/json"
    b = seen["body"]
    assert b["sender"] == {"name": "Sur Music", "email": "noreply@surmusicradio.com"}
    assert b["to"] == [{"email": "customer@example.com"}] and b["replyTo"] == {"email": "mousainternational@gmail.com"}
    assert b["subject"] == "Hello" and b["textContent"] == "Body text" and "xkeysib" not in json.dumps(b)


def test_brevo_errors_never_raise_and_never_log_the_key(app, monkeypatch, caplog):
    app.config.update(BREVO_API_KEY="xkeysib-secret-value")

    def boom(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)
    monkeypatch.setattr(mailer.urllib.request, "urlopen", boom)
    with app.app_context():
        assert mailer._send_brevo(app.config, "a@example.com", "s", "b", None) == "failed"
        monkeypatch.setattr(mailer.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
        assert mailer._send_brevo(app.config, "a@example.com", "s", "b", None) == "failed"
    assert "xkeysib-secret-value" not in caplog.text and "a@example.com" not in caplog.text


def test_forgot_password_sends_a_reset_email_when_brevo_is_set(app):
    app.config.update(BREVO_API_KEY="xkeysib-test-key")
    member = app.test_client()
    signup(member, "forgetful@example.com")
    visitor = app.test_client()
    r = post(visitor, "/forgot", {"email": "forgetful@example.com"}, page="/forgot", follow_redirects=True)
    assert b"we sent a reset link" in r.data.lower()
    sent = [m for m in app.config.get("SENT_MAIL", []) if m["To"] == "forgetful@example.com"]
    assert sent and "/reset/" in sent[-1].get_content() and "Sur Music" in sent[-1]["From"]
    assert "Reset your" in sent[-1]["Subject"]
    # an unknown address gets the same answer and no e-mail
    before = len(app.config["SENT_MAIL"])
    r = post(visitor, "/forgot", {"email": "nobody@example.com"}, page="/forgot", follow_redirects=True)
    assert b"we sent a reset link" in r.data.lower() and len(app.config["SENT_MAIL"]) == before


def test_without_a_key_the_site_says_how_to_get_help(app):
    app.config.update(BREVO_API_KEY="", SMTP_HOST="", SMTP_FROM="")
    r = post(app.test_client(), "/forgot", {"email": "x@example.com"}, page="/forgot", follow_redirects=True)
    assert b"not switched on yet" in r.data and b"mousainternational@gmail.com" in r.data
