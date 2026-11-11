"""Keep the small, valuable data (accounts, admin, 2-step keys, settings, favourites, likes, reviews, app
licences, uploaded pictures) safe on hosting WITHOUT a permanent disk (Render's free plan).

Why: on Render's free plan every restart, deploy or wake-up after sleeping starts from a fresh copy of the
code. A database file on that machine disappears, so accounts and settings vanished again and again.

How (free, no new service):
* A small encrypted copy of those tables is written to a PRIVATE GitHub repository (one file, a new commit
  only when something changed). Git history keeps every older copy, so this is also the weekly backup.
* When the site starts with an empty database (no accounts at all), it reads that copy back first.

Where the copy is kept (first one configured wins):
* Cloudflare Workers KV (free: 1,000 writes a day, values up to 25 MB; over the limit it simply stops, no bill):
  BACKUP_CF_ACCOUNT_ID, BACKUP_CF_NAMESPACE_ID, BACKUP_CF_TOKEN (an API token with "Workers KV Storage: Edit" only)
* or a PRIVATE GitHub repository: BACKUP_GITHUB_REPO + BACKUP_GITHUB_TOKEN ("Contents: read and write" on it only)
Optional: BACKUP_KEY (encryption password; default: derived from SECRET_KEY), BACKUP_EVERY_MINUTES (default 10).
"""
import base64
import gzip
import hashlib
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

# Parents first (foreign keys). Big or throw-away tables (station lists, page views, plays, rate limits,
# "live now") are NOT copied: they are rebuilt by themselves.
TABLES = ["settings", "users", "user_2fa", "favorites", "station_likes", "reviews", "messages", "apps",
          "media_blobs", "app_licenses", "app_subscriptions", "app_trials", "app_devices", "app_tokens"]
FORMAT = "surmusic-snapshot-v1"
FILE_PATH = "surmusic-data.json.gz.enc"
MAX_BYTES = 20 * 1024 * 1024          # never push more than this (GitHub file limit is far higher)

_state = {"last_hash": None, "sha": None, "started": False, "last_ok": None, "last_error": None}
_lock = threading.Lock()


# ------------------------------------------------------------------ where the data lives

def storage_is_persistent(storage_dir):
    """True when STORAGE_DIR survives a restart. On Render it does only if a paid disk is mounted there.
    Elsewhere (own computer, VPS, docker volume) a normal folder is kept, so this returns True."""
    if os.environ.get("RENDER", "").lower() != "true":
        return True
    path = os.path.abspath(storage_dir)
    while True:
        if os.path.ismount(path):
            return path != "/"
        parent = os.path.dirname(path)
        if parent == path:
            return False
        path = parent


def _kv_on():
    return all(os.environ.get(k) for k in ("BACKUP_CF_ACCOUNT_ID", "BACKUP_CF_NAMESPACE_ID", "BACKUP_CF_TOKEN"))


def _gh_on():
    return bool(os.environ.get("BACKUP_GITHUB_REPO") and os.environ.get("BACKUP_GITHUB_TOKEN"))


def enabled():
    return _kv_on() or _gh_on()


def backend():
    return "cloudflare-kv" if _kv_on() else ("github" if _gh_on() else "")


def status():
    """For the admin panel and /healthz: no secrets."""
    return {"enabled": enabled(), "where": backend(), "last_ok": _state["last_ok"], "last_error": _state["last_error"]}


# ------------------------------------------------------------------ encryption

def _fernet():
    from cryptography.fernet import Fernet
    secret = os.environ.get("BACKUP_KEY") or os.environ.get("SECRET_KEY") or ""
    if len(secret) < 16:
        raise RuntimeError("BACKUP_KEY or SECRET_KEY is needed to encrypt the backup")
    key = base64.urlsafe_b64encode(hashlib.sha256(("surmusic-backup:" + secret).encode()).digest())
    return Fernet(key)


def seal(payload: bytes) -> bytes:
    return _fernet().encrypt(gzip.compress(payload, 9))


def unseal(blob: bytes) -> bytes:
    return gzip.decompress(_fernet().decrypt(blob))


# ------------------------------------------------------------------ export / import

