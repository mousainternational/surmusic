"""Every station and every type (naat, qawwali…) has its own page, with ads and SEO."""
import json
import re

from conftest import api, login, post


def test_genre_pages(client):
    for slug in ("naat", "qawwali", "ghazal", "sufi", "punjabi", "quran", "news", "old-songs"):
        r = client.get(f"/genre/{slug}")
        assert r.status_code == 200, slug
        html = r.get_data(as_text=True)
        assert 'rel="canonical"' in html and "Radio categories" in html and 'aria-current="page"' in html
    assert "Naat Radio" in client.get("/genre/naat").get_data(as_text=True)
    assert client.get("/genre/nothing").status_code == 404
    home = client.get("/").get_data(as_text=True)
    strip = home.split("data-nav-tabs", 1)[1].split("</nav>", 1)[0]                             # the category tabs
    assert "/genre/naat" not in strip and "/genre/quran" not in strip
    header = home.split('<nav id="menu"', 1)[1].split("</nav>", 1)[0]                           # the header menu
    assert header.count("<details") == 3 and "🌐 Language" in header and "🌍 Country" in header
    other = header.split("📻 Types", 1)[1].split("Other</h3>", 1)[1].split("</ul>", 1)[0]
    for slug in ("qawwali", "sufi", "ghazal"):                                                  # inside "Other"
        assert f'href="/genre/{slug}"' in other, slug
    assert 'href="/country/usa"' in header and 'href="/continent/europe"' in header
    for word in ("Madani", "Dawat", "Majlis", "Hadith", "Noha", "/genre/naat", "/genre/quran"):                 # all live under Islamic
        assert word not in header, word
    assert 'href="/genre/news"' in header and 'href="/blog"' in header                          # Guides is in the menu
    assert 'href="/genre/hindi"' in header and 'href="/genre/health"' in header
    assert 'class="cat-tile"' not in home                                                       # one set of buttons, not two
    assert 'id="cat-religious"' in client.get("/radio-stations").get_data(as_text=True)


def test_station_rows_link_to_own_page(client):
    html = client.get("/genre/qawwali").get_data(as_text=True)
    hrefs = re.findall(r'data-href="(/station/[^"]+)"', html)
    assert hrefs and all(re.fullmatch(r"/station/[\w-]+/[a-z0-9-]+", h) for h in hrefs)


def test_station_page(client, app):
    html = client.get("/genre/qawwali").get_data(as_text=True)
    href = re.findall(r'data-href="(/station/[^"]+)"', html)[0]
    r = client.get(href)
    assert r.status_code == 200
    page = r.get_data(as_text=True)
    name = re.search(r"<h1>([^<]+)</h1>", page).group(1)
    assert f"<title>{name} Live — Pakistan Radio Online Free" in page
    assert '"@type": "RadioStation"' in page or '"@type":"RadioStation"' in page.replace(" ", "")
    assert f'href="http://localhost{href}"' in page or href in re.search(r'rel="canonical" href="([^"]+)"', page).group(1)
    assert "More stations like" in page and "Ask us to remove it" in page
    uuid = href.split("/")[2]
    assert client.get(f"/station/{uuid}").status_code == 301                      # short link → full address
    assert client.get(f"/station/{uuid}/wrong-name").headers["Location"].endswith(href)
    assert client.get("/station/does-not-exist").status_code == 404
    # the owner removes it → the page is gone (410) everywhere
    st = json.loads(re.search(r'data-station="([^"]+)"', page).group(1).replace("&#34;", '"').replace("&quot;", '"'))
    login(client)
    post(client, "/admin/stations/block", {"uuid": st["uuid"], "url": st["url"], "name": st["name"], "back": "/"},
         page="/")
    assert app.test_client().get(href).status_code == 410


def test_sitemap_lists_genres_and_station_pages(client):
    client.get("/genre/ghazal")                                           # loads (caches) that list
    xml = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/genre/naat</loc>" in xml and "/station/" in xml


