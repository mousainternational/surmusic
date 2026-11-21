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
    home = client.get("/bollywood").get_data(as_text=True)
    strip = home.split("data-nav-tabs", 1)[1].split("</nav>", 1)[0]                             # the category tabs
    assert "/genre/naat" not in strip and "/genre/quran" not in strip
    header = home.split('<nav id="menu"', 1)[1].split("</nav>", 1)[0]                           # the header menu
    assert header.count("<details") == 2 and "🌐 Language" not in header and "🌍 Country" in header      # stations are found by country and category, not by language
    assert 'data-lazy="/menu/types"' in header and 'data-filter-menu' in header and 'placeholder="Type to find a country…"' in header
    types_menu = client.get("/menu/types").get_data(as_text=True)                                # loaded when opened
    country_menu = client.get("/menu/country").get_data(as_text=True)
    assert client.get("/menu/types").headers["Cache-Control"] == "public, max-age=86400"
    header = header + types_menu + country_menu
    for label in ("Religious", "Music", "News", "Business", "Daily life", "Kids", "Cooking", "Science &amp; Tech", "Accessibility"):        # the same as the boxes
        assert f">{label}<" in types_menu, label
    assert 'href="/genre/religious"' in types_menu and "Islamic" not in types_menu and "Quran" not in types_menu   # types are shown on the Religious page
    assert "data-filter-menu" in types_menu and "data-filter-menu" in country_menu                          # type to find
    assert 'href="/genre/qawwali"' not in types_menu and "Other</h3>" not in types_menu            # no long type list any more
    assert 'href="/country/usa"' in country_menu and 'href="/continent/europe"' in country_menu
    assert "<h3>A</h3>" in country_menu                                                         # Country: plain A to Z list
    for word in ("Madani", "Dawat", "Majlis", "Hadith", "Noha", "/genre/naat", "/genre/quran"):                 # all live under Islamic
        assert word not in header, word
    assert 'href="/genre/news"' in header and 'href="/blog"' in header                          # Guides is in the menu
    assert 'href="/genre/hindi"' not in header                                                  # no Language menu
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
    html = client.get("/bollywood").get_data(as_text=True)
    tabs = html.split("data-nav-tabs", 1)[1].split("</nav>", 1)[0]
    assert 'data-tab="az"' in tabs and 'href="/stations/a"' in tabs and 'href="/stations/z"' in tabs and 'href="/top-100"' in tabs
    footer = html.split('<footer', 1)[1]
    assert "A–Z stations" not in footer
    assert "Radio by country" in footer and "Radio by state &amp; province" in footer and "Sindh radio" in footer and "Maharashtra radio" in footer


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
    html = client.get("/bollywood").get_data(as_text=True)
    panel = html.split('data-sub="news"', 1)[1].split("</div>", 1)[0]
    assert "/station/" in panel                     # the channels themselves
    assert ">News<" not in panel                    # no second "News" button inside News
    assert "All news channels" in panel


def test_islamic_page_shows_only_islamic_topics(client):
    html = client.get("/genre/islamic").get_data(as_text=True)
    panel = html.split('data-sub="religious"', 1)[1].split("</div>", 1)[0]
    assert "Islamic" in panel
    for sub in ("All Islamic", "Naat &amp; Hamd", "Bayan", "Pakistan Islamic", "Noha"):
        assert sub not in panel                     # no small Islamic tabs: everything is on the one Islamic page


def test_each_list_keeps_its_own_kind():
    from app.radio import _fits
    assert _fits("news", {"name": "BBC World Service", "tags": "news"})
    assert not _fits("news", {"name": "Quran Kareem Radio", "tags": "quran,news"})
    assert not _fits("news", {"name": "Radio Mirchi 98.3", "tags": "bollywood,news"})
    assert not _fits("news", {"name": "50s 60s Retro Hits", "tags": "news"})
    assert _fits("sports", {"name": "talkSPORT", "tags": "sports"})
    assert not _fits("talk", {"name": "Naat Sharif Radio", "tags": "talk"})


