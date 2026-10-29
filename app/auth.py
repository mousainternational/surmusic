"""Accounts: sign up, sign in, email verification, password reset, account management."""
import hashlib
import json
from datetime import datetime, timedelta, timezone

from flask import (Blueprint, Response, current_app, flash, g, redirect, render_template, request, session,
                   url_for)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from . import analytics
from .db import get_db, utcnow
from .mailer import send_mail, smtp_ready
from .security import current_user, login_required, rate_limited, safe_next, start_session
from .settings import get_settings
from .util import valid_email

bp = Blueprint("auth", __name__)
LOCK_AFTER, LOCK_MINUTES = 5, 15
MIN_PASSWORD = 10
COMMON_PASSWORDS = {
    "1234567890", "12345678910", "123456789a", "password123", "password1234", "qwertyuiop", "1q2w3e4r5t",
    "iloveyou123", "pakistan123", "pakistan786", "abc1234567", "asdfghjkl1", "qwerty1234", "1111111111",
    "0000000000", "zaq12wsxcde", "welcome123", "admin12345", "letmein123", "football123", "aaaaaaaaaa",
    "abcdefghij", "sunshine123", "princess123", "surmusic123", "mousa12345",
}
META = {"noindex": True}


def _signer(salt):
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=salt)


def _pw_fingerprint(password_hash):
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def password_problem(password, email=""):
    if len(password) < MIN_PASSWORD:
        return f"Password must be at least {MIN_PASSWORD} characters."
    if len(password) > 200:
        return "Password is too long."
    low = password.lower()
    if low in COMMON_PASSWORDS or len(set(password)) < 4:
        return "This password is too easy to guess. Please choose a stronger one."
    if email and low == email.lower():
        return "Password must not be your email address."
    return None


def _form_ok():
    """Honeypot field for bots."""
    return not request.form.get("website")


def _send_verification(user):
    token = _signer("verify").dumps({"uid": user["id"], "email": user["email"]})
    link = current_app.config["SITE_URL"] + url_for("auth.verify", token=token)
    s = get_settings()
    return send_mail(user["email"], f"Confirm your {s['site_name']} account",
                     f"Assalam o Alaikum{', ' + user['display_name'] if user['display_name'] else ''}!\n\n"
                     f"Please confirm your email address for {s['site_full_name']}:\n{link}\n\n"
                     "This link works for 48 hours. If you did not sign up, ignore this email.\n\n"
                     f"— {s['site_name']} by {s['owner_name']}")


def verification_required():
    return get_settings().get("require_email_verification") == "1" and smtp_ready()


# ---------------------------------------------------------------- sign up / in / out