def _columns(db, table):
    if db.pg:
        return {r["column_name"] for r in db.all(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?", (table,))}
    return {r["name"] for r in db.all(f"PRAGMA table_info({table})")}


def export_tables(db):
    tables = {}
    for t in TABLES:
        try:
            tables[t] = db.all(f"SELECT * FROM {t}")
        except Exception:          # table missing in an older database
            db.rollback()
            tables[t] = []
    return tables


def snapshot_bytes(db):
    """Stable JSON of the valuable tables (same data → same bytes, so unchanged data is not pushed)."""
    body = {"format": FORMAT, "tables": export_tables(db)}
    return json.dumps(body, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")


def import_tables(db, data):
    """Load a snapshot into an EMPTY database. Returns {table: rows}."""
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("tables"), dict):
        raise ValueError("not a Sur Music snapshot")
    counts = {}
    try:
        for t in TABLES:
            rows = data["tables"].get(t) or []
            allowed = _columns(db, t)
            if not allowed:
                continue
            db.execute(f"DELETE FROM {t}")
            for row in rows:
                cols = [c for c in row if c in allowed]
                if cols:
                    db.execute(f"INSERT INTO {t} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                               [row[c] for c in cols])
            counts[t] = len(rows)
            if db.pg and "id" in allowed:
                db.execute(f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), "
                           f"COALESCE((SELECT MAX(id) FROM {t}), 0) + 1, false)")
        db.commit()
    except Exception:
        db.rollback()
        raise
    return counts


# ------------------------------------------------------------------ GitHub (contents API)

def _http(method, url, body=None, token=None):
    """Small HTTPS helper; replaced in tests. Returns (status, bytes)."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "surmusic-backup"})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https host)
            return r.status, r.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() or b""


def _kv_http(method, url, data=None, token=None):
    """Raw bytes to/from Cloudflare's API; replaced in tests. Returns (status, bytes)."""
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "User-Agent": "surmusic-backup"})
    if data is not None:
        req.add_header("Content-Type", "application/octet-stream")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https host)
            return r.status, r.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() or b""


def _kv_url():
    a, n = os.environ["BACKUP_CF_ACCOUNT_ID"].strip(), os.environ["BACKUP_CF_NAMESPACE_ID"].strip()
    return f"https://api.cloudflare.com/client/v4/accounts/{a}/storage/kv/namespaces/{n}/values/{FILE_PATH}"


def _url():
    repo = os.environ["BACKUP_GITHUB_REPO"].strip().strip("/")
    branch = os.environ.get("BACKUP_GITHUB_BRANCH", "main")
    return f"https://api.github.com/repos/{repo}/contents/{FILE_PATH}", branch


def fetch_remote():
    """(sha, decrypted bytes) of the saved copy, (None, None) if there is none yet. Raises on errors."""
    if _kv_on():
        code, raw = _kv_http("GET", _kv_url(), token=os.environ["BACKUP_CF_TOKEN"])
        if code == 404:
            return None, None
        if code != 200:
            raise RuntimeError(f"Cloudflare answered {code}")
        return None, unseal(raw)
    url, branch = _url()
    token = os.environ["BACKUP_GITHUB_TOKEN"]
    code, raw = _http("GET", f"{url}?ref={branch}", token=token)
    if code == 404:
        return None, None
    if code != 200:
        raise RuntimeError(f"GitHub answered {code}")
    meta = json.loads(raw)
    content = meta.get("content") or ""
    if not content and meta.get("git_url"):      # files over 1 MB: fetch the blob instead
        code, raw = _http("GET", meta["git_url"], token=token)
        if code != 200:
            raise RuntimeError(f"GitHub answered {code}")
        content = json.loads(raw).get("content") or ""
    blob = base64.b64decode(content)
    return meta.get("sha"), unseal(blob)


