"""Paid Sur Music app, sold directly: one account, one year, one phone.

How it works
* The person signs in (the same account as the website) and pays by JazzCash / NayaPay / Wise to the verified
  details set in Admin -> Donations, then sends the transaction ID on /app/subscribe.
* The owner checks the payment in the real payment app and presses Approve (Admin -> App subscriptions).
* The app asks /api/app/status with the sign-in cookie: active subscription + the phone it is bound to.
  A second phone is refused (it may take over after 7 idle days), so sharing the APK does nothing.
Nothing here stores a card, PIN, password or OTP. Only hashes of phone IDs are kept.
"""
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for

from .db import get_db, utcnow
from .security import admin_required, audit, current_user, login_required, rate_limited
from .seo import build_meta
from .settings import donation_method
from .util import valid_email

bp = Blueprint("subs", __name__)

PRICE_TEXT = "$5 per year"
PERIOD_DAYS = 365
IDLE_DAYS = 7                      # a second phone may take over after this many silent days
METHODS = (("jazzcash", "JazzCash"), ("nayapay", "NayaPay"), ("wise", "Wise (international)"))


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.replace(microsecond=0).isoformat()


def active_until(db, uid):
    """Latest expiry of this account's approved subscriptions, or None when there is no live one."""
    row = db.one("SELECT MAX(expires_at) AS e FROM app_subscriptions WHERE user_id = ? AND status = 'active'", (uid,))
    e = row["e"] if row else None
    if not e:
        return None
    try:
        return e if datetime.fromisoformat(e) > _now() else None
    except ValueError:
        return None


def license_state(db, user, install):
    """(ok, reason, expires) for this account on this phone. Admins use the app free."""
    if user["role"] == "admin":
        until = _iso(_now() + timedelta(days=30))
    else:
        until = active_until(db, user["id"])
        if not until:
            return False, "subscribe", None
    ih = hashlib.sha256(install.encode()).hexdigest()
    now = _now()
    row = db.one("SELECT install_hash, last_seen FROM app_devices WHERE user_id = ?", (user["id"],))
    if row is None:
        db.execute("INSERT INTO app_devices (user_id, install_hash, first_seen, last_seen) VALUES (?, ?, ?, ?)",
                   (user["id"], ih, _iso(now), _iso(now)))
    elif row["install_hash"] == ih:
        db.execute("UPDATE app_devices SET last_seen = ? WHERE user_id = ?", (_iso(now), user["id"]))
    else:
        try:
            idle = now - datetime.fromisoformat(row["last_seen"])
        except ValueError:
            idle = timedelta(days=999)
        if idle < timedelta(days=IDLE_DAYS):
            return False, "other_device", until
        db.execute("UPDATE app_devices SET install_hash = ?, last_seen = ? WHERE user_id = ?",
                   (ih, _iso(now), user["id"]))
    db.commit()
    return True, "ok", until


def _json():
    """JSON body, only when sent as JSON (a web form on another site cannot do that)."""
    data = request.get_json(silent=True) if request.is_json else None
    return data if isinstance(data, dict) else {}


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _install_ok(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9-]{16,80}", value) is not None


