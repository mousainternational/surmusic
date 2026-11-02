"""Sign-in-to-listen gate and admin activity / location tracking."""
import gzip
import json
import os
import re
import shutil

from conftest import STATION, USER_PASSWORD, api, login, post, signup

CHROME_ANDROID = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/130.0 Mobile Safari/537.36")
CHROME_WINDOWS = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/130.0 Safari/537.36")


# ---------------------------------------------------------------- gate

def _gate_on(app):
    a = app.test_client()
    login(a)
    post(a, "/admin/settings?section=accounts", {"signup_enabled": "1", "play_requires_login": "1"},
         page="/admin/settings")


def test_free_listening_by_default(client, app):
    html = client.get("/hollywood").get_data(as_text=True)
    assert "stream.example.com" in html and 'data-locked="0"' in html and 'id="login-gate"' not in html
    assert api(client, "POST", "/api/play", {"station": STATION}).status_code == 200
    ev = _events(app)
    assert any(e["kind"] == "play" and e["user_id"] is None for e in ev)       # guest play still counted


def test_old_saved_gate_is_switched_off_once(tmp_path, monkeypatch):
    """Owners who had 'sign in to listen' saved get free listening after the update — but can turn it on again."""
    from app import create_app
    from app.db import Database
    monkeypatch.setenv("SECRET_KEY", "k" * 40)
    cfg = {"DATABASE_URL": f"sqlite:///{tmp_path / 'g.db'}", "STORAGE_DIR": str(tmp_path / "st"),
           "TESTING": True, "RADIO_DEMO": True}
    create_app(cfg)
    db = Database(cfg["DATABASE_URL"])
    db.execute("DELETE FROM settings WHERE key LIKE '_done_%'")
    db.execute("INSERT INTO settings (key, value) VALUES ('play_requires_login', '1')")
    db.commit()
    create_app(cfg)
    assert db.scalar("SELECT COUNT(*) FROM settings WHERE key = 'play_requires_login'") == 0
    db.execute("INSERT INTO settings (key, value) VALUES ('play_requires_login', '1')")   # owner turns it on again
    db.commit()
    create_app(cfg)
    assert db.scalar("SELECT value FROM settings WHERE key = 'play_requires_login'") == "1"
    db.close()


def test_guests_cannot_get_stream_urls_when_gate_on(client, app):
    _gate_on(app)
    html = client.get("/hollywood").get_data(as_text=True)
    assert "stream.example.com" not in html          # no playable links in the page source
    assert 'data-locked="1"' in html and 'id="login-gate"' in html
    station = client.get("/api/stations/hollywood").get_json()["stations"][0]
    assert api(client, "POST", "/api/stream", {"station": station}).status_code == 401
    assert api(client, "POST", "/api/play", {"station": station}).status_code == 401
    signup(client)
    r = api(client, "POST", "/api/stream", {"station": station})
    assert r.status_code == 200 and r.get_json()["url"].startswith("https://stream.example.com/")
    member_html = client.get("/hollywood").get_data(as_text=True)
    assert "stream.example.com" in member_html and 'data-locked="0"' in member_html
    # tampered token is rejected
    bad = dict(station, token=station["token"][:-4] + "AAAA")
    assert api(client, "POST", "/api/stream", {"station": bad}).status_code == 400


def test_gate_can_be_switched_off(client, app):
    _gate_on(app)
    a = app.test_client()
    login(a)
    post(a, "/admin/settings?section=accounts", {"signup_enabled": "1"}, page="/admin/settings")
    html = client.get("/hollywood").get_data(as_text=True)
    assert "stream.example.com" in html and 'data-locked="0"' in html
    assert api(client, "POST", "/api/play", {"station": STATION}).status_code == 200


def test_signup_returns_to_page(client):
    r = post(client, "/signup?next=/lollywood", {"email": "z@example.com", "password": USER_PASSWORD,
                                                 "password2": USER_PASSWORD, "agree": "1"}, page="/signup")
    assert r.status_code == 302 and r.headers["Location"].endswith("/lollywood")
    r = post(client, "/signup?next=https://evil.example", {}, page="/")  # already signed in → safe default
    assert r.headers["Location"] in ("/", "http://localhost/")


# ---------------------------------------------------------------- events

def _events(app):
    with app.app_context():
        from app.db import Database
        db = Database(app.config["DATABASE_URL"])
        rows = db.all("SELECT * FROM events ORDER BY id")
        db.close()
        return rows


