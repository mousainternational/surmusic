"""Low-database mode: browsing and listening must not wake the (free) database."""
from conftest import STATION, api, login

from app import db as dbmod
from app import lowdb


def _count_connections(monkeypatch):
    counter = {"n": 0}
    real_init = dbmod.Database.__init__

    def counting_init(self, *a, **kw):
        counter["n"] += 1
        return real_init(self, *a, **kw)

    monkeypatch.setattr(dbmod.Database, "__init__", counting_init)
    return counter


def test_listening_and_browsing_do_not_touch_the_database(client, app, monkeypatch):
    app.config["LOW_DB_MODE"] = True
    app.config["RATE_LIMITS_DISABLED"] = False
    for path in ("/", "/bollywood", "/lollywood", "/hollywood"):       # first visits fill the memory caches
        assert client.get(path).status_code == 200
    counter = _count_connections(monkeypatch)

    for path in ("/", "/bollywood", "/hollywood", "/about"):
        assert client.get(path).status_code == 200
    api(client, "POST", "/api/track", {"path": "/bollywood", "tz": "Asia/Karachi", "ref": "https://www.google.com/"})
    assert api(client, "POST", "/api/play", {"station": STATION, "category": "bollywood"}).status_code == 200
    for _ in range(3):                                                  # three minutes of listening
        api(client, "POST", "/api/heartbeat", {"station_name": STATION["name"], "category": "bollywood"})
    assert counter["n"] == 0, f"database opened {counter['n']} times while a visitor browsed and listened"
    assert len(lowdb.state(app).queue) >= 2                                         # page view + play are queued

    # the owner opens Admin → Live now: queued rows are written, the listener is shown from memory
    admin = app.test_client()
    login(admin)
    live = admin.get("/admin/live").get_data(as_text=True)
    assert STATION["name"] in live and "Pakistan" in live
    assert lowdb.state(app).queue == []
    from app.db import Database
    db = Database(app.config["DATABASE_URL"])
    kinds = [r["kind"] for r in db.all("SELECT kind FROM events")]
    assert "page_view" in kinds and "play" in kinds
    assert db.scalar("SELECT COUNT(*) FROM plays") == 1
    db.close()


def test_listening_time_recorded_when_stopped(client, app):
    app.config["LOW_DB_MODE"] = True
    client.get("/")
    api(client, "POST", "/api/heartbeat", {"station_name": "Radio One", "category": "bollywood"})
    st = lowdb.state(app)
    with st.lock:                                         # pretend they started 5 minutes ago
        row = next(iter(st.live.values()))
        row["started_at"] = "2020-01-01T00:00:00+00:00"
        row["last_seen"] = "2020-01-01T00:05:00+00:00"
    api(client, "POST", "/api/heartbeat", {"stop": True})
    assert not st.live
    with app.app_context():
        lowdb.flush(app)
    from app.db import Database
    db = Database(app.config["DATABASE_URL"])
    detail = db.scalar("SELECT detail FROM events WHERE kind = 'listened'")
    db.close()
    assert detail == "Radio One · 6 min"          # 5 min + up to 1 min after the last check-in


def test_queue_kept_when_database_is_unreachable(app):
    app.config["LOW_DB_MODE"] = True
    with app.app_context():
        lowdb.defer("INSERT INTO plays (station_uuid, station_name, category, created_at) VALUES (?, ?, ?, ?)",
                    ("x", "X", "", "2026-01-01T00:00:00+00:00"))
        good = app.config["DATABASE_URL"]
        app.config["DATABASE_URL"] = "sqlite:////nonexistent-dir/x.db"
        assert lowdb.flush(app) == 0 and lowdb.pending() == 1           # kept for the next try
        app.config["DATABASE_URL"] = good
        assert lowdb.flush(app) == 1 and lowdb.pending() == 0


def test_rate_limits_still_work_in_memory(client, app):
    app.config["LOW_DB_MODE"] = True
    app.config["RATE_LIMITS_DISABLED"] = False
    with app.test_request_context("/"):
        from app.security import rate_limited
        assert not any(rate_limited("t", 3, 60) for _ in range(3))
        assert rate_limited("t", 3, 60)


def test_free_hosting_turns_it_on_by_default(monkeypatch):
    import importlib
    monkeypatch.setenv("EPHEMERAL_STORAGE", "1")
    monkeypatch.delenv("LOW_DB_MODE", raising=False)
    from app import config
    importlib.reload(config)
    try:
        assert config.Config.LOW_DB_MODE is True
    finally:
        monkeypatch.delenv("EPHEMERAL_STORAGE")
        importlib.reload(config)