@bp.route("/api/app/login", methods=["POST"])
def api_login():
    """The app signs in with e-mail + password and receives a token that works only on this phone."""
    from werkzeug.security import check_password_hash
    from . import twofa
    from .auth import LOCK_AFTER, LOCK_MINUTES, verification_required
    data = _json()
    email = (data.get("email") or "").strip().lower() if isinstance(data.get("email"), str) else ""
    password, install = data.get("password"), data.get("install")
    if not (valid_email(email) and isinstance(password, str) and 1 <= len(password) <= 200 and _install_ok(install)):
        return jsonify({"ok": False, "reason": "bad_request"}), 400
    if rate_limited("applogin", 20, 900):
        return jsonify({"ok": False, "reason": "slow_down"}), 429
    db, now = get_db(), _now()
    row = db.one("SELECT * FROM users WHERE email = ?", (email,))
    if row and row["locked_until"] and datetime.fromisoformat(row["locked_until"]) > now:
        return jsonify({"ok": False, "reason": "locked"}), 429
    if not (row and check_password_hash(row["password_hash"], password)):
        if row:
            fails = row["failed_attempts"] + 1
            lock = _iso(now + timedelta(minutes=LOCK_MINUTES)) if fails >= LOCK_AFTER else None
            db.execute("UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                       (0 if lock else fails, lock, row["id"]))
            db.commit()
        return jsonify({"ok": False, "reason": "wrong"}), 401
    if not row["is_active"]:
        return jsonify({"ok": False, "reason": "suspended"}), 403
    if verification_required() and not row["email_verified"] and row["role"] != "admin":
        return jsonify({"ok": False, "reason": "verify_email"}), 403
    if twofa.is_enabled(row["id"]):
        return jsonify({"ok": False, "reason": "use_website"}), 403          # accounts with a 2-step code sign in on the website
    db.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login_at = ? WHERE id = ?",
               (utcnow(), row["id"]))
    token = secrets.token_urlsafe(32)
    db.execute("INSERT INTO app_tokens (token_hash, user_id, install_hash, created_at, last_seen) VALUES (?, ?, ?, ?, ?)",
               (_hash(token), row["id"], _hash(install), utcnow(), utcnow()))
    db.commit()
    return jsonify({"ok": True, "token": token, "email": row["email"]})


@bp.route("/api/app/status", methods=["POST"])
def api_status():
    """The app asks: may this signed-in person use the app on this phone?"""
    data = _json()
    token, install = data.get("token"), data.get("install")
    if not (isinstance(token, str) and 20 <= len(token) <= 200 and _install_ok(install)):
        return jsonify({"ok": False, "reason": "bad_request"}), 400
    if rate_limited("appstatus", 120, 3600):
        return jsonify({"ok": False, "reason": "slow_down"}), 429
    db = get_db()
    row = db.one("SELECT t.user_id, t.install_hash, u.id, u.role, u.is_active FROM app_tokens t "
                 "JOIN users u ON u.id = t.user_id WHERE t.token_hash = ?", (_hash(token),))
    if row is None or row["install_hash"] != _hash(install) or not row["is_active"]:
        return jsonify({"ok": False, "reason": "login"}), 401
    db.execute("UPDATE app_tokens SET last_seen = ? WHERE token_hash = ?", (utcnow(), _hash(token)))
    ok, reason, until = license_state(db, {"id": row["user_id"], "role": row["role"]}, install)
    return jsonify({"ok": ok, "reason": reason, "until": until or ""}), (200 if ok else 403)


@bp.route("/api/app/logout", methods=["POST"])
def api_logout():
    token = _json().get("token")
    if isinstance(token, str) and 20 <= len(token) <= 200:
        db = get_db()
        db.execute("DELETE FROM app_tokens WHERE token_hash = ?", (_hash(token),))
        db.commit()
    return jsonify({"ok": True})