def test_account_events_recorded(client, app):
    client.environ_base["HTTP_USER_AGENT"] = CHROME_ANDROID
    signup(client)
    post(client, "/logout", page="/")
    login(client, "sara@example.com", "wrong-password-1")
    login(client, "sara@example.com", USER_PASSWORD)
    kinds = [e["kind"] for e in _events(app)]
    assert kinds[:4] == ["signup", "logout", "login_failed", "login"]
    ev = _events(app)[0]
    assert (ev["device"], ev["browser"], ev["os"]) == ("Mobile", "Chrome", "Android")
    assert ev["user_id"] == 2


def test_bots_are_not_counted(client, app):
    client.environ_base["HTTP_USER_AGENT"] = "Googlebot/2.1 (+http://www.google.com/bot.html)"
    api(client, "POST", "/api/track", {"path": "/", "tz": "Asia/Karachi"})
    assert _events(app) == []


def test_page_view_with_timezone_country(client, app):
    client.environ_base["HTTP_USER_AGENT"] = CHROME_WINDOWS
    api(client, "POST", "/api/track", {"path": "/lollywood", "tz": "Asia/Karachi", "ref": "https://www.google.com/"})
    ev = _events(app)[-1]
    assert (ev["kind"], ev["path"], ev["country"], ev["referrer"]) == ("page_view", "/lollywood", "PK", "google.com")
    assert ev["region"] == ""  # a time zone gives the country only, never a made-up city
    api(client, "POST", "/api/track", {"path": "/admin/", "tz": "Asia/Karachi"})  # admin pages ignored
    assert len(_events(app)) == 1


def test_live_listeners_and_duration(client, app):
    client.environ_base["HTTP_USER_AGENT"] = CHROME_ANDROID
    signup(client)
    api(client, "POST", "/api/track", {"path": "/", "tz": "Asia/Karachi"})
    api(client, "POST", "/api/heartbeat", {"station_name": "Lahore Sur FM", "category": "lollywood"})
    a = app.test_client()
    login(a)
    live = a.get("/admin/live.json").get_json()
    assert live["listening"] == 1
    row = live["rows"][0]
    assert row["who"] == "Sara" and row["station"] == "Lahore Sur FM" and row["place"] == "Pakistan"
    assert row["device"] == "Mobile"
    assert "Lahore Sur FM" in a.get("/admin/live").get_data(as_text=True)
    # pretend they listened for 20 minutes, then stopped
    with app.app_context():
        from app.db import Database
        db = Database(app.config["DATABASE_URL"])
        db.execute("UPDATE live_sessions SET started_at = '2026-01-01T10:00:00+00:00', "
                   "last_seen = '2026-01-01T10:20:00+00:00'")
        db.commit()
        db.close()
    api(client, "POST", "/api/heartbeat", {"stop": True})
    assert a.get("/admin/live.json").get_json()["listening"] == 0
    listened = [e for e in _events(app) if e["kind"] == "listened"]
    assert listened and listened[0]["detail"] == "Lahore Sur FM · 21 min"
    assert b"21" in a.get("/admin/users/2").data  # minutes on the user page
    assert b"Minutes listened" in client.get("/account").data


def test_admin_tracking_pages(client, app):
    client.environ_base["HTTP_USER_AGENT"] = CHROME_WINDOWS
    signup(client)
    api(client, "POST", "/api/track", {"path": "/bollywood", "tz": "Asia/Dubai"})
    api(client, "POST", "/api/play", {"station": STATION, "category": "lollywood"})
    a = app.test_client()
    login(a)
    for path in ["/admin/", "/admin/live", "/admin/analytics", "/admin/analytics?days=30", "/admin/activity",
                 "/admin/activity?kind=signup", "/admin/users", "/admin/users/2"]:
        r = a.get(path)
        assert r.status_code == 200, path
    html = a.get("/admin/activity").get_data(as_text=True)
    assert "Signed up" in html and "Played a station" in html and "Lahore Sur FM" in html
    assert "🇦🇪" in a.get("/admin/analytics").get_data(as_text=True)
    assert "sara@example.com" in a.get("/admin/").get_data(as_text=True) or \
        "Sara" in a.get("/admin/").get_data(as_text=True)
    signup_page = a.get("/admin/users/2").get_data(as_text=True)
    assert "Windows" in signup_page and "Chrome" in signup_page


