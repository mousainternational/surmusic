import json
import re

import pytest

from conftest import STATION, api, csrf, login, post

PAGES = ["/", "/bollywood", "/lollywood", "/hollywood", "/search", "/search?q=lahore", "/favorites", "/download",
         "/donate", "/about", "/contact", "/faq", "/privacy", "/terms", "/disclaimer", "/donation-disclaimer",
         "/cookies", "/login", "/signup", "/forgot"]


def test_pages_render(client):
    for p in PAGES:
        r = client.get(p)
        assert r.status_code == 200, p
        assert b"Mousa International Software House" in r.data, p  # MISH branding on every page


def test_404(client):
    r = client.get("/nope")
    assert r.status_code == 404 and b"Page not found" in r.data


def test_station_lists_rendered_on_server(client):
    html = client.get("/lollywood").get_data(as_text=True)
    assert "Lahore Sur FM" in html and 'data-station="' in html
    assert "Lollywood &amp; Pakistani Radio" in html


def test_security_headers_and_nonce(client):
    r = client.get("/")
    csp = r.headers["Content-Security-Policy"]
    nonce = re.search(r"'nonce-([^']+)'", csp).group(1)
    assert "frame-ancestors 'none'" in csp and "object-src 'none'" in csp
    assert r.headers["X-Frame-Options"] == "DENY" and r.headers["X-Content-Type-Options"] == "nosniff"
    html = r.get_data(as_text=True)
    for tag in re.findall(r"<script(?![^>]*application/ld\+json)[^>]*>", html):
        assert f'nonce="{nonce}"' in tag, tag
    assert client.get("/").headers["Content-Security-Policy"] != csp  # fresh nonce per request


def test_no_inline_handlers_or_styles(client):
    for p in PAGES:
        html = client.get(p).get_data(as_text=True)
        assert " style=" not in html, p
        assert "onclick=" not in html and "onerror=" not in html, p


def test_seo(client):
    html = client.get("/").get_data(as_text=True)
    assert '<link rel="canonical" href="https://surmusic.example/">' in html
    types = {json.loads(b)["@type"] for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)}
    assert {"WebSite", "WebApplication", "Organization"} <= types
    faq = client.get("/faq").get_data(as_text=True)
    assert '"FAQPage"' in faq
    titles = set()
    for p in ["/", "/bollywood", "/lollywood", "/hollywood", "/download", "/donate", "/about", "/contact", "/faq",
              "/privacy", "/terms", "/disclaimer", "/cookies"]:
        t = re.search(r"<title>(.*?)</title>", client.get(p).get_data(as_text=True)).group(1)
        assert t not in titles, t
        titles.add(t)
    assert b"noindex" in client.get("/search?q=abc").data
    assert b"noindex" in client.get("/login").data


def test_robots_sitemap_adstxt(client):
    robots = client.get("/robots.txt").get_data(as_text=True)
    assert "Disallow: /admin" in robots and "Disallow: /api/" in robots and "Sitemap: https://surmusic.example/sitemap.xml" in robots
    sm = client.get("/sitemap.xml").get_data(as_text=True)
    assert "https://surmusic.example/lollywood" in sm and "/admin" not in sm
    assert client.get("/ads.txt").get_data(as_text=True).startswith("#")


def test_healthz(client):
    assert client.get("/healthz").get_json()["status"] == "ok"


def test_api_stations_and_search(client):
    data = client.get("/api/stations/hollywood").get_json()
    # listening is free by default: visitors get playable stream URLs
    assert data["stations"] and all(s["url"].startswith("https://") for s in data["stations"])
    assert client.get("/api/search?q=hits").status_code == 200


def test_contact(client, app):
    r = post(client, "/contact", {"name": "A", "email": "bad"}, page="/contact")
    assert r.status_code == 400
    r = post(client, "/contact", {"name": "Ali", "email": "ali@example.com", "subject": "Advertising",
                                  "message": "I want to sponsor a station."}, page="/contact", follow_redirects=True)
    assert b"your message was received" in r.data
    r = post(client, "/contact", {"name": "Bot", "email": "b@example.com", "subject": "Spam spam",
                                  "message": "Spam spam spam", "website": "x"}, page="/contact")
    assert r.status_code == 400