@bp.route("/signup", methods=["GET", "POST"])
def signup():
    s = get_settings()
    nxt = safe_next(request.args.get("next"), url_for("public.home"))
    if current_user():
        return redirect(nxt)
    if s.get("signup_enabled") != "1":
        return render_template("auth/closed.html", meta=META)
    form, errors = {}, {}
    if request.method == "POST":
        form = {"email": (request.form.get("email") or "").strip().lower(),
                "display_name": " ".join((request.form.get("display_name") or "").split())[:40]}
        password = request.form.get("password") or ""
        if not valid_email(form["email"]):
            errors["email"] = "Please enter a valid email address."
        problem = password_problem(password, form["email"])
        if problem:
            errors["password"] = problem
        elif password != (request.form.get("password2") or ""):
            errors["password2"] = "The two passwords do not match."
        if not request.form.get("agree"):
            errors["agree"] = "Please accept the Terms and Privacy Policy."
        if not _form_ok():
            errors["form"] = "Sign-up rejected."
        db = get_db()
        if not errors and db.one("SELECT id FROM users WHERE email = ?", (form["email"],)):
            errors["email"] = "An account with this email already exists. Try signing in or resetting your password."
        if not errors and rate_limited("signup", 5, 3600):
            errors["form"] = "Too many sign-ups from your connection. Please try again later."
        if not errors:
            uid = db.insert("users", {"email": form["email"],
                                      "password_hash": generate_password_hash(password, method="scrypt"),
                                      "display_name": form["display_name"], "role": "user", "is_active": 1,
                                      "email_verified": 0, "created_at": utcnow()})
            db.commit()
            analytics.record("signup", uid, detail=form["display_name"])
            user = db.one("SELECT * FROM users WHERE id = ?", (uid,))
            status = _send_verification(user) if smtp_ready() else "pending_setup"
            if verification_required():
                flash("Account created. We sent a confirmation link to your email — open it to sign in.", "success")
                return redirect(url_for("auth.login"))
            start_session(user, remember=True)
            if status == "sent":
                flash("Welcome to Sur Music! Press play to start listening. We also sent a link to confirm your "
                      "email.", "success")
            else:
                flash("Welcome to Sur Music! Your account is ready — press play to start listening.", "success")
            return redirect(nxt)
    return render_template("auth/signup.html", meta={"title": "Create your account | Sur Music", "noindex": True},
                           form=form, errors=errors), (400 if errors else 200)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(safe_next(request.args.get("next"), url_for("public.home")))
    error, email = None, ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        db = get_db()
        if not _form_ok():
            error = "Sign-in rejected."
        elif rate_limited("login", 20, 900):
            error = "Too many sign-in attempts. Please wait 15 minutes."
        else:
            row = db.one("SELECT * FROM users WHERE email = ?", (email,))
            now = datetime.now(timezone.utc)
            if row and row["locked_until"] and datetime.fromisoformat(row["locked_until"]) > now:
                error = "This account is temporarily locked after several failed attempts. Try again in 15 minutes."
            elif row and check_password_hash(row["password_hash"], password):
                if not row["is_active"]:
                    error = "This account has been suspended. Contact us if you think this is a mistake."
                elif verification_required() and not row["email_verified"] and row["role"] != "admin":
                    error = "Please confirm your email first. Check your inbox, or request a new link below."
                    session["resend_uid"] = row["id"]
                else:
                    db.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login_at = ? "
                               "WHERE id = ?", (utcnow(), row["id"]))
                    db.commit()
                    start_session(row, remember=bool(request.form.get("remember")))
                    analytics.record("login", row["id"])
                    if row["role"] == "admin":
                        from .security import audit
                        audit("admin_login", email)
                    default = url_for("admin.dashboard") if row["role"] == "admin" else url_for("public.home")
                    return redirect(safe_next(request.args.get("next"), default))
            else:
                if row:
                    fails = row["failed_attempts"] + 1
                    lock = (now + timedelta(minutes=LOCK_MINUTES)).replace(microsecond=0).isoformat() \
                        if fails >= LOCK_AFTER else None
                    db.execute("UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                               (0 if lock else fails, lock, row["id"]))
                    db.commit()
                error = "Incorrect email or password."
                analytics.record("login_failed", row["id"] if row else None, detail=email[:100])
    return render_template("auth/login.html", meta={"title": "Sign in | Sur Music", "noindex": True},
                           error=error, email=email, can_resend=bool(session.get("resend_uid"))), \
        (401 if error else 200)


@bp.route("/logout", methods=["POST"])
def logout():
    u = current_user()
    if u:
        analytics.stop_listening(u["id"])
        analytics.record("logout", u["id"])
    geo = (session.get("geo_c"), session.get("geo_r"))
    session.clear()
    if geo[0]:
        session["geo_c"], session["geo_r"] = geo
    flash("You are signed out.", "success")
    return redirect(url_for("public.home"))


# ---------------------------------------------------------------- email verification

@bp.route("/verify/<token>")
def verify(token):
    try:
        data = _signer("verify").loads(token, max_age=48 * 3600)
    except (BadSignature, SignatureExpired):
        flash("This confirmation link is invalid or has expired. Sign in to get a new one.", "error")
        return redirect(url_for("auth.login"))
    db = get_db()
    row = db.one("SELECT * FROM users WHERE id = ? AND email = ?", (data.get("uid"), data.get("email")))
    if not row:
        flash("This confirmation link is no longer valid.", "error")
        return redirect(url_for("auth.login"))
    db.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (row["id"],))
    db.commit()
    flash("Thank you — your email is confirmed.", "success")
    return redirect(url_for("auth.account") if current_user() else url_for("auth.login"))


