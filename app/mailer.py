"""Email delivery (configured only with environment variables).

Two ways, first one wins:
* Brevo web API (BREVO_API_KEY): works on free hosting such as Render's free plan that blocks SMTP ports.
* Plain SMTP (SMTP_HOST + SMTP_FROM).
"""
import json
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage

from flask import current_app

from .util import valid_email


def smtp_ready():
    """True when this site can send e-mail (the name is kept from when SMTP was the only way)."""
    c = current_app.config
    return bool(c.get("BREVO_API_KEY") or (c.get("SMTP_HOST") and c.get("SMTP_FROM")))


def _send_brevo(c, to_address, subject, body, reply_to):
    """One transactional e-mail through Brevo's HTTPS API. Returns 'sent' or 'failed'; nothing secret is logged."""
    payload = {"sender": {"name": c.get("MAIL_FROM_NAME") or "Sur Music", "email": c.get("MAIL_FROM_EMAIL")},
               "to": [{"email": to_address}], "subject": subject[:200], "textContent": body}
    if reply_to and valid_email(reply_to):
        payload["replyTo"] = {"email": reply_to}
    req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=json.dumps(payload).encode("utf-8"),
                                 method="POST", headers={"api-key": c["BREVO_API_KEY"], "accept": "application/json",
                                                         "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 (fixed https host)
            return "sent" if 200 <= r.status < 300 else "failed"
    except urllib.error.HTTPError as exc:
        current_app.logger.warning("Email delivery failed (Brevo HTTP %s).", exc.code)
        return "failed"
    except (OSError, ValueError):
        current_app.logger.warning("Email delivery failed (Brevo unreachable).")
        return "failed"


def send_mail(to_address, subject, body, reply_to=None):
    """Return 'sent', 'pending_setup' or 'failed'. Never raises to the visitor."""
    if not smtp_ready() or not valid_email(to_address or ""):
        return "pending_setup"
    c = current_app.config
    msg = EmailMessage()
    msg["From"] = c["SMTP_FROM"] if c.get("SMTP_FROM") else f"{c.get('MAIL_FROM_NAME')} <{c.get('MAIL_FROM_EMAIL')}>"
    msg["To"] = to_address
    if reply_to:
        msg["Reply-To"] = reply_to
    msg["Subject"] = subject[:200]
    msg.set_content(body)
    if current_app.config.get("TESTING"):
        current_app.config.setdefault("SENT_MAIL", []).append(msg)
        return "sent"
    if c.get("BREVO_API_KEY"):
        from .settings import get_settings
        return _send_brevo(c, to_address, subject, body, reply_to or get_settings().get("app_contact_email"))
    try:
        if c["SMTP_PORT"] == 465:
            server = smtplib.SMTP_SSL(c["SMTP_HOST"], 465, context=ssl.create_default_context(), timeout=20)
        else:
            server = smtplib.SMTP(c["SMTP_HOST"], c["SMTP_PORT"], timeout=20)
            if c["SMTP_TLS"]:
                server.starttls(context=ssl.create_default_context())
        with server:
            if c["SMTP_USER"]:
                server.login(c["SMTP_USER"], c["SMTP_PASSWORD"])
            server.send_message(msg)
        return "sent"
    except (OSError, smtplib.SMTPException):
        current_app.logger.warning("Email delivery failed (SMTP error).")
        return "failed"