def test_open_redirect_blocked(client):
    r = post(client, "/login?next=//evil.example", {"email": "owner@example.com", "password": "correct-horse-battery-staple"})
    assert r.status_code == 302 and r.headers["Location"] in ("/", "/admin/")


def test_play_counts_popular(client):
    login(client)
    for _ in range(3):
        assert api(client, "POST", "/api/play", {"station": STATION, "category": "lollywood"}).status_code == 200
    assert b"Popular on Sur Music" in client.get("/").data
    bad = dict(STATION, url="http://insecure.example/stream")
    assert api(client, "POST", "/api/play", {"station": bad}).status_code == 400
    assert client.post("/api/play", json={"station": STATION}).status_code == 403  # no CSRF header


def test_radio_normalize_filters():
    from app.radio import normalize
    raw = [
        {"stationuuid": "a", "name": "Good", "url_resolved": "https://x.example/a", "lastcheckok": 1, "hls": 0},
        {"stationuuid": "b", "name": "Http", "url_resolved": "http://x.example/b", "lastcheckok": 1, "hls": 0},
        {"stationuuid": "c", "name": "Broken", "url_resolved": "https://x.example/c", "lastcheckok": 0, "hls": 0},
        {"stationuuid": "d", "name": "Hls", "url_resolved": "https://x.example/d.m3u8", "lastcheckok": 1, "hls": 1},
        {"stationuuid": "a", "name": "Dup", "url_resolved": "https://x.example/a", "lastcheckok": 1, "hls": 0},
        {"stationuuid": "e", "name": "<script>x</script>", "url_resolved": "javascript:alert(1)", "lastcheckok": 1},
    ]
    out = normalize(raw)
    assert [s["uuid"] for s in out] == ["a"]


def test_radio_cache_and_stale_fallback(app, monkeypatch):
    from app import radio
    app.config["RADIO_DEMO"] = False
    calls = []

    def fake(path):
        calls.append(path)
        return [{"stationuuid": f"x{len(calls)}", "name": "Cached FM", "url_resolved": "https://s.example/1",
                 "lastcheckok": 1, "hls": 0}]
    monkeypatch.setattr(radio, "_fetch_json", fake)
    with app.test_request_context():
        first = radio.category_stations("hollywood")
        n = len(calls)
        again = radio.category_stations("hollywood")
        assert first == again and len(calls) == n  # served from cache
        from app.db import get_db
        db = get_db()
        db.execute("UPDATE station_cache SET fetched_at = '2000-01-01T00:00:00+00:00'")
        db.commit()

        def down(path):
            raise radio.RadioError("down")
        monkeypatch.setattr(radio, "_fetch_json", down)
        assert radio.category_stations("hollywood") == first  # stale data instead of an error
        with pytest.raises(radio.RadioError):
            radio.category_stations("bollywood")


def test_category_page_shows_error_gracefully(app, client, monkeypatch):
    from app import radio
    app.config["RADIO_DEMO"] = False

    def down(path):
        raise radio.RadioError("down")
    monkeypatch.setattr(radio, "_fetch_json", down)
    r = client.get("/bollywood")
    assert r.status_code == 200 and b"not reachable right now" in r.data


def test_markdown_policy_is_safe(client):
    login(client)
    post(client, "/admin/settings?section=policies", {"faq_md": "<script>alert(1)</script>\n\n[x](javascript:alert(1))",
                                                       "privacy_md": "p", "terms_md": "t", "disclaimer_md": "d",
                                                       "donation_disclaimer_md": "dd", "cookies_md": "c",
                                                       "policies_updated": "2026-10-28"}, page="/admin/settings")
    html = client.get("/faq").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html and 'href="javascript:' not in html


def test_static_urls_change_when_file_changes(client):
    """Browsers must never keep an old player.js after an update."""
    import re
    html = client.get("/").get_data(as_text=True)
    m = re.search(r'/static/js/player\.js\?v=([0-9a-f]{12})', html)
    assert m, "player.js should carry a content hash"
    assert "v=1.0.0" not in html


def test_ping_is_light(client):
    r = client.get("/ping")
    assert r.status_code == 200 and r.get_data(as_text=True) == "ok"