@bp.route("/verify/resend", methods=["POST"])
def verify_resend():
    uid = current_user()["id"] if current_user() else session.get("resend_uid")
    if uid and smtp_ready() and not rate_limited("verify-resend", 3, 3600):
        row = get_db().one("SELECT * FROM users WHERE id = ?", (uid,))
        if row and not row["email_verified"]:
            _send_verification(row)
    flash("If your email still needs confirming, a new link is on its way.", "success")
    return redirect(url_for("auth.account") if current_user() else url_for("auth.login"))


# ---------------------------------------------------------------- password reset

@bp.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        if valid_email(email) and _form_ok() and not rate_limited("forgot", 5, 3600):
            row = get_db().one("SELECT * FROM users WHERE email = ? AND is_active = 1", (email,))
            if row and smtp_ready():
                token = _signer("reset").dumps({"uid": row["id"], "fp": _pw_fingerprint(row["password_hash"])})
                link = current_app.config["SITE_URL"] + url_for("auth.reset", token=token)
                s = get_settings()
                send_mail(row["email"], f"Reset your {s['site_name']} password",
                          f"Someone (hopefully you) asked to reset the password for {row['email']}.\n\n"
                          f"Choose a new password here (valid for 1 hour, works once):\n{link}\n\n"
                          "If you did not ask for this, ignore this email — your password stays the same.")
        # Same answer whether or not the account exists (prevents email discovery).
        msg = "If an account exists for that email, we sent a reset link. Check your inbox and spam folder."
        if not smtp_ready():
            msg = ("Password-reset emails are not available yet on this website. "
                   "Please contact us through the Contact page for help.")
        flash(msg, "success" if smtp_ready() else "warning")
        return redirect(url_for("auth.forgot"))
    return render_template("auth/forgot.html", meta={"title": "Forgot password | Sur Music", "noindex": True})