def test_station_page_share_embed_and_details(client):
    """Like the big directories: station details, share buttons and an "add to your website" player."""
    html = client.get("/genre/qawwali").get_data(as_text=True)
    href = re.findall(r'data-href="(/station/[^"]+)"', html)[0]
    page = client.get(href).get_data(as_text=True)
    uuid = href.split("/")[2]
    assert "station details" in page and "<dt>Country</dt>" in page and "Suggest an update" in page
    assert "https://wa.me/?text=" in page and "facebook.com/sharer" in page and "t.me/share" in page
    assert 'id="embed-code"' in page and f"/embed/station/{uuid}" in page
    assert "&lt;iframe" in page                                              # shown as text, not a live frame
    assert 'href="/contact?topic=update' in page
    r = client.get(f"/embed/station/{uuid}")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Listen on Sur Music" in body and href in body                     # always links back to the station page
    assert "frame-ancestors *" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Frame-Options"] != "DENY" and "noindex" in r.headers["X-Robots-Tag"]
    assert client.get("/embed/station/does-not-exist").status_code == 404
    assert client.get(href).headers["X-Frame-Options"] == "DENY"            # normal pages still cannot be framed
    subject = client.get("/contact?topic=update&station=Test+FM").get_data(as_text=True)
    assert "Station details update: Test FM" in subject


def test_station_details_from_radio_browser():
    from app import radio
    raw = [{"stationuuid": "abc-1", "name": "Test FM", "url_resolved": "https://s.example/live", "lastcheckok": 1,
            "homepage": "http://testfm.example/", "language": "urdu,punjabi", "state": "Lahore", "codec": "mp3",
            "votes": 42, "clickcount": 7, "bitrate": 128}]
    st = radio.normalize(raw)[0]
    assert st["homepage"] == "http://testfm.example/" and st["language"] == "Urdu, Punjabi"
    assert st["state"] == "Lahore" and st["codec"] == "MP3" and st["votes"] == 42
    bad = radio.normalize([dict(raw[0], homepage="javascript:alert(1)")])[0]
    assert bad["homepage"] == ""


def test_az_tab_next_to_categories_and_not_in_footer(client):
    html = client.get("/").get_data(as_text=True)
    tabs = html.split("data-nav-tabs", 1)[1].split("</nav>", 1)[0]
    assert 'data-tab="az"' in tabs and 'href="/stations/a"' in tabs and 'href="/stations/z"' in tabs and 'href="/top-100"' in tabs
    footer = html.split('<footer', 1)[1]
    assert "A–Z stations" not in footer
    assert "Radio by country" in footer and "Pakistan by province" in footer and "Sindh radio" in footer


def test_province_pages(client):
    for slug in ("punjab-pakistan", "sindh", "khyber-pakhtunkhwa", "balochistan", "maharashtra"):
        r = client.get(f"/genre/{slug}")
        assert r.status_code == 200, slug
    page = client.get("/genre/sindh").get_data(as_text=True)
    assert "Sindh Radio" in page and "Karachi" in page
    assert 'href="/genre/sindh"' in client.get("/pakistan-fm-radio").get_data(as_text=True)


def test_station_page_hides_official_website_but_keeps_it_for_search_engines(client, app):
    from app import seo
    st = {"name": "Test FM", "homepage": "http://testfm.example/", "country": "Pakistan", "state": "Lahore"}
    with app.test_request_context("/"):
        ld = seo.station_ld(st, "/station/x/test-fm")
    assert ld["sameAs"] == "http://testfm.example/" and ld["address"]["addressLocality"] == "Lahore"
    html = client.get("/genre/qawwali").get_data(as_text=True)
    href = re.findall(r'data-href="(/station/[^"]+)"', html)[0]
    assert "Official website" not in client.get(href).get_data(as_text=True)


def test_like_and_dislike_a_station(client):
    html = client.get("/genre/qawwali").get_data(as_text=True)
    href = re.findall(r'data-href="(/station/[^"]+)"', html)[0]
    uuid = href.split("/")[2]
    page = client.get(href).get_data(as_text=True)
    assert f'data-like-uuid="{uuid}"' in page and 'data-like="1"' in page and 'data-like="-1"' in page
    r = api(client, "POST", "/api/like", {"uuid": uuid, "value": 1}, page=href)
    assert r.status_code == 200 and r.get_json()["likes"] == 1
    r = api(client, "POST", "/api/like", {"uuid": uuid, "value": 1}, page=href)     # same visitor: still one vote
    assert r.get_json()["likes"] == 1
    r = api(client, "POST", "/api/like", {"uuid": uuid, "value": -1}, page=href)    # changes the vote
    assert r.get_json()["likes"] == 0 and r.get_json()["dislikes"] == 1
    r = api(client, "POST", "/api/like", {"uuid": uuid, "value": 0}, page=href)
    assert r.get_json()["dislikes"] == 0
    assert api(client, "POST", "/api/like", {"uuid": uuid, "value": 5}, page=href).status_code == 400
    assert api(client, "POST", "/api/like", {"uuid": "nope", "value": 1}, page=href).status_code == 404