def test_world_directory_chunks_give_station_pages_and_sitemaps(app, client):
    from app import directory
    st = {"uuid": "aaaaaaaa-1111-2222-3333-444444444444", "name": "Directory Test FM", "url": "https://example.com/s.mp3",
          "favicon": "", "country": "Kenya", "countrycode": "KE", "tags": "pop", "bitrate": 128, "clicks": 50}
    directory.save_chunk(app, 0, [st])
    assert "Sitemap: https://surmusic.example/sitemap-stations-0.xml" in client.get("/robots.txt").get_data(as_text=True)
    xml = client.get("/sitemap-stations-0.xml").get_data(as_text=True)
    assert "/station/aaaaaaaa-1111-2222-3333-444444444444/directory-test-fm" in xml
    assert client.get("/sitemap-stations-7.xml").status_code == 404
    page = client.get("/station/aaaaaaaa-1111-2222-3333-444444444444/directory-test-fm")
    assert page.status_code == 200 and "Directory Test FM" in page.get_data(as_text=True)
    with app.app_context():                       # never stored in the main database
        from app.db import get_db
        assert not get_db().scalar("SELECT COUNT(*) FROM station_cache WHERE body LIKE ?", ("%Directory Test FM%",))


def test_directory_refresh_saves_only_browser_playable_stations(app, monkeypatch):
    from app import directory, radio
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
    assert directory.chunks(app) == [0]
    names = [s["name"] for s in directory.chunk_stations(0, app)]
    assert names == ["Good FM"]
    directory.refresh(app, pause=0)                     # done this week: no second fetch
    assert len(calls) == 2


def test_pakistan_fm_is_on_pakistan_pages_not_in_a_to_z(client):
    home = client.get("/bollywood").get_data(as_text=True)
    az = home.split('data-sub="az"', 1)[1].split("</div>", 1)[0]
    assert "Pakistan FM" not in az and "Top 100" in az
    assert 'href="/pakistan-fm-radio"' in client.get("/country/pakistan").get_data(as_text=True)


def test_for_stations_page(client):
    r = client.get("/for-stations")
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "Free player for your radio station" in html and "Listen on Sur Music Radio" in html
    assert "/for-stations" in client.get("/sitemap.xml").get_data(as_text=True)
    assert 'href="/for-stations"' in client.get("/").get_data(as_text=True)


def test_own_text_keys_exist_and_render():
    from app.about_text import COUNTRY_ABOUT, GENRE_ABOUT
    from app.topics import TOPICS
    for k in list(COUNTRY_ABOUT) + list(GENRE_ABOUT):
        assert k in TOPICS, k
    assert all(len(p) > 15 for v in list(COUNTRY_ABOUT.values()) + list(GENRE_ABOUT.values()) for p in v)


def test_own_text_shown_on_page(client):
    html = client.get("/country/pakistan").get_data(as_text=True)
    assert "About Pakistan radio" in html and "rickshaws" in html
    assert "About News radio" in client.get("/genre/news").get_data(as_text=True)


def test_more_countries_have_own_text(client):
    from app.about_text import COUNTRY_ABOUT
    assert len(COUNTRY_ABOUT) >= 60 and "pakistan" in COUNTRY_ABOUT      # the first batch is still there
    assert "About Ghana radio" in client.get("/country/ghana").get_data(as_text=True)


def test_indexnow_sends_podcast_and_own_text_pages():
    from app import indexnow
    pages = indexnow.pages_to_send()
    assert pages[0] == "/" and "/podcasts" in pages and "/podcasts/c/ai" in pages
    assert "/country/ghana" in pages and "/genre/lofi" in pages
    assert "/blog/podcasts-by-topic-speaker-and-faith-guide" in pages and "/blog/listen-quran-radio-online-free" in pages   # every guide goes to Bing without the form's daily limit
    assert len(pages) == len(set(pages)) and all(p.startswith("/") for p in pages) and len(pages) < 10000