def test_account_shows_recent_signins(client, app):
    signup(client)
    post(client, "/logout", page="/")
    login(client, "sara@example.com", USER_PASSWORD)
    assert b"Recent sign-ins" in client.get("/account").data


def test_deleting_account_anonymizes_events(client, app):
    signup(client)
    post(client, "/account/delete", {"password": USER_PASSWORD}, page="/account")
    assert all(e["user_id"] is None for e in _events(app))


# ---------------------------------------------------------------- GeoIP database (city level)

def test_geoip_import_and_city_lookup(app, tmp_path):
    from app import geo
    csv_gz = tmp_path / "dbip-city-lite-test.csv.gz"
    with gzip.open(csv_gz, "wt", encoding="utf-8") as f:
        f.write("ip_start,ip_end,continent,country,stateprov,city,latitude,longitude\n")  # tolerated header
        f.write('203.0.113.0,203.0.113.255,AS,PK,Punjab,"Lahore",31.55,74.34\n')
        f.write('198.51.100.0,198.51.100.255,AS,AE,Dubai,"Dubai",25.2,55.27\n')
        f.write('2001:db8::,2001:db8::ffff,AS,IN,Maharashtra,"Mumbai",19.07,72.87\n')
    dest = str(tmp_path / "geoip.sqlite")
    assert geo.import_csv(str(csv_gz), dest) == 3
    app.config["GEOIP_DB"] = dest
    with app.test_request_context():
        assert geo.lookup("203.0.113.77") == {"country": "PK", "region": "Punjab", "city": "Lahore"}
        assert geo.lookup("2001:db8::42")["city"] == "Mumbai"
        assert geo.lookup("192.0.2.1")["country"] == ""
        assert geo.place("PK", "Punjab", "Lahore") == "Lahore, Punjab, Pakistan"


def test_city_appears_in_admin(client, app, tmp_path):
    from app import geo
    csv_path = tmp_path / "c.csv"
    csv_path.write_text('203.0.113.0,203.0.113.255,AS,PK,Punjab,"Lahore",31.5,74.3\n')
    app.config["GEOIP_DB"] = str(tmp_path / "geoip.sqlite")
    geo.import_csv(str(csv_path), app.config["GEOIP_DB"])
    client.environ_base.update(REMOTE_ADDR="203.0.113.9", HTTP_USER_AGENT=CHROME_ANDROID)
    signup(client)
    api(client, "POST", "/api/heartbeat", {"station_name": "Lahore Sur FM", "category": "lollywood"})
    a = app.test_client()
    login(a)
    assert a.get("/admin/live.json").get_json()["rows"][0]["place"] == "Lahore, Pakistan"
    assert "Lahore" in a.get("/admin/activity").get_data(as_text=True)
    assert b"IP Geolocation by DB-IP" in client.get("/").data  # licence attribution shown


def test_cloudflare_headers_only_when_trusted(client, app):
    client.environ_base.update(HTTP_CF_IPCOUNTRY="AE", HTTP_CF_IPCITY="Dubai", HTTP_USER_AGENT=CHROME_WINDOWS)
    api(client, "POST", "/api/track", {"path": "/"})
    assert _events(app)[-1]["country"] == ""          # spoofable header ignored by default
    app.config["TRUST_CF_HEADERS"] = True
    api(client, "POST", "/api/track", {"path": "/"})
    assert (_events(app)[-1]["country"], _events(app)[-1]["region"]) == ("AE", "Dubai")


def test_retention_purge(client, app):
    api(client, "POST", "/api/track", {"path": "/", "tz": "Asia/Karachi"})
    with app.app_context():
        from app.db import Database
        db = Database(app.config["DATABASE_URL"])
        db.execute("UPDATE events SET created_at = '2020-01-01T00:00:00+00:00'")
        db.commit()
        db.close()
    a = app.test_client()
    login(a)
    a.get("/admin/")  # dashboard runs the purge
    assert [e["kind"] for e in _events(app)] == ["login"]


# ---------------------------------------------------------------- city database (.mmdb) and Cloudflare Tunnel

MMDB = os.path.join(os.path.dirname(__file__), "data", "GeoIP2-City-Test.mmdb")


