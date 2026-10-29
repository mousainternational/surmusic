"""Two-step sign-in (authenticator-app codes, RFC 6238 TOTP) — optional, recommended for admins.

* Works with Google Authenticator, Microsoft Authenticator, Authy and similar apps (SHA-1, 6 digits, 30 seconds).
* The secret is stored encrypted with a key derived from SECRET_KEY, so a copy of the database alone is not enough.
* A code can be used only once (the last accepted time step is remembered).
* Ten single-use recovery codes are shown once when it is switched on; only their hashes are stored.
"""
import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

from .db import get_db, utcnow

ISSUER = "Sur Music"
STEP = 30
DIGITS = 6


def _fernet():
    key = hashlib.sha256((current_app.config["SECRET_KEY"] + "|two-step").encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def code_at(secret, step):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10 ** DIGITS).zfill(DIGITS)


def current_step(now=None):
    return int((now if now is not None else time.time()) // STEP)


def check_code(secret, code, last_step=0, now=None):
    """Return the accepted time step, or None. Allows one step of clock drift either way; never reuses a step."""
    code = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(code) != DIGITS:
        return None
    step = current_step(now)
    for s in (step - 1, step, step + 1):
        if s > (last_step or 0) and hmac.compare_digest(code_at(secret, s), code):
            return s
    return None


def otpauth_uri(secret, email):
    label = quote(f"{ISSUER}:{email}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(ISSUER)}&algorithm=SHA1&digits={DIGITS}&period={STEP}"


def pretty(secret):
    return " ".join(secret[i:i + 4] for i in range(0, len(secret), 4))


# ---------------------------------------------------------------- storage (table user_2fa)

def _row(user_id):
    return get_db().one("SELECT * FROM user_2fa WHERE user_id = ?", (user_id,))


def secret_of(row):
    try:
        return _fernet().decrypt(row["secret"].encode()).decode()
    except (InvalidToken, ValueError, TypeError, AttributeError):
        return None


def is_enabled(user_id):
    r = _row(user_id)
    return bool(r and r["enabled"])


def start_setup(user_id):
    """Create (or replace) a not-yet-enabled secret and return it."""
    secret = new_secret()
    db = get_db()
    db.execute("DELETE FROM user_2fa WHERE user_id = ?", (user_id,))
    db.execute("INSERT INTO user_2fa (user_id, secret, enabled, recovery_json, last_step, created_at) "
               "VALUES (?, ?, 0, '[]', 0, ?)", (user_id, _fernet().encrypt(secret.encode()).decode(), utcnow()))
    db.commit()
    return secret


def pending_secret(user_id):
    r = _row(user_id)
    return secret_of(r) if r and not r["enabled"] else None


def _hash_recovery(code):
    norm = "".join(ch for ch in code.lower() if ch.isalnum())
    key = hashlib.sha256((current_app.config["SECRET_KEY"] + "|recovery").encode()).digest()
    return hmac.new(key, norm.encode(), hashlib.sha256).hexdigest()


def new_recovery_codes(n=10):
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return ["".join(secrets.choice(alphabet) for _ in range(5)) + "-" + "".join(secrets.choice(alphabet) for _ in range(5))
            for _ in range(n)]


def enable(user_id, code):
    """Confirm setup with a code from the app. Returns the recovery codes, or None if the code is wrong."""
    r = _row(user_id)
    if not r or r["enabled"]:
        return None
    secret = secret_of(r)
    step = secret and check_code(secret, code, r["last_step"])
    if not step:
        return None
    codes = new_recovery_codes()
    db = get_db()
    db.execute("UPDATE user_2fa SET enabled = 1, last_step = ?, recovery_json = ?, created_at = ? WHERE user_id = ?",
               (step, json.dumps([_hash_recovery(c) for c in codes]), utcnow(), user_id))
    db.commit()
    return codes


def verify(user_id, code):
    """Check a sign-in code or a recovery code. Returns 'code', 'recovery' or None."""
    r = _row(user_id)
    if not r or not r["enabled"]:
        return None
    secret = secret_of(r)
    db = get_db()
    step = secret and check_code(secret, code, r["last_step"])
    if step:
        db.execute("UPDATE user_2fa SET last_step = ? WHERE user_id = ?", (step, user_id))
        db.commit()
        return "code"
    try:
        hashes = json.loads(r["recovery_json"] or "[]")
    except ValueError:
        hashes = []
    h = _hash_recovery(str(code or ""))
    if len("".join(ch for ch in str(code or "") if ch.isalnum())) == 10 and h in hashes:
        hashes.remove(h)
        db.execute("UPDATE user_2fa SET recovery_json = ? WHERE user_id = ?", (json.dumps(hashes), user_id))
        db.commit()
        return "recovery"
    return None


def recovery_left(user_id):
    r = _row(user_id)
    try:
        return len(json.loads(r["recovery_json"] or "[]")) if r else 0
    except ValueError:
        return 0


def regenerate_recovery(user_id):
    codes = new_recovery_codes()
    db = get_db()
    db.execute("UPDATE user_2fa SET recovery_json = ? WHERE user_id = ?",
               (json.dumps([_hash_recovery(c) for c in codes]), user_id))
    db.commit()
    return codes


def disable(user_id):
    db = get_db()
    db.execute("DELETE FROM user_2fa WHERE user_id = ?", (user_id,))
    db.commit()
