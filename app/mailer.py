"""Email delivery through SMTP (configured only with environment variables)."""
import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app

from .util import valid_email


def smtp_ready():
    c = current_app.config
    return bool(c.get("SMTP_HOST") and c.get("SMTP_FROM"))


def send_mail(to_address, subject, body, reply_to=None):
    """Return 'sent', 'pending_setup' or 'failed'. Never raises to the visitor."""
    if not smtp_ready() or not valid_email(to_address or ""):
        return "pending_setup"
    c = current_app.config
    msg = EmailMessage()
    msg["From"] = c["SMTP_FROM"]
    msg["To"] = to_address
    if reply_to:
        msg["Reply-To"] = reply_to
    msg["Subject"] = subject[:200]
    msg.set_content(body)
    if current_app.config.get("TESTING"):
        current_app.config.setdefault("SENT_MAIL", []).append(msg)
        return "sent"
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