def test_admin_from_environment(tmp_path, monkeypatch):
    """Render free has no shell: the first admin can come from ADMIN_EMAIL / ADMIN_PASSWORD."""
    from app import create_app
    monkeypatch.setenv("SECRET_KEY", "k" * 40)
    cfg = {"DATABASE_URL": f"sqlite:///{tmp_path / 'boot.db'}", "STORAGE_DIR": str(tmp_path / "st"),
           "TESTING": True, "RADIO_DEMO": True}
    monkeypatch.setenv("ADMIN_EMAIL", "Owner@Example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "short")
    from app.db import Database
    create_app(cfg)
    db = Database(f"sqlite:///{tmp_path / 'boot.db'}")
    assert db.scalar("SELECT COUNT(*) FROM users") == 0          # weak password ignored
    monkeypatch.setenv("ADMIN_PASSWORD", "a-long-owner-password")
    create_app(cfg)
    assert db.scalar("SELECT role FROM users WHERE email = 'owner@example.com'") == "admin"
    monkeypatch.setenv("ADMIN_PASSWORD", "another-long-password")
    create_app(cfg)                                                # existing account never changed
    from werkzeug.security import check_password_hash
    h = db.scalar("SELECT password_hash FROM users WHERE email = 'owner@example.com'")
    assert check_password_hash(h, "a-long-owner-password")
    db.close()


def test_old_render_address_redirects_to_own_domain(client, app):
    app.config["SITE_URL"] = "https://surmusic.com"
    r = client.get("/bollywood?x=1", base_url="https://surmusic-vv37.onrender.com")
    assert r.status_code == 301 and r.headers["Location"] == "https://surmusic.com/bollywood?x=1"
    assert client.get("/ping", base_url="https://surmusic-vv37.onrender.com").status_code == 200
    assert client.get("/", base_url="https://surmusic.com").status_code == 200
    app.config["SITE_URL"] = "https://surmusic-vv37.onrender.com"            # before a domain: no redirect
    assert client.get("/", base_url="https://surmusic-vv37.onrender.com").status_code == 200


def test_iphone_and_share_tags(client):
    html = client.get("/").get_data(as_text=True)
    for tag in ('name="apple-mobile-web-app-title" content="Sur Music"', 'rel="apple-touch-icon"',
                'viewport-fit=cover', 'property="og:image"', 'rel="canonical"', 'application/ld+json'):
        assert tag in html, tag


def test_admin_menu_has_clear_links(client):
    from conftest import login
    login(client)
    menu = client.get("/").get_data(as_text=True)
    assert "⚙️ Admin panel" in menu and "My account" in menu and "Sign out" in menu and 'hd-dd hd-acct' in menu
    assert ">Admin</a>" not in menu


def test_android_license_allows_one_phone_per_subscription(client, app, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from app.db import Database
    token = "purchase-token-" + "x" * 40
    body = lambda install: {"token": token, "install": install}
    a, b = "phone-a-" + "1" * 16, "phone-b-" + "2" * 16
    assert client.post("/api/app/license", json=body(a)).get_json() == {"ok": True}
    assert client.post("/api/app/license", json=body(a)).status_code == 200          # same phone again
    r = client.post("/api/app/license", json=body(b))                                  # a shared copy on another phone
    assert r.status_code == 403 and r.get_json()["reason"] == "other_device"
    assert client.post("/api/app/license", json={"token": "short", "install": a}).status_code == 400
    db = Database(app.config["DATABASE_URL"])                                          # the old phone went silent for 8 days
    old = (datetime.now(timezone.utc) - timedelta(days=8)).replace(microsecond=0).isoformat()
    db.execute("UPDATE app_licenses SET last_seen = ?", (old,)); db.commit(); db.close()
    assert client.post("/api/app/license", json=body(b)).get_json() == {"ok": True}    # the new phone takes over
    assert client.post("/api/app/license", json=body(a)).status_code == 403            # and the old one is locked out


def test_privacy_policy_mentions_the_android_subscription_check(client):
    html = client.get("/privacy").get_data(as_text=True)
    assert "Android app subscription" in html and "transaction ID" in html and "sold through Google Play" not in html


def test_big_player_is_loaded_only_when_opened_and_static_files_are_cached_long(client):
    home = client.get("/").get_data(as_text=True)
    assert 'id="np"' in home and 'id="np-skin"' in home and home.count("<option") >= 15
    assert 'id="np-open"' in home and 'data-src="/static/js/nowplaying.js?v=' in home
    assert '<script nonce' in home and 'src="/static/js/nowplaying.js' not in home.split('id="np-open"')[0].split("<script")[-1]
    import re
    assert not re.search(r'<script[^>]+src="/static/js/nowplaying\.js', home)          # not on every page view
    v = re.search(r'/static/css/site\.css\?v=[0-9a-f]+', home).group(0)
    r = client.get(v)
    assert r.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert client.get("/static/css/site.css").headers["Cache-Control"] == "public, max-age=2592000"


def test_download_page_explains_how_to_install_on_iphone(client):
    html = client.get("/download").get_data(as_text=True)
    assert 'id="iphone"' in html and "Add to Home Screen" in html and "Safari" in html
    assert "APK" in html and "iPhone" in html
    assert 'rel="apple-touch-icon"' in html and 'name="apple-mobile-web-app-capable"' in html


def test_accessibility_button_in_the_header_and_its_seo(client):
    import json, re
    home = client.get("/").get_data(as_text=True)
    head = home.split("</header>")[0]
    assert 'class="a11y-btn"' in head and 'href="/accessibility"' in head and "Accessibility" in head
    assert "screen reader friendly radio" in home
    page = client.get("/accessibility").get_data(as_text=True)
    assert "blind-friendly radio" in page and "TalkBack or VoiceOver radio" in page
    kinds = [json.loads(b).get("@type") for b in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S)]
    assert "WebPage" in kinds and "BreadcrumbList" in kinds
    ld = next(json.loads(b) for b in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S) if '"WebPage"' in b)
    assert "ARIA" in ld["accessibilityFeature"] and "fullKeyboardControl" in ld["accessibilityControl"]


