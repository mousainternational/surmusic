import re


def test_long_admin_lists_scroll_inside_their_card(client):
    css = client.get("/static/css/site.css").get_data(as_text=True)
    rule = " ".join(re.findall(r"\.bars-list \{[^}]*\}", css))
    assert "max-height" in rule and "overflow-y: auto" in rule


def test_statistics_copy_is_saved_at_least_every_hour_without_a_fast_store():
    src = open("app/persist.py", encoding="utf-8").read()
    assert '"30" if _kv_on() else "60"' in src


def test_visit_sources_are_grouped_and_add_up_to_the_visitors(app):
    from app import analytics
    from app.db import get_db
    names = {"https://m.facebook.com/": "facebook.com", "https://lm.facebook.com/l.php": "facebook.com", "facebook.com": "facebook.com",
             "https://www.google.com.pk/": "google.com", "https://mail.google.com/": "mail.google.com", "https://www.bing.com/": "bing.com",
             "https://t.co/x": "x.com", "https://www.surmusicradio.com/": "Direct (typed, app or bookmark)", "": "Direct (typed, app or bookmark)",
             "https://news.example.co.uk/a": "example.co.uk"}
    for ref, want in names.items():
        assert analytics.source_name(ref) == want, ref
    with app.test_request_context():
        db = get_db()
        now = analytics.datetime.now(analytics.timezone.utc).replace(microsecond=0).isoformat()
        for vid, ref in [("a", "https://m.facebook.com/"), ("b", "https://lm.facebook.com/l.php"), ("c", ""), ("d", "https://www.bing.com/"),
                         ("e", "https://www.surmusicradio.com/")]:
            db.execute("INSERT INTO events (kind, visitor_id, referrer, created_at) VALUES ('page_view', ?, ?, ?)", (vid, ref, now))
            db.execute("INSERT INTO events (kind, visitor_id, referrer, created_at) VALUES ('page_view', ?, 'https://m.facebook.com/', ?)", (vid, now))   # later pages do not count
        db.commit()
        s = analytics.summary(7)
        rows = {r["label"]: r["visitors"] for r in s["referrers"]}
        assert rows == {"facebook.com": 2, "Direct (typed, app or bookmark)": 2, "bing.com": 1}
        assert sum(rows.values()) == s["totals"]["visitors"]