def test_llms_txt_lists_provinces_directory_and_popular_stations(client):
    client.get("/genre/qawwali")                       # a station list has been loaded once
    txt = client.get("/llms.txt").get_data(as_text=True)
    assert "/top-100" in txt and "/pakistan-fm-radio" in txt and "/stations/a" in txt
    assert "Sindh radio" in txt and "Popular stations" in txt and "/station/" in txt


def test_news_tab_lists_channels_not_another_news_button(client):
    client.get("/genre/news")                       # fills the news list (demo data in tests)
    html = client.get("/").get_data(as_text=True)
    panel = html.split('data-sub="news"', 1)[1].split("</div>", 1)[0]
    assert "/station/" in panel                     # the channels themselves
    assert ">News<" not in panel                    # no second "News" button inside News
    assert "All news channels" in panel


def test_islamic_page_shows_only_islamic_topics(client):
    html = client.get("/genre/islamic").get_data(as_text=True)
    panel = html.split('data-sub="religious"', 1)[1].split("</div>", 1)[0]
    assert "Quran" in panel and "Naat" in panel
    for other in ("Christian", "Bhajan", "Gurbani", "Jewish"):
        assert other not in panel


def test_each_list_keeps_its_own_kind():
    from app.radio import _fits
    assert _fits("news", {"name": "BBC World Service", "tags": "news"})
    assert not _fits("news", {"name": "Quran Kareem Radio", "tags": "quran,news"})
    assert not _fits("news", {"name": "Radio Mirchi 98.3", "tags": "bollywood,news"})
    assert not _fits("news", {"name": "50s 60s Retro Hits", "tags": "news"})
    assert _fits("sports", {"name": "talkSPORT", "tags": "sports"})
    assert not _fits("talk", {"name": "Naat Sharif Radio", "tags": "talk"})


def test_world_directory_chunks_give_station_pages_and_sitemaps(app, client):
    import json as _json
    from app.db import get_db, utcnow
    st = {"uuid": "aaaaaaaa-1111-2222-3333-444444444444", "name": "Directory Test FM", "url": "https://example.com/s.mp3",
          "favicon": "", "country": "Kenya", "countrycode": "KE", "tags": "pop", "bitrate": 128, "clicks": 50}
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO station_cache (cache_key, body, fetched_at) VALUES (?, ?, ?)",
                   ("dir:0", _json.dumps([st]), utcnow()))
        db.commit()
    assert "Sitemap: https://surmusic.example/sitemap-stations-0.xml" in client.get("/robots.txt").get_data(as_text=True)
    xml = client.get("/sitemap-stations-0.xml").get_data(as_text=True)
    assert "/station/aaaaaaaa-1111-2222-3333-444444444444/directory-test-fm" in xml
    assert client.get("/sitemap-stations-7.xml").status_code == 404
    page = client.get("/station/aaaaaaaa-1111-2222-3333-444444444444/directory-test-fm")
    assert page.status_code == 200 and "Directory Test FM" in page.get_data(as_text=True)


def test_directory_refresh_saves_only_browser_playable_stations(app, monkeypatch):
    from app import directory, radio
    from app.db import get_db
    calls = []

    def fake(path):
        calls.append(path)
        if "offset=0" not in path:
            return []
        return [{"stationuuid": "bbbbbbbb-1111-2222-3333-444444444444", "name": "Good FM", "url_resolved": "https://x.example/a.mp3",
                 "lastcheckok": 1, "hls": 0, "clickcount": 9, "tags": "news", "country": "Kenya"},
                {"stationuuid": "cccccccc-1111-2222-3333-444444444444", "name": "Old FM", "url_resolved": "http://x.example/b.mp3",
                 "lastcheckok": 1, "hls": 0, "clickcount": 9}]
    monkeypatch.setattr(radio, "_fetch_json", fake)
    directory.refresh(app, pause=0)
    with app.app_context():
        assert directory.chunk_keys(get_db()) == ["dir:0"]
        body = get_db().one("SELECT body FROM station_cache WHERE cache_key = ?", ("dir:0",))["body"]
    assert "Good FM" in body and "Old FM" not in body
    directory.refresh(app, pause=0)                     # locked / not due: no second fetch
    assert len(calls) == 2


def test_pakistan_fm_is_on_pakistan_pages_not_in_a_to_z(client):
    home = client.get("/").get_data(as_text=True)
    az = home.split('data-sub="az"', 1)[1].split("</div>", 1)[0]
    assert "Pakistan FM" not in az and "Top 100" in az
    assert 'href="/pakistan-fm-radio"' in client.get("/country/pakistan").get_data(as_text=True)
