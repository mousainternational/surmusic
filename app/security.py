"""CSRF, rate limiting, accounts/sessions, audit log and security headers (nonce-based CSP)."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlparse

from flask import abort, current_app, g, redirect, request, session, url_for

from .db import get_db, utcnow

# ---------------------------------------------------------------- identity helpers

def via_local_tunnel():
    """True when the request came through a Cloudflare Tunnel (cloudflared) running on this same computer.
    Only a program on this machine can connect from 127.0.0.1, so its CF-Connecting-IP header can be trusted."""
    import ipaddress
    try:
        return ipaddress.ip_address(request.remote_addr or "").is_loopback and bool(request.headers.get("CF-Connecting-IP"))
    except ValueError:
        return False


def client_ip():
    """The visitor's IP address (used for rate limits and approximate location; never stored)."""
    if via_local_tunnel():
        import ipaddress
        cf = (request.headers.get("CF-Connecting-IP") or "").strip()
        try:
            return str(ipaddress.ip_address(cf))
        except ValueError:
            pass
    return request.remote_addr or "0.0.0.0"


def ip_hash(ip=None):
    """Only a keyed hash of visitor IPs is ever stored."""
    key = current_app.config["SECRET_KEY"].encode()
    return hmac.new(key, (ip or client_ip()).encode(), hashlib.sha256).hexdigest()[:32]


# ---------------------------------------------------------------- CSRF

def csrf_token():
    tok = session.get("_csrf")
    if not tok:
        tok = secrets.token_urlsafe(32)
        session["_csrf"] = tok
    return tok


def _same_origin():
    src = request.headers.get("Origin") or request.headers.get("Referer")
    if not src or src == "null":
        return True
    return urlparse(src).netloc == request.host


def csrf_protect():
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token", "")
    good = session.get("_csrf", "")
    if not good or not sent or not hmac.compare_digest(sent, good) or not _same_origin():
        if request.path.startswith("/api/"):
            abort(403)
        abort(400, description="Your form session expired. Please reload the page and try again.")


# ---------------------------------------------------------------- rate limiting

def rate_limited(name, limit, window_seconds, ident=None):
    """True when the caller exceeded `limit` hits in the window (records the hit)."""
    if current_app.config.get("RATE_LIMITS_DISABLED"):
        return False
    db = get_db()
    bucket = f"{name}:{ident or ip_hash()}"
    now = datetime.now(timezone.utc)
    row = db.one("SELECT hits, reset_at FROM rate_limits WHERE bucket = ?", (bucket,))
    if row is None or datetime.fromisoformat(row["reset_at"]) <= now:
        reset = (now + timedelta(seconds=window_seconds)).replace(microsecond=0).isoformat()
        db.execute("DELETE FROM rate_limits WHERE bucket = ?", (bucket,))
        db.execute("INSERT INTO rate_limits (bucket, hits, reset_at) VALUES (?, 1, ?)", (bucket, reset))
        db.commit()
        return False
    if row["hits"] >= limit:
        return True
    db.execute("UPDATE rate_limits SET hits = hits + 1 WHERE bucket = ?", (bucket,))
    db.commit()
    return False


def purge_rate_limits():
    db = get_db()
    db.execute("DELETE FROM rate_limits WHERE reset_at < ?", (utcnow(),))
    db.commit()


# ---------------------------------------------------------------- accounts & sessions

def start_session(user, remember=False):
    """Fresh session on every login (prevents session fixation)."""
    geo = (session.get("geo_c"), session.get("geo_r"))
    session.clear()
    if geo[0]:
        session["geo_c"], session["geo_r"] = geo
    session.permanent = bool(remember) and user["role"] != "admin"
    session["uid"] = user["id"]
    session["sv"] = user["session_version"]
    session["login_at"] = utcnow()
    csrf_token()
    g.pop("user", None)


def current_user():
    if "user" in g:
        return g.user
    g.user = None
    uid, sv = session.get("uid"), session.get("sv")
    if uid:
        row = get_db().one("SELECT id, email, display_name, role, is_active, email_verified, session_version "
                           "FROM users WHERE id = ?", (uid,))
        ok = row is not None and row["session_version"] == sv and row["is_active"] == 1
        if ok and row["role"] == "admin":
            try:  # admin sessions expire after ADMIN_SESSION_HOURS regardless of "remember me"
                started = datetime.fromisoformat(session.get("login_at", ""))
                limit = timedelta(hours=current_app.config["ADMIN_SESSION_HOURS"])
                ok = datetime.now(timezone.utc) - started < limit
            except ValueError:
                ok = False
        if ok:
            g.user = row
        else:
            session.clear()
    return g.user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            if request.path.startswith("/api/"):
                abort(401)
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return redirect(url_for("auth.login", next=request.path))
        if user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapper


def audit(action, detail=""):
    user = current_user()
    db = get_db()
    db.execute("INSERT INTO audit_log (admin_id, action, detail, ip, created_at) VALUES (?, ?, ?, ?, ?)",
               (user["id"] if user else None, action, detail[:500], ip_hash(), utcnow()))
    db.commit()


def safe_next(target, default):
    """Only allow redirects to local paths (prevents open redirects)."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return default


# ---------------------------------------------------------------- headers / CSP

def csp_nonce():
    if "csp_nonce" not in g:
        g.csp_nonce = secrets.token_urlsafe(18)
    return g.csp_nonce


def build_csp(ads_enabled):
    nonce = csp_nonce()
    if ads_enabled:
        # Google AdSense loads further scripts and iframes; 'strict-dynamic' trusts only scripts
        # started by our nonce-tagged tags (Google's recommended CSP for ads).
        return ("default-src 'self'; "
                f"script-src 'nonce-{nonce}' 'strict-dynamic' https: 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' https: data:; font-src 'self' https: data:; "
                "media-src https: blob:; connect-src 'self' https:; frame-src https:; "
                "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
    return ("default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; style-src 'self'; img-src 'self' https: data:; "
            "font-src 'self'; media-src https: blob:; connect-src 'self'; frame-src 'none'; "
            "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


def security_headers(resp, ads_enabled=False):
    is_admin_area = request.path.startswith(("/admin", "/account"))
    resp.headers.setdefault("Content-Security-Policy", build_csp(ads_enabled and not is_admin_area))
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    if current_app.config.get("SESSION_COOKIE_SECURE"):
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if is_admin_area or request.path.startswith(("/login", "/signup", "/forgot", "/reset", "/verify")):
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        resp.headers["Cache-Control"] = "no-store"
    return resp
