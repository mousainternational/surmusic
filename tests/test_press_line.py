"""The activity log says whether a visitor who opened a station or podcast page pressed play afterwards."""
from datetime import datetime, timedelta, timezone

from app import analytics
from app.analytics import get_db


def _ins(db, kind, vid, path, when, detail=""):
    db.execute("INSERT INTO events (kind, visitor_id, user_id, path, referrer, country, region, device, browser, os, "
               "detail, created_at) VALUES (?, ?, NULL, ?, '', 'PK', '', 'Mobile', 'Chrome', 'Android', ?, ?)",
               (kind, vid, path, detail, when))
    db.commit()


def test_press_line_for_station_and_podcast_pages(app):
    with app.app_context():
        db = get_db()
        t0 = datetime(2026, 11, 27, 6, 0, 0, tzinfo=timezone.utc)
        iso = lambda d: d.replace(microsecond=0).isoformat()
        db.execute("DELETE FROM events")
        _ins(db, "page_view", "pressA", "/station/1/alif", iso(t0))
        _ins(db, "play", "pressA", "", iso(t0 + timedelta(minutes=2)), detail="Alif")
        _ins(db, "page_view", "nopress", "/station/1/alif", iso(t0))
        _ins(db, "page_view", "podpress", "/podcasts/9", iso(t0))
        _ins(db, "play", "podpress", "", iso(t0 + timedelta(minutes=5)), detail="Episode 1")
        _ins(db, "page_view", "late", "/station/1/alif", iso(t0))
        _ins(db, "play", "late", "", iso(t0 + timedelta(minutes=45)), detail="Alif")
        _ins(db, "page_view", "home", "/", iso(t0))
        rows = {(r["visitor_id"], r["path"]): r for r in analytics.recent(kind="page_view", limit=50)}
        assert rows[("pressA", "/station/1/alif")]["pressed"] is True
        assert rows[("nopress", "/station/1/alif")]["pressed"] is False
        assert rows[("podpress", "/podcasts/9")]["pressed"] is True
        assert rows[("late", "/station/1/alif")]["pressed"] is False          # 45 minutes later is too late
        assert "pressed" not in rows[("home", "/")]                          # only station and podcast pages