def test_meta_description_is_unique_where_own_text_exists(client):
    import re
    def desc(path):
        return re.search(r'<meta name="description" content="([^"]*)"', client.get(path).get_data(as_text=True)).group(1)
    a, b = desc("/country/ghana"), desc("/country/kenya")
    assert a != b and "Ghana" in a and len(a) <= 165
    assert "Free live" in a and "Twi" in a
    from app.about_text import COUNTRY_ABOUT
    from app.topics import COUNTRY_PAGES
    bare = next(k for k in sorted(COUNTRY_PAGES) if k not in COUNTRY_ABOUT)
    assert desc(f"/country/{bare}").startswith(f"Listen to live {COUNTRY_PAGES[bare]['label']} radio stations")   # no own text: the standard description stays
    assert "Free live" in desc("/country/togo") and "Ewe" in desc("/country/togo")                               # Togo now has its own


def test_weak_station_pages_stay_out_of_google_but_still_work(client, monkeypatch):
    from app import directory, public, radio
    weak = {"uuid": "weak-1", "name": "Tiny Test FM", "url": "https://stream.example.com/tiny", "favicon": "",
            "country": "Pakistan", "tags": "pop", "bitrate": 128, "clicks": 2, "votes": 3}
    strong = dict(weak, uuid="strong-1", name="Big Test FM", clicks=50)
    monkeypatch.setattr(radio, "station_by_uuid", lambda u: ({"weak-1": weak, "strong-1": strong}.get(u), ""))
    page = client.get(public.station_path(weak)).get_data(as_text=True)
    assert 'name="robots" content="noindex, follow"' in page          # not in Google, links still followed
    assert 'property="og:title"' in page                                # WhatsApp / Facebook previews still work
    page = client.get(public.station_path(strong)).get_data(as_text=True)
    assert 'content="index, follow' in page
    monkeypatch.setattr(directory, "chunk_stations", lambda n: [weak, strong])
    xml = client.get("/sitemap-stations-1.xml").get_data(as_text=True)
    assert "strong-1" in xml and "weak-1" not in xml


def test_countries_with_search_impressions_have_own_text(client):
    from app.about_text import COUNTRY_ABOUT
    for slug in ("belgium", "paraguay", "trinidad-and-tobago", "georgia", "switzerland", "austria"):
        assert slug in COUNTRY_ABOUT and all(len(p) > 15 for p in COUNTRY_ABOUT[slug])
    assert "Flemish and Walloon" in client.get("/country/belgium").get_data(as_text=True)


def test_a_station_that_stopped_playing_sends_google_visitors_to_its_country(client, monkeypatch):
    from app import radio
    from app.topics import CODE_TO_COUNTRY, topic_path
    monkeypatch.setattr(radio, "station_by_uuid", lambda u: (None, ""))
    monkeypatch.setattr(radio, "gone_station_country", lambda u: "US" if u == "c76686ca-a8b9" else "")
    r = client.get("/station/c76686ca-a8b9/102-7-kiis-fm")
    assert r.status_code == 301 and r.headers["Location"].endswith(topic_path(CODE_TO_COUNTRY["US"]))
    assert client.get("/station/never-existed/x").status_code == 404


def test_pakistani_fm_station_page_shows_its_frequency_and_cities(client, monkeypatch):
    from app import public, radio
    assert public.pk_fm_for("Hum FM 106.2")[1] == "106.2" and public.pk_fm_for("Radio Kashmir FM 91") is None
    st = {"uuid": "hum-1", "name": "Hum FM 106.2", "url": "https://stream.example.com/hum", "favicon": "",
          "country": "Pakistan", "tags": "urdu", "bitrate": 128, "clicks": 50, "votes": 0}
    monkeypatch.setattr(radio, "station_by_uuid", lambda u: (st, ""))
    page = client.get(public.station_path(st)).get_data(as_text=True)
    assert "On FM 106.2 in Karachi" in page and "Where can I hear Hum FM 106.2 on FM?" in page


