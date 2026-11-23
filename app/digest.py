"""The weekly message for members who asked for it ("what was trending this week").

Only members who ticked the box get it, every message carries a one-click way to stop, and at most DAILY_LIMIT are sent a day
(the free Brevo plan allows 300 a day; the rest of the room stays for sign-up and password messages). Each member is mailed
about once every 7 days. Members whose address is not confirmed are skipped.
"""
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

from .db import utcnow

DAILY_LIMIT = 250
EVERY_DAYS = 7


def set_optin(db, uid, on):
    row = db.one("SELECT token FROM digest_optin WHERE user_id = ?", (uid,))
    if on and not row:
        db.execute("INSERT INTO digest_optin (user_id, token, last_sent) VALUES (?, ?, NULL)", (uid, secrets.token_urlsafe(24)))
    elif not on and row:
        db.execute("DELETE FROM digest_optin WHERE user_id = ?", (uid,))
    db.commit()


def is_on(db, uid):
    return bool(db.one("SELECT 1 AS x FROM digest_optin WHERE user_id = ?", (uid,)))


def token_exists(db, token):
    return bool(token) and bool(db.one("SELECT 1 AS x FROM digest_optin WHERE token = ?", (token,)))


def stop_by_token(db, token):
    """True if a member was found and removed."""
    row = db.one("SELECT user_id FROM digest_optin WHERE token = ?", (token or "",))
    if not row:
        return False
    db.execute("DELETE FROM digest_optin WHERE user_id = ?", (row["user_id"],))
    db.commit()
    return True


def due(db, limit):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=EVERY_DAYS - 0.25)).replace(microsecond=0).isoformat()
    return db.all("SELECT d.user_id, d.token, u.email AS address, u.display_name FROM digest_optin d JOIN users u ON u.id = d.user_id "
                  "WHERE u.is_active = 1 AND u.email_verified = 1 AND (d.last_sent IS NULL OR d.last_sent < ?) "
                  "ORDER BY d.last_sent IS NOT NULL, d.last_sent LIMIT ?", (cutoff, limit))


def sent_today(db):
    return db.scalar("SELECT COUNT(*) FROM digest_optin WHERE last_sent LIKE ?", (utcnow()[:10] + "%",)) or 0


def build_body(name, site, trends, news, token):
    lines = [f"Hello {name}," if name else "Hello,", "", "Here is what people were following this week on Sur Music.", ""]
    if trends:
        lines.append("TRENDING NOW")
        lines += [f"- {t['term']}: {t['t']}" for t in trends[:8]]
        lines += ["", f"All trending topics: {site}/trending", ""]
    if news:
        lines.append("TODAY'S TOP HEADLINES")
        lines += [f"- {n['t']}" for n in news[:6]]
        lines += ["", f"More news: {site}/today", ""]
    lines += [f"Weather in your city: {site}/weather", f"Listen live, free: {site}", "",
              "You get this message because you asked for it in your Sur Music account.",
              f"To stop it with one click: {site}/unsubscribe/{token}"]
    return "\n".join(lines)


def send_due(db, send, site, trends, news, limit=DAILY_LIMIT, pause=1.0):
    """Send to the members who are due, within today's limit. Returns how many were sent. Stops if sending is not set up."""
    room = limit - sent_today(db)
    sent = 0
    for r in (due(db, room) if room > 0 else []):
        result = send(r["address"], "Sur Music: what was trending this week", build_body(r["display_name"], site, trends, news, r["token"]))
        if result == "pending_setup":
            break
        if result == "sent":
            db.execute("UPDATE digest_optin SET last_sent = ? WHERE user_id = ?", (utcnow(), r["user_id"]))
            db.commit()
            sent += 1
        if pause:
            time.sleep(pause)
    return sent


_THREAD = {"pid": None}


def start(app, collect):
    """Once an hour in this process (from about 5 a.m. UTC): send to the members who are due. collect() -> (trends, news)."""
    import os
    if app.config.get("TESTING") or app.config.get("RADIO_DEMO") or _THREAD["pid"] == os.getpid():
        return None
    _THREAD["pid"] = os.getpid()

    def run():
        from .db import Database
        from .mailer import send_mail, smtp_ready
        time.sleep(120)
        while True:
            try:
                with app.app_context():
                    if smtp_ready() and datetime.now(timezone.utc).hour >= 5:
                        trends, news = collect()
                        if trends or news:
                            db = Database(app.config["DATABASE_URL"])
                            try:
                                send_due(db, send_mail, app.config["SITE_URL"], trends, news)
                            finally:
                                db.close()
            except Exception:
                pass
            time.sleep(3600)
    t = threading.Thread(target=run, daemon=True, name="weekly-digest")
    t.start()
    return t