@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset(token):
    try:
        data = _signer("reset").loads(token, max_age=3600)
    except (BadSignature, SignatureExpired):
        flash("This reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("auth.forgot"))
    db = get_db()
    row = db.one("SELECT * FROM users WHERE id = ?", (data.get("uid"),))
    if not row or _pw_fingerprint(row["password_hash"]) != data.get("fp"):
        flash("This reset link was already used. Please request a new one.", "error")
        return redirect(url_for("auth.forgot"))
    error = None
    if request.method == "POST":
        password = request.form.get("password") or ""
        error = password_problem(password, row["email"])
        if not error and password != (request.form.get("password2") or ""):
            error = "The two passwords do not match."
        if not error:
            db.execute("UPDATE users SET password_hash = ?, session_version = session_version + 1, "
                       "failed_attempts = 0, locked_until = NULL, email_verified = 1 WHERE id = ?",
                       (generate_password_hash(password, method="scrypt"), row["id"]))
            db.commit()
            analytics.record("password_reset", row["id"])
            session.clear()
            flash("Your password was changed. Please sign in.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/reset.html", meta={"title": "Choose a new password | Sur Music", "noindex": True},
                           error=error), (400 if error else 200)


# ---------------------------------------------------------------- my account

@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    db = get_db()
    me = db.one("SELECT * FROM users WHERE id = ?", (g.user["id"],))
    if request.method == "POST":
        action = request.form.get("action")
        if action == "profile":
            name = " ".join((request.form.get("display_name") or "").split())[:40]
            db.execute("UPDATE users SET display_name = ? WHERE id = ?", (name, me["id"]))
            db.commit()
            flash("Profile saved.", "success")
        elif action == "password":
            cur, new, again = (request.form.get(k) or "" for k in ("current", "new", "again"))
            problem = password_problem(new, me["email"])
            if not check_password_hash(me["password_hash"], cur):
                flash("Your current password is incorrect.", "error")
            elif problem:
                flash(problem, "error")
            elif new != again:
                flash("The two new passwords do not match.", "error")
            else:
                sv = me["session_version"] + 1
                db.execute("UPDATE users SET password_hash = ?, session_version = ? WHERE id = ?",
                           (generate_password_hash(new, method="scrypt"), sv, me["id"]))
                db.commit()
                session["sv"] = sv  # keep this device signed in, sign out every other device
                flash("Password changed. You were signed out on all other devices.", "success")
        elif action == "signout_all":
            sv = me["session_version"] + 1
            db.execute("UPDATE users SET session_version = ? WHERE id = ?", (sv, me["id"]))
            db.commit()
            session["sv"] = sv
            flash("Signed out on all other devices.", "success")
        return redirect(url_for("auth.account"))
    stats = {
        "favorites": db.scalar("SELECT COUNT(*) FROM favorites WHERE user_id = ?", (me["id"],)),
        "history": db.scalar("SELECT COUNT(*) FROM history WHERE user_id = ?", (me["id"],)),
    }
    recent = [json.loads(r["station_json"]) | {"played_at": r["played_at"]} for r in
              db.all("SELECT station_json, played_at FROM history WHERE user_id = ? ORDER BY played_at DESC LIMIT 10",
                     (me["id"],))]
    signins = [e for e in analytics.recent(user_id=me["id"], limit=60) if e["kind"] in ("login", "signup")][:5]
    return render_template("account/account.html", meta={"title": "My account | Sur Music", "noindex": True},
                           me=me, stats=stats, recent=recent, smtp=smtp_ready(), signins=signins,
                           minutes=analytics.listening_minutes(me["id"]))


@bp.route("/account/export")
@login_required
def account_export():
    db = get_db()
    me = db.one("SELECT email, display_name, role, email_verified, created_at, last_login_at FROM users WHERE id = ?",
                (g.user["id"],))
    data = {
        "account": me,
        "favorites": [json.loads(r["station_json"]) for r in
                      db.all("SELECT station_json FROM favorites WHERE user_id = ?", (g.user["id"],))],
        "history": [dict(json.loads(r["station_json"]), played_at=r["played_at"]) for r in
                    db.all("SELECT station_json, played_at FROM history WHERE user_id = ? ORDER BY played_at DESC",
                           (g.user["id"],))],
    }
    return Response(json.dumps(data, indent=1, ensure_ascii=False), mimetype="application/json",
                    headers={"Content-Disposition": 'attachment; filename="surmusic-my-data.json"'})


@bp.route("/account/delete", methods=["POST"])
@login_required
def account_delete():
    db = get_db()
    me = db.one("SELECT * FROM users WHERE id = ?", (g.user["id"],))
    if me["role"] == "admin":
        flash("Administrator accounts cannot be deleted here.", "error")
        return redirect(url_for("auth.account"))
    if not check_password_hash(me["password_hash"], request.form.get("password") or ""):
        flash("Password is incorrect — your account was not deleted.", "error")
        return redirect(url_for("auth.account"))
    db.execute("DELETE FROM favorites WHERE user_id = ?", (me["id"],))
    db.execute("DELETE FROM history WHERE user_id = ?", (me["id"],))
    db.execute("DELETE FROM live_sessions WHERE user_id = ?", (me["id"],))
    db.execute("UPDATE events SET user_id = NULL WHERE user_id = ?", (me["id"],))
    db.execute("DELETE FROM users WHERE id = ?", (me["id"],))
    db.commit()
    analytics.record("account_deleted")
    session.clear()
    flash("Your account and all its data were deleted. Thank you for listening to Sur Music.", "success")
    return redirect(url_for("public.home"))