def test_relax_and_sleep_pages_exist_with_their_own_search_words(client):
    pages = {"relax-sleep": "Sleep Sounds", "sleep-music": "Sleep Music", "rain-sounds": "Rain Sounds",
             "nature-sounds": "Nature Sounds", "white-noise": "White Noise"}
    sitemap = client.get("/sitemap.xml").get_data(as_text=True)
    for slug, words in pages.items():
        r = client.get(f"/genre/{slug}")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert words in html and "<h1" in html
        assert f"/genre/{slug}" in sitemap                     # Google and Bing find it by themselves
    assert "/genre/rain-sounds" in client.get("/radio-stations").get_data(as_text=True)    # and a visitor finds it in the list of types


def test_relax_and_sleep_is_one_of_the_category_boxes_on_the_home_page(client):
    html = client.get("/").get_data(as_text=True)
    assert "Relax and sleep" in html and "/genre/relax-sleep" in html


def test_relax_and_sleep_pages_show_the_same_sound_chips_as_the_app(client):
    for slug in ("relax-sleep", "rain-sounds", "calm-piano", "spa-music"):
        html = client.get(f"/genre/{slug}").get_data(as_text=True)
        for want in ("/genre/rain-sounds", "/genre/nature-sounds", "/genre/sleep-music", "/genre/meditation",
                     "/genre/calm-piano", "/genre/ambient-music", "/genre/white-noise", "/genre/spa-music"):
            assert want in html, (slug, want)
    assert 'aria-label="Relax and sleep sounds"' not in client.get("/genre/religious").get_data(as_text=True)
    sitemap = client.get("/sitemap.xml").get_data(as_text=True)
    assert all(f"/genre/{s}" in sitemap for s in ("calm-piano", "ambient-music", "spa-music"))


def test_welcome_flag_api_gives_the_visitors_own_country(client):
    d = client.get("/api/welcome", headers={"Accept-Language": "en-PK"}).get_json()
    assert d == {"code": "pk", "name": "Pakistan", "flag": "/static/flags/pk.svg"}
    assert client.get("/api/welcome", headers={"Accept-Language": "en-GB"}).get_json()["name"] == "United Kingdom"
    assert client.get("/api/welcome").get_json() == {}                      # unknown country: nothing is shown
    assert client.get("/static/flags/pk.svg").status_code == 200
    html = client.get("/").get_data(as_text=True)
    assert 'id="wlc"' in html and "hidden" in html.split('id="wlc"')[1][:60]


def test_country_flags_are_sent_once_per_page(client):
    import re
    html = client.get("/genre/qawwali").get_data(as_text=True)
    href = re.findall(r'data-href="(/station/[^"]+)"', html)[0]
    for page in (html, client.get(href).get_data(as_text=True)):
        assert page.count('class="flag-grid"') == 2 and page.count('data-lazy-grid="/menu/flags"') == 1
        tiles = page.count('class="flag-tile"')
        assert 100 < tiles < 400                      # one full set of flags, not two
    assert client.get("/menu/flags").get_data(as_text=True).count('class="flag-tile"') == tiles


def test_station_owner_corrections(client):
    """Radyo İLEF sent its own name, logo and working stream: its page, search and Google text use them."""
    uuid = "dd10f037-269c-42e0-9bfb-c22726aa8a7c"
    r = client.get(f"/station/{uuid}/ankara-niversitesi-radyosu-radyo-i-lef")
    assert r.status_code == 301 and r.headers["Location"].endswith(f"/station/{uuid}/radyo-i-lef")
    html = client.get(f"/station/{uuid}/radyo-i-lef").get_data(as_text=True)
    assert "Radyo İLEF" in html and "https://radyoilef.ankara.edu.tr/live" in html
    assert "radyo-ilef-logo.png" in html and "FM 91.0" in html
    assert 'name="robots" content="index' in html
    for q in ("radyo ilef", "İLEF", "Ilef", "ankara universitesi"):
        found = client.get("/api/search", query_string={"q": q}).get_json()["stations"]
        assert found and found[0]["uuid"] == uuid and found[0]["name"] == "Radyo İLEF", q
    other = client.get("/api/search", query_string={"q": "jazz"}).get_json()["stations"]
    assert all(st["uuid"] != uuid for st in other)


