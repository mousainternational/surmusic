"""Low-database mode — keeps the free PostgreSQL (Neon) asleep as much as possible.

Neon's free plan counts the hours the database is awake; it sleeps 5 minutes after the last query. Without this
mode every playing visitor wakes it once a minute (the "still listening" check-in), so a site with listeners
around the clock would use up the free hours. In low-database mode:

* "Live now" listeners, unique-visitor counts and rate limits are kept in this process's memory.
* Analytics events, plays and history are queued in memory and written in one batch every 15 minutes
  (sooner when someone opens the admin panel, and before the free server goes to sleep / restarts).
* Settings, station lists and "popular" lists are cached in memory.

So listening, browsing and page views do not touch the database at all; it wakes about once per 15 minutes.
Run ONE server process (WEB_CONCURRENCY=1, more threads) so all visitors share the same memory.
Turned on automatically on free hosting (EPHEMERAL_STORAGE=1) or with LOW_DB_MODE=1.
"""
import os
import threading
import time

from flask import current_app

_APPS = []          # apps with low-database mode in this process (for the gunicorn exit hook)


class State:
    def __init__(self):
        self.lock = threading.RLock()
        self.queue = []                 # [(sql, params)]
        self.oldest = None              # time.time() of the oldest queued write
        self.last_request = time.time()
        self.live = {}                  # session_key -> dict(listener)
        self.visitors = {}              # visitor_id -> last seen (time.time())
        self.hits = {}                  # rate-limit bucket -> [hits, reset_at]
        self.cache = {}                 # key -> (expires_at, value)
        self.thread_pid = None


def enabled(app=None):
    app = app or current_app
    return bool(app.config.get("LOW_DB_MODE"))


def state(app=None):
    app = app or current_app._get_current_object()
    st = app.extensions.get("lowdb")
    if st is None:
        st = app.extensions["lowdb"] = State()
        if app not in _APPS:
            _APPS.append(app)
    return st


# ---------------------------------------------------------------- memory cache

def cache_get(key):
    st = state()
    with st.lock:
        hit = st.cache.get(key)
        if hit and hit[0] > time.time():
            return True, hit[1]
    return False, None


def cache_set(key, value, ttl):
    st = state()
    with st.lock:
        st.cache[key] = (time.time() + ttl, value)
        if len(st.cache) > 500:                       # keep it small: drop expired / oldest
            now = time.time()
            for k in [k for k, v in st.cache.items() if v[0] <= now][:250] or list(st.cache)[:100]:
                st.cache.pop(k, None)


def cache_drop(prefix):
    st = state()
    with st.lock:
        for k in [k for k in st.cache if k.startswith(prefix)]:
            st.cache.pop(k, None)


# ---------------------------------------------------------------- deferred writes

MAX_QUEUE = 20000


def defer(sql, params):
    st = state()
    with st.lock:
        if len(st.queue) >= MAX_QUEUE:      # database unreachable for a long time: drop the oldest
            del st.queue[:1000]
        st.queue.append((sql, tuple(params)))
        if st.oldest is None:
            st.oldest = time.time()


def pending():
    return len(state().queue)


def flush(app=None):
    """Write every queued row in one connection. Safe to call often; does nothing when the queue is empty."""
    app = app or current_app._get_current_object()
    st = state(app)
    with st.lock:
        batch, st.queue, st.oldest = st.queue, [], None
    if not batch:
        return 0
    from .db import Database
    db = None
    try:
        db = Database(app.config["DATABASE_URL"])
        for sql, params in batch:
            db.execute(sql, params)
        db.commit()
        return len(batch)
    except Exception:
        app.logger.exception("Low-database mode: writing %s queued rows failed; will retry", len(batch))
        if db is not None:
            try:
                db.rollback()
            except Exception:
                pass
        with st.lock:                      # put them back in front, keep order
            st.queue[:0] = batch
            st.oldest = st.oldest or time.time()
        return 0
    finally:
        if db is not None:
            db.close()


def touch_request():
    """Called on every request: remember activity and make sure the background writer runs in this process."""
    app = current_app._get_current_object()
    st = state(app)
    st.last_request = time.time()
    if st.thread_pid != os.getpid():
        st.thread_pid = os.getpid()
        threading.Thread(target=_writer, args=(app,), name="lowdb-writer", daemon=True).start()


def _writer(app):
    every = app.config.get("LOW_DB_FLUSH_SECONDS", 900)
    idle = app.config.get("LOW_DB_IDLE_FLUSH_SECONDS", 600)
    st = state(app)
    while True:
        time.sleep(min(60, max(5, every // 10)))
        try:
            now = time.time()
            old_enough = st.oldest is not None and now - st.oldest >= every
            going_idle = st.queue and now - st.last_request >= idle      # free server sleeps after 15 min idle
            if old_enough or going_idle or len(st.queue) >= 2000:
                flush(app)
            _sweep(app)
        except Exception:  # pragma: no cover
            app.logger.exception("Low-database mode writer")


def flush_all():
    """Gunicorn exit hook (gunicorn.conf.py): save what is still queued before the process stops."""
    for app in list(_APPS):
        try:
            with app.app_context():
                flush(app)
        except Exception:  # pragma: no cover
            pass


# ---------------------------------------------------------------- rate limits in memory

def rate_limited(bucket, limit, window_seconds):
    st = state()
    now = time.time()
    with st.lock:
        hit = st.hits.get(bucket)
        if hit is None or hit[1] <= now:
            st.hits[bucket] = [1, now + window_seconds]
            if len(st.hits) > 50000:
                for k in [k for k, v in st.hits.items() if v[1] <= now]:
                    st.hits.pop(k, None)
            return False
        if hit[0] >= limit:
            return True
        hit[0] += 1
        return False


# ---------------------------------------------------------------- visitors and live listeners in memory

def saw_visitor(visitor_id):
    st = state()
    with st.lock:
        st.visitors[visitor_id] = time.time()


def online_visitors(seconds=300):
    st = state()
    cutoff = time.time() - seconds
    with st.lock:
        return sum(1 for t in st.visitors.values() if t >= cutoff)


def _sweep(app):
    """Close listening sessions whose tab vanished, forget old visitor ids."""
    from . import analytics
    st = state(app)
    cutoff = time.time() - analytics.LIVE_SECONDS
    with st.lock:
        stale = [k for k, v in st.live.items() if v["_seen"] < cutoff]
        gone = [st.live.pop(k) for k in stale]
        for k in [k for k, t in st.visitors.items() if t < time.time() - 3600]:
            st.visitors.pop(k, None)
    if gone:
        with app.app_context():
            for row in gone:
                analytics.close_session(row, extra=30)