def test_admin_own_activity_is_not_counted_but_visitors_are(app):
    from conftest import login, signup
    from app.db import Database
    owner, visitor = app.test_client(), app.test_client()
    login(owner)                                              # the owner signs in, browses and downloads
    owner.get("/"); owner.get("/hollywood"); owner.get("/download/android")
    signup(visitor, "sara@example.com")
    visitor.get("/"); visitor.get("/hollywood")
    db = Database(app.config["DATABASE_URL"])
    admin_id = db.one("SELECT id FROM users WHERE role = 'admin'")["id"]
    assert db.scalar("SELECT COUNT(*) FROM events WHERE user_id = ?", (admin_id,)) == 0         # nothing from the owner
    assert db.scalar("SELECT COUNT(*) FROM events WHERE kind = 'signup'") == 1                   # visitors still counted
    again = app.test_client()
    login(again, "sara@example.com", "listen-to-ghazals-42")
    assert db.scalar("SELECT COUNT(*) FROM events WHERE kind = 'login'") >= 1
    db.close()


def test_old_admin_events_are_removed_once_at_start(tmp_path, monkeypatch):
    from app import db as dbmod
    from app.db import Database, utcnow
    url = f"sqlite:///{tmp_path / 'x.db'}"
    dbmod.migrate(url)
    d = Database(url)
    d.execute("INSERT INTO users (email, password_hash, role, display_name, created_at, is_active) VALUES ('a@x.com', 'h', 'admin', 'A', ?, 1)", (utcnow(),))
    d.execute("INSERT INTO users (email, password_hash, role, display_name, created_at, is_active) VALUES ('b@x.com', 'h', 'user', 'B', ?, 1)", (utcnow(),))
    d.execute("DELETE FROM schema_migrations WHERE version = 2")
    for uid, kind in ((1, "login"), (1, "page_view"), (1, "login_failed"), (2, "login")):
        d.execute("INSERT INTO events (kind, visitor_id, user_id, created_at) VALUES (?, 'v', ?, ?)", (kind, uid, utcnow()))
    d.commit(); d.close()
    dbmod.migrate(url)
    d = Database(url)
    kinds = sorted((r["user_id"], r["kind"]) for r in d.all("SELECT user_id, kind FROM events"))
    assert kinds == [(1, "login_failed"), (2, "login")]
    d.close()


def test_app_ads_txt_matches_ads_txt(client):
    a, b = client.get("/ads.txt"), client.get("/app-ads.txt")
    assert b.status_code == 200 and b.get_data() == a.get_data() and b.mimetype == "text/plain"