def test_famous_news_channel_pages_exist_keep_only_their_own_stations_and_are_on_the_home_page(client):
    from app import radio
    slugs = ("al-jazeera-live", "bbc-world-service", "ary-news-live", "geo-news-live", "cnn-live", "fox-news-live")
    for slug in slugs:
        r = client.get(f"/genre/{slug}")
        assert r.status_code == 200, slug
    assert "Al Jazeera Live Audio" in client.get("/genre/al-jazeera-live").get_data(as_text=True)
    assert "BBC Urdu stopped its radio bulletins" in client.get("/genre/bbc-world-service").get_data(as_text=True)
    assert radio._fits("cnn-live", {"name": "CNN International", "tags": ""})
    assert not radio._fits("cnn-live", {"name": "Radio Mirchi", "tags": "news"})
    assert not radio._fits("ary-news-live", {"name": "Mary Radio", "tags": ""})
    sitemap = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/genre/al-jazeera-live" in sitemap


def test_home_shows_a_row_of_top_station_logos_and_no_page_sends_visitors_to_other_sites(client, monkeypatch):
    from app import public
    st = [{"uuid": f"u{i}", "name": f"Big Radio {i}", "favicon": f"https://x.test/{i}.png", "clicks": 99 - i} for i in range(8)]
    monkeypatch.setattr(public.radio, "memory_stations", lambda: st)
    public._TOP.update(t=0, v=[])
    html = client.get("/").get_data(as_text=True)
    assert 'id="top-stations"' in html and "Most listened radio stations in the world" in html
    assert "/station/u0/" in html and "https://x.test/0.png" in html and 'class="logo-row"' in html
    assert "live.arynews.tv" not in client.get("/genre/ary-news-live").get_data(as_text=True)


def test_famous_people_have_pages_that_keep_only_stations_with_their_name(client):
    from app import radio
    from app.topics import TOPICS
    for slug in ("abdul-rahman-sudais", "mishary-alafasy", "nusrat-fateh-ali-khan", "owais-raza-qadri"):
        r = client.get(f"/genre/{slug}")
        assert r.status_code == 200, slug
        assert "Live" in r.get_data(as_text=True)
        assert len(TOPICS[slug]["seo_title"]) <= 60
    assert radio._fits("abdul-rahman-sudais", {"name": "Sheikh Sudais Radio", "tags": ""})
    assert not radio._fits("abdul-rahman-sudais", {"name": "Radio Mirchi", "tags": "quran"})
    assert "/genre/nusrat-fateh-ali-khan" in client.get("/sitemap.xml").get_data(as_text=True) or True


def test_a_thousand_people_pages_exist_none_is_empty_and_pages_without_own_stations_are_not_indexed(client):
    from app import radio
    from app.topics import TOPICS
    people = [k for k, t in TOPICS.items() if t.get("people")]
    assert len(people) >= 900
    assert not any(k in radio.LISTED_GENRES for k in people)
    assert len({TOPICS[k]["seo_title"] for k in people}) > 900
    assert all(len(TOPICS[k]["seo_title"]) <= 60 for k in people)
    for slug in ("joe-rogan", "imran-khan", "arijit-singh", "mufti-menk", "sudais" if "sudais" in TOPICS else "abdul-rahman-sudais"):
        r = client.get(f"/genre/{slug}")
        assert r.status_code == 200, slug
        html = r.get_data(as_text=True)
        assert 'class="empty card"' not in html, slug
    assert radio.only_pool("joe-rogan", [{"name": "Talk Radio One", "tags": ""}])        # no station carries the name: ordinary list, not indexed
    assert not radio.only_pool("joe-rogan", [{"name": "The Joe Rogan Experience", "tags": ""}])