def push(db, force=False):
    """Write the copy (Cloudflare KV or GitHub) if the data changed. Returns 'pushed', 'unchanged', 'off' or 'failed'."""
    if not enabled():
        return "off"
    with _lock:
        try:
            payload = snapshot_bytes(db)
            digest = hashlib.sha256(payload).hexdigest()
            if digest == _state["last_hash"] and not force:
                return "unchanged"
            data = json.loads(payload)
            if not data["tables"].get("users"):
                # never replace a good copy with an empty database (e.g. right after a failed restore)
                return "unchanged"
            blob = seal(payload)
            if len(blob) > MAX_BYTES:
                _state["last_error"] = "backup too large"
                return "failed"
            if _kv_on():
                code, _raw = _kv_http("PUT", _kv_url(), blob, token=os.environ["BACKUP_CF_TOKEN"])
                if code != 200:
                    _state["last_error"] = f"Cloudflare answered {code}"
                    log.warning("Data backup to Cloudflare failed (HTTP %s)", code)
                    return "failed"
                _state["last_hash"] = digest
                _state["last_ok"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                _state["last_error"] = None
                log.warning("Data backup saved to Cloudflare KV (%d bytes)", len(blob))
                return "pushed"
            url, branch = _url()
            token = os.environ["BACKUP_GITHUB_TOKEN"]
            if _state["sha"] is None:
                code, raw = _http("GET", f"{url}?ref={branch}", token=token)
                if code == 200:
                    _state["sha"] = json.loads(raw).get("sha")
            body = {"message": "Sur Music data backup", "branch": branch,
                    "content": base64.b64encode(blob).decode("ascii")}
            if _state["sha"]:
                body["sha"] = _state["sha"]
            code, raw = _http("PUT", url, body, token=token)
            if code == 409 or code == 422:        # someone else wrote it: read the new sha and try once more
                code2, raw2 = _http("GET", f"{url}?ref={branch}", token=token)
                if code2 == 200:
                    body["sha"] = json.loads(raw2).get("sha")
                    code, raw = _http("PUT", url, body, token=token)
            if code not in (200, 201):
                _state["last_error"] = f"GitHub answered {code}"
                log.warning("Data backup to GitHub failed (HTTP %s)", code)
                return "failed"
            _state["sha"] = json.loads(raw).get("content", {}).get("sha")
            _state["last_hash"] = digest
            _state["last_ok"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            _state["last_error"] = None
            return "pushed"
        except Exception as exc:   # never break the site for a backup
            db.rollback()
            _state["last_error"] = exc.__class__.__name__
            log.warning("Data backup failed: %s", exc.__class__.__name__)
            return "failed"


def restore_if_empty(url):
    """At start: if the database has no accounts, load the saved copy. Returns a short status word."""
    if not enabled():
        return "off"
    from .db import Database
    db = Database(url)
    try:
        if db.scalar("SELECT COUNT(*) FROM users"):
            return "not-needed"
        sha, payload = fetch_remote()
        if payload is None:
            return "no-copy"
        counts = import_tables(db, json.loads(payload))
        _state["sha"] = sha
        _state["last_hash"] = hashlib.sha256(payload).hexdigest()
        log.warning("Restored saved data from GitHub: %s", ", ".join(f"{k}={v}" for k, v in counts.items() if v))
        return "restored"
    except Exception as exc:
        db.rollback()
        _state["last_error"] = exc.__class__.__name__
        log.error("Could not restore saved data from GitHub: %s", exc.__class__.__name__)
        return "failed"
    finally:
        db.close()


def push_url(url, force=False):
    from .db import Database
    db = Database(url)
    try:
        return push(db, force=force)
    finally:
        db.close()


_APP_URLS = []


def start(app):
    """Background loop: every BACKUP_EVERY_MINUTES write the copy if something changed."""
    if not enabled() or app.config.get("TESTING") or _state["started"]:
        return
    _state["started"] = True
    _APP_URLS.append(app.config["DATABASE_URL"])
    try:
        every = max(2, int(os.environ.get("BACKUP_EVERY_MINUTES", "10")))
    except ValueError:
        every = 10

    def loop():
        time.sleep(60)
        while True:
            push_url(app.config["DATABASE_URL"])
            time.sleep(every * 60)

    threading.Thread(target=loop, name="data-backup", daemon=True).start()


_timer = {"t": None}
_timer_lock = threading.Lock()


def schedule_push(app, delay=15):
    """Save a copy soon after something important changed (sign-up, email confirmed, 2-step, settings),
    instead of waiting for the 10-minute loop: a restart in between would lose it. Several changes close
    together give one save."""
    if not enabled() or app.config.get("TESTING_NO_SCHEDULE"):
        return
    url = app.config["DATABASE_URL"]

    def run():
        _timer["t"] = None
        push_url(url)

    with _timer_lock:
        if _timer["t"] is not None:
            return
        t = threading.Timer(delay, run)
        t.daemon = True
        _timer["t"] = t
    t.start()


def push_all_on_exit():
    """Called by gunicorn just before the server stops (deploy, restart, going to sleep)."""
    for url in _APP_URLS:
        push_url(url)