@bp.route("/app/subscribe", methods=["GET", "POST"])
@login_required
def subscribe():
    db, user = get_db(), current_user()
    methods = [(k, label, donation_method(k)) for k, label in METHODS if donation_method(k)]
    errors = {}
    if request.method == "POST":
        method = request.form.get("method", "")
        ref = " ".join((request.form.get("reference") or "").split())[:80]
        note = " ".join((request.form.get("note") or "").split())[:200]
        if method not in {k for k, _, _ in methods}:
            errors["method"] = "Please choose how you paid."
        if len(ref) < 4:
            errors["reference"] = "Enter the transaction ID from your payment receipt (at least 4 characters)."
        pending = db.one("SELECT COUNT(*) AS n FROM app_subscriptions WHERE user_id = ? AND status = 'pending'",
                         (user["id"],))["n"]
        if pending >= 3:
            errors["reference"] = "You already have requests waiting. Please wait for them to be checked."
        if not errors and rate_limited("subreq", 10, 3600):
            errors["reference"] = "Too many requests. Please try again later."
        if not errors:
            db.insert("app_subscriptions", {"user_id": user["id"], "status": "pending", "method": method,
                                            "reference": ref, "note": note, "created_at": utcnow()})
            db.commit()
            flash("Thank you. We will check your payment and switch the app on for your account.", "ok")
            return redirect(url_for("subs.subscribe"))
    mine = db.all("SELECT id, status, method, reference, created_at, expires_at FROM app_subscriptions "
                  "WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user["id"],))
    meta = build_meta("Sur Music app subscription", "Subscribe to the Sur Music Android app.", noindex=True)
    return render_template("app_subscribe.html", meta=meta, methods=methods, errors=errors, mine=mine,
                           price=PRICE_TEXT, until=active_until(db, user["id"]), ld=[],
                           form=request.form if request.method == "POST" else {})


# ---------------------------------------------------------------- admin

@bp.route("/admin/subscriptions")
@admin_required
def admin_list():
    db = get_db()
    pending = db.all("SELECT s.id, s.method, s.reference, s.note, s.created_at, u.email FROM app_subscriptions s "
                     "JOIN users u ON u.id = s.user_id WHERE s.status = 'pending' ORDER BY s.id")
    live = db.all("SELECT s.id, s.user_id, s.expires_at, u.email FROM app_subscriptions s JOIN users u ON u.id = s.user_id "
                  "WHERE s.status = 'active' ORDER BY s.expires_at DESC LIMIT 200")
    now = _iso(_now())
    live = [r for r in live if (r["expires_at"] or "") > now]
    return render_template("admin/subscriptions.html", pending=pending, live=live, price=PRICE_TEXT)


@bp.route("/admin/subscriptions/<int:sid>/<any(approve, reject, revoke):action>", methods=["POST"])
@admin_required
def admin_action(sid, action):
    db = get_db()
    row = db.one("SELECT id, user_id, status FROM app_subscriptions WHERE id = ?", (sid,))
    if row is None:
        abort(404)
    if action == "approve" and row["status"] == "pending":
        start = max(_now(), datetime.fromisoformat(active_until(db, row["user_id"]) or _iso(_now())))
        db.execute("UPDATE app_subscriptions SET status = 'active', decided_at = ?, expires_at = ? WHERE id = ?",
                   (utcnow(), _iso(start + timedelta(days=PERIOD_DAYS)), sid))
        flash("Approved. The app is now on for this account for one year.", "ok")
    elif action == "reject" and row["status"] == "pending":
        db.execute("UPDATE app_subscriptions SET status = 'rejected', decided_at = ? WHERE id = ?", (utcnow(), sid))
        flash("Request rejected.", "ok")
    elif action == "revoke" and row["status"] == "active":
        db.execute("UPDATE app_subscriptions SET status = 'revoked', decided_at = ? WHERE id = ?", (utcnow(), sid))
        flash("Subscription switched off.", "ok")
    db.commit()
    audit(f"subscription_{action}", f"id={sid}")
    return redirect(url_for("subs.admin_list"))


@bp.route("/admin/subscriptions/grant", methods=["POST"])
@admin_required
def admin_grant():
    """Give a year to an account without a payment request (for example after a payment seen in the app)."""
    db = get_db()
    email = (request.form.get("email") or "").strip().lower()
    days = max(1, min(int(request.form.get("days") or PERIOD_DAYS) if (request.form.get("days") or "").isdigit() else PERIOD_DAYS, 1095))
    user = db.one("SELECT id FROM users WHERE lower(email) = ?", (email,)) if valid_email(email) else None
    if user is None:
        flash("No account with that email.", "error")
        return redirect(url_for("subs.admin_list"))
    start = max(_now(), datetime.fromisoformat(active_until(db, user["id"]) or _iso(_now())))
    db.insert("app_subscriptions", {"user_id": user["id"], "status": "active", "method": "granted", "reference": "admin",
                                    "created_at": utcnow(), "decided_at": utcnow(),
                                    "expires_at": _iso(start + timedelta(days=days))})
    db.commit()
    audit("subscription_grant", f"user={user['id']} days={days}")
    flash(f"Granted {days} days to {email}.", "ok")
    return redirect(url_for("subs.admin_list"))


@bp.route("/admin/subscriptions/reset-device", methods=["POST"])
@admin_required
def admin_reset_device():
    db = get_db()
    uid = request.form.get("user_id", "")
    if uid.isdigit():
        db.execute("DELETE FROM app_devices WHERE user_id = ?", (int(uid),))
        db.commit()
        audit("subscription_reset_device", f"user={uid}")
        flash("Phone released: the next phone that signs in becomes the one for this account.", "ok")
    return redirect(url_for("subs.admin_list"))