def test_mmdb_city_lookup(app, tmp_path):
    """Official MaxMind test database: 81.2.69.142 = London, 89.160.20.112 = Linköping (Östergötland)."""
    from app import geo
    dest = tmp_path / "dbip-city-lite.mmdb"
    shutil.copy(MMDB, dest)
    app.config["GEOIP_MMDB"] = str(dest)
    with app.test_request_context("/"):
        assert geo.available()
        assert geo.lookup("81.2.69.142") == {"country": "GB", "region": "England", "city": "London"}
        sw = geo.lookup("89.160.20.112")
        assert sw["country"] == "SE" and sw["city"] == "Linköping" and sw["region"] == "Östergötland County"
        assert geo.lookup("2001:218::1")["country"] == "JP"
        assert geo.lookup("127.0.0.1")["city"] == "Local network"


def test_visitor_city_through_cloudflare_tunnel(client, app, tmp_path):
    """cloudflared on the same computer: the visitor's real IP comes in CF-Connecting-IP."""
    dest = tmp_path / "dbip-city-lite.mmdb"
    shutil.copy(MMDB, dest)
    app.config["GEOIP_MMDB"] = str(dest)
    tunnel = {"CF-Connecting-IP": "81.2.69.142", "CF-IPCountry": "GB"}
    api(client, "POST", "/api/play", {"station": STATION}, headers=tunnel, environ_base={"REMOTE_ADDR": "127.0.0.1"})
    ev = [e for e in _events(app) if e["kind"] == "play"][-1]
    assert ev["country"] == "GB" and ev["region"] == "London"
    # the same header from a NON-local address is ignored (cannot be faked from the internet)
    api(client, "POST", "/api/play", {"station": STATION}, headers={"CF-Connecting-IP": "81.2.69.142"},
        environ_base={"REMOTE_ADDR": "203.0.113.9"})
    ev = [e for e in _events(app) if e["kind"] == "play"][-1]
    assert ev["region"] != "London"


def test_monthly_download(tmp_path):
    """Download (current month, falling back to last month), gunzip, validate, replace atomically."""
    import io as _io
    from app import geo
    data = open(MMDB, "rb").read()
    asked = []

    class Resp(_io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): self.close()

    def opener(req, timeout=0):
        asked.append(req.full_url)
        if len(asked) == 1:
            raise OSError("HTTP 404: this month's file is not published yet")
        return Resp(gzip.compress(data))

    dest = str(tmp_path / "geo" / "dbip-city-lite.mmdb")
    assert geo.update_mmdb(dest, "https://example.test/dbip-city-lite-{month}.mmdb.gz", opener=opener) == "updated"
    assert len(asked) == 2 and asked[0] != asked[1]
    assert geo.read_status(dest)["state"] == "ready"
    assert not os.path.exists(dest + ".lock") and not os.path.exists(dest + ".part")
    assert geo.update_mmdb(dest, "unused", opener=opener) == "fresh"            # not again within a month

    bad = str(tmp_path / "bad" / "x.mmdb")
    assert geo.update_mmdb(bad, "https://example.test/{month}.mmdb.gz",
                           opener=lambda req, timeout=0: Resp(gzip.compress(b"not a database"))) == "failed"
    assert not os.path.exists(bad) and geo.read_status(bad)["state"] == "failed"



def test_dashboard_tells_owner_about_city_database(client, app, tmp_path):
    app.config.update(GEOIP_AUTO=True, GEOIP_MMDB=str(tmp_path / "none.mmdb"), GEOIP_DB=str(tmp_path / "none.sqlite"))
    login(client)
    assert "downloading in the background" in client.get("/admin/").get_data(as_text=True)
    shutil.copy(MMDB, tmp_path / "none.mmdb")
    html = client.get("/admin/").get_data(as_text=True)
    assert "downloading in the background" not in html and "IP Geolocation by DB-IP" in client.get("/").get_data(as_text=True)


def test_visitor_city_on_render(client, app, tmp_path):
    """On Render (Cloudflare in front): city and country come from True-Client-IP, so every visitor is no longer
    'Unknown' and visitors no longer share one rate-limit bucket."""
    dest = tmp_path / "dbip-city-lite.mmdb"
    shutil.copy(MMDB, dest)
    app.config["GEOIP_MMDB"] = str(dest)
    app.config["BEHIND_CLOUDFLARE"] = True
    render = {"X-Forwarded-For": "81.2.69.142, 104.22.17.40", "True-Client-IP": "81.2.69.142",
              "CF-Connecting-IP": "81.2.69.142"}
    api(client, "POST", "/api/play", {"station": STATION}, headers=render, environ_base={"REMOTE_ADDR": "10.21.157.68"})
    ev = [e for e in _events(app) if e["kind"] == "play"][-1]
    assert ev["country"] == "GB" and ev["region"] == "London"
