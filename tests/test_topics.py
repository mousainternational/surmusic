"""v1.6: many radio types and countries, each with its own page and words for Google."""
import re

from app.topics import COUNTRY_PAGES, GENRE_PAGES, TOPICS


def test_every_type_and_country_page_works(client):
    assert len(TOPICS) >= 40
    for slug in GENRE_PAGES:
        html = client.get(f"/genre/{slug}").get_data(as_text=True)
        assert TOPICS[slug]["seo_title"].replace("&", "&amp;") in html, slug
    for slug in COUNTRY_PAGES:
        r = client.get(f"/country/{slug}")
        assert r.status_code == 200, slug
    assert client.get("/genre/pakistan").headers["Location"].endswith("/country/pakistan")
    assert client.get("/country/naat").headers["Location"].endswith("/genre/naat")
    assert client.get("/country/nowhere").status_code == 404


def test_page_text_for_search(client):
    html = client.get("/genre/naat").get_data(as_text=True)
    assert "نعت شریف ریڈیو" in html and "naat sharif live" in html
    assert 'href="/radio-stations"' in html


def test_all_radio_page_links_everything(client):
    html = client.get("/radio-stations").get_data(as_text=True)
    from app.topics import SECT_PAGES
    for slug, t in TOPICS.items():
        if slug in SECT_PAGES:                      # kept for search engines only (sitemap), not shown as a button
            assert "/genre/" + slug + '"' not in html
            continue
        assert ("/country/" if t["kind"] == "country" else "/genre/") + slug + '"' in html


def test_sitemap_lists_all_pages(client):
    xml = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/radio-stations</loc>" in xml and "/country/pakistan</loc>" in xml and "/genre/pashto</loc>" in xml


def test_station_found_from_saved_list_with_one_query(client, app):
    client.get("/country/uae")
    html = client.get("/country/uae").get_data(as_text=True)
    href = re.findall(r'data-href="(/station/[^"]+)"', html)[0]
    app.extensions.get("lowdb") and app.extensions["lowdb"].cache.clear()
    page = client.get(href).get_data(as_text=True)
    assert 'href="/country/uae"' in page


def test_world_countries_and_continents(client, monkeypatch):
    from app import radio
    from app.topics import CONTINENTS
    assert len(COUNTRY_PAGES) > 200
    assert TOPICS["japan"]["native"] == "日本" and TOPICS["brazil"]["group"] == "south-america"
    assert TOPICS["uk"]["group"] == "europe" and TOPICS["pakistan"]["group"] == "asia"
    for c in CONTINENTS:
        assert client.get(f"/continent/{c}").status_code == 200
    assert client.get("/continent/mars").status_code == 404
    html = client.get("/country/germany").get_data(as_text=True)
    assert "/continent/europe" in html
    # only countries that really have stations are listed (when Radio Browser tells us the numbers)
    monkeypatch.setattr(radio, "country_counts", lambda: {"DE": 900, "NR": 0})
    html = client.get("/continent/oceania").get_data(as_text=True)
    assert "Nauru" not in html and "noindex" in html
    html = client.get("/radio-stations").get_data(as_text=True)
    assert "/country/germany" in html and "/country/nauru" not in html
    xml = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/country/germany</loc>" in xml and "/country/nauru</loc>" not in xml


def test_accessibility_page_and_world_links(client):
    html = client.get("/accessibility").get_data(as_text=True)
    assert "screen reader" in html.lower() and "<kbd>K</kbd>" in html
    home = client.get("/").get_data(as_text=True)
    menu = client.get("/menu/country").get_data(as_text=True)                 # the Country menu, loaded when opened
    assert 'href="/country/usa"' in menu and 'href="/continent/europe"' in menu and 'href="/accessibility"' in home
    assert 'id="sr-announce"' in home
    for slug in ("christian", "latin", "talk", "afrobeats"):
        assert client.get(f"/genre/{slug}").status_code == 200


def test_category_tabs(client):
    def parts(path):
        html = client.get(path).get_data(as_text=True)
        nav = html.split("data-nav-tabs", 1)[1].split("</nav>", 1)[0]
        tabs = re.findall(r'<a class="nt-tab( on)?"[^>]*data-tab="([^"]+)"', nav)
        return nav, tabs
    nav, tabs = parts("/bollywood")
    assert [t for _, t in tabs] == ["music", "news", "sports", "talk", "religious", "accessibility", "az"]
    assert [t for on, t in tabs if on] == ["music"]
    for href in ("/bollywood", "/lollywood", "/hollywood", "/genre/ghazal", "/genre/news", "/genre/cricket",
                 "/genre/islamic", "/genre/christian", "/genre/bhajan"):
        assert f'href="{href}"' in nav, href
    # nothing in the buttons points at one school of thought, and Quran / Naat have no tab of their own
    for word in ("madani", "majlis", "hadith", "Dawat", "/genre/quran", "/genre/naat"):
        assert word not in nav, word
    nav, tabs = parts("/genre/quran")                     # Quran lives under Religious → Islamic
    assert [t for on, t in tabs if on] == ["religious"]
    assert ">All Islamic<" not in nav and "Naat &amp; Hamd" not in nav      # no small Islamic tabs
    assert [t for on, t in parts("/country/pakistan")[1] if on] == []          # countries live in the header menu
    assert 'data-tab="languages"' not in nav and 'data-tab="countries"' not in nav
    assert [t for on, t in parts("/genre/news")[1] if on] == ["news"]
    # the pages that hold those stations are still there for Google
    xml = client.get("/sitemap.xml").get_data(as_text=True)
    assert client.get("/genre/madani").status_code == 200


def test_popular_list_merges_duplicates_and_never_links_to_a_missing_page(client, app):
    from app.db import Database, utcnow
    db = Database(app.config["DATABASE_URL"])
    for uuid, name, cat, n in [("e1b2c3d4-1111-2222-3333-444455556666", "Radio Pakistan Islamabad", "lollywood", 3),
                               ("e1b2c3d4-1111-2222-3333-444455556666", "Radio Pakistan Islamabad", "news", 2),
                               ("c1b2c3d4-1111-2222-3333-444455556666", "The Holy Quran by Sheikh Mahmoud Al-Husary — "
                                "Murattal Recitation 24/7 very long name", "quran", 4)]:
        for _ in range(n):
            db.execute("INSERT INTO plays (station_uuid, station_name, category, created_at) VALUES (?, ?, ?, ?)",
                       (uuid, name, cat, utcnow()))
    db.commit(); db.close()
    html = client.get("/").get_data(as_text=True)
    block = html.split('class="popular-list"', 1)[1].split("</ol>", 1)[0]
    assert block.count("Radio Pakistan Islamabad</a>") == 1 and "5 plays" in block
    for href in re.findall(r'href="([^"]+)"', block):
        assert client.get(href.replace("&amp;", "&")).status_code == 200, href


def test_titles_fit_in_a_search_result(client):
    """Google cuts titles at about 60-65 characters: country pages and the home page must stay short."""
    import re
    from app.topics import TOPICS
    for slug, t in TOPICS.items():
        if t["kind"] == "country" and len(t["label"]) < 20:
            html = client.get(f"/country/{slug}").get_data(as_text=True)
            m = re.search(r"<title>(.*?)</title>", html)
            if m:                                   # only listed countries (with stations) have a page
                assert len(m.group(1)) <= 70, m.group(1)
    home = re.search(r"<title>(.*?)</title>", client.get("/").get_data(as_text=True)).group(1)
    assert len(home) <= 65, home


def test_llms_txt_and_page_schema(client):
    r = client.get("/llms.txt")
    assert r.status_code == 200 and "surmusic.example/radio-stations" in r.get_data(as_text=True)
    assert "ContactPage" in client.get("/contact").get_data(as_text=True)
    assert "WebPage" in client.get("/donate").get_data(as_text=True)


def test_music_player_keywords_are_on_the_matching_pages(client):
    pop = client.get("/genre/pop").get_data(as_text=True)
    assert "free online music player" in pop
    dance = client.get("/genre/dance").get_data(as_text=True)
    assert "EDM radio" in dance
    assert "relaxing music player" in client.get("/genre/lofi").get_data(as_text=True)
    assert "classic hits" in client.get("/genre/old-songs").get_data(as_text=True)
    home = client.get("/").get_data(as_text=True)
    assert "free online music player and radio player" in home


def test_player_style_words_are_on_the_home_page(client):
    home = client.get("/").get_data(as_text=True)
    for word in ("neon music player", "vinyl record player", "glass music player", "EDM equalizer", "audio visualizer"):
        assert word in home


def test_indexnow_key_file(client, app):
    from app import indexnow
    key = indexnow.key_for(app.config["SECRET_KEY"])
    r = client.get(f"/{key}.txt")
    assert r.status_code == 200 and r.get_data(as_text=True) == key
    assert client.get("/" + "a" * 32 + ".txt").status_code == 404


def test_favourite_stars_only_for_members(client, app):
    from tests.conftest import signup
    html = client.get("/").get_data(as_text=True)
    assert re.search(r'<body class="[^"]*\bguest\b', html)
    c2 = app.test_client()
    signup(c2)
    assert "guest" not in c2.get("/").get_data(as_text=True).split("<body", 1)[1].split(">", 1)[0]
    css = open("app/static/css/site.css", encoding="utf-8").read()
    assert "body.guest .st-fav" in css


def test_share_picture_and_button(client, monkeypatch):
    from app import radio
    st = {"uuid": "9062f97c-7c49-4a6a-be28-4997a06aa001", "name": "OmniRadio - Islamic Audio Library (متنوع)",
          "country": "Qatar", "url": "https://example.com/s", "tags": "islam"}
    monkeypatch.setattr(radio, "station_by_uuid", lambda u: (st if u == st["uuid"] else None, "naat"))
    r = client.get(f"/og/station/{st['uuid']}.png")
    assert r.status_code == 200 and r.mimetype == "image/png" and r.data[:4] == b"\x89PNG"
    assert client.get("/og/station/zzzz.png").status_code == 404
    assert client.get("/og/station/ffffffff-0000-0000-0000-000000000000.png").status_code == 404
    page = client.get("/").get_data(as_text=True)
    assert 'id="pl-share"' in page and 'id="np-share"' in page


def test_long_lists_are_paged(client, monkeypatch):
    from app import radio
    fake = [{"uuid": f"id{i:04d}", "name": f"Station {i}", "url": "https://x.example/s", "favicon": "",
             "country": "Qatar", "tags": "ghazal", "bitrate": 128, "clicks": 1000 - i} for i in range(230)]
    monkeypatch.setattr(radio, "genre_stations", lambda slug: fake)
    p1 = client.get("/genre/ghazal").get_data(as_text=True)
    assert p1.split('class="with-side"', 1)[1].count('<li class="st') == 100 and "?page=2" in p1 and "230 live stations" in p1
    assert "noindex" not in p1.split("</head>")[0]
    p3 = client.get("/genre/ghazal?page=3").get_data(as_text=True)
    assert p3.split('class="with-side"', 1)[1].count('<li class="st') == 30 and "noindex" in p3.split("</head>")[0]
    assert client.get("/genre/ghazal?page=99").status_code == 200       # too high a page → the last one
    assert client.get("/genre/ghazal?page=abc").status_code == 200


def test_ai_and_search_optimisation(client, monkeypatch):
    import json as _json
    from app import radio
    fake = [{"uuid": f"id{i:04d}", "name": f"Station {i}", "url": "https://x.example/s", "favicon": "",
             "country": "Qatar", "tags": "ghazal", "bitrate": 128, "clicks": 100 - i} for i in range(12)]
    monkeypatch.setattr(radio, "genre_stations", lambda slug: fake)
    html = client.get("/genre/ghazal").get_data(as_text=True)
    assert '<meta name="keywords" content="Ghazal radio' in html
    blocks = [_json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    kinds = {b["@type"] for b in blocks}
    assert {"BreadcrumbList", "CollectionPage", "FAQPage"} <= kinds
    coll = next(b for b in blocks if b["@type"] == "CollectionPage")
    assert coll["mainEntity"]["numberOfItems"] == 12
    assert "Is Ghazal radio free to listen to?" in html and "Station 0, Station 1, Station 2" in html
    robots = client.get("/robots.txt").get_data(as_text=True)
    assert "User-agent: GPTBot" in robots and "User-agent: ClaudeBot" in robots and "Disallow: /admin" in robots
    assert robots.strip().endswith("/sitemap.xml")
    llms = client.get("/llms.txt").get_data(as_text=True)
    assert "## Radio by type" in llms and "/genre/naat" in llms and "Facts for answers" in llms


def test_every_title_is_at_most_60_characters(client):
    from app.topics import TOPICS
    for slug in ("home", ):
        pass
    for slug, t in TOPICS.items():
        assert len(t["seo_title"]) <= 60, (slug, len(t["seo_title"]))
    for path in ("/", "/bollywood", "/lollywood", "/hollywood", "/genre/naat", "/genre/quran", "/genre/qawwali",
                 "/country/pakistan", "/download", "/radio-stations", "/islam", "/live-news", "/blog"):
        html = client.get(path).get_data(as_text=True)
        title = re.search(r"<title>(.*?)</title>", html, re.S).group(1)
        assert len(title.replace("&amp;", "&")) <= 60, (path, title)


def test_city_pages_near_me_and_station_faq(client):
    for path in ("/genre/lahore", "/genre/karachi", "/genre/mumbai", "/genre/dubai", "/genre/hyderabad-sindh"):
        r = client.get(path)
        assert r.status_code == 200, path
        title = re.search(r"<title>(.*?)</title>", r.get_data(as_text=True), re.S).group(1).replace("&amp;", "&")
        assert len(title) <= 60 and "Radio" in title, (path, title)
    assert 'href="/genre/lahore"' in client.get("/radio-stations").get_data(as_text=True)
    assert client.get("/near-me").status_code == 302
    html = client.get("/genre/quran").get_data(as_text=True)
    listing = html.split("data-nav-tabs", 1)[1].split("</nav>", 1)[1]     # the station list, not the News tab chips
    href = re.search(r'href="(/station/[^"]+)"', listing).group(1)
    page = client.get(href).get_data(as_text=True)
    assert "FAQPage" in page and "stops playing" in page


def test_now_playing_reads_the_song_name(app, monkeypatch):
    import threading, socket
    from app import radio
    meta = b"StreamTitle='Nusrat Fateh Ali Khan - Tere Bin';"
    block = meta + b"\0" * ((16 - len(meta) % 16) % 16)
    every = 1000
    body = b"a" * every + bytes([len(block) // 16]) + block + b"b" * every
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)

    def serve():
        c, _ = srv.accept(); c.recv(2048)
        c.sendall(b"HTTP/1.0 200 OK\r\nicy-metaint: 1000\r\ncontent-type: audio/mpeg\r\n\r\n" + body); c.close()

    threading.Thread(target=serve, daemon=True).start()
    assert radio.parse_icy(block) == "Nusrat Fateh Ali Khan - Tere Bin"
    with app.app_context():
        # our own machine is never contacted (no private addresses), and http is refused
        assert radio.read_track(f"https://127.0.0.1:{srv.getsockname()[1]}/x") == ""
        assert radio.read_track("http://example.com/x") == ""
        monkeypatch.setattr(radio, "_public_host", lambda h: True)
        # plain-http fake server: read_track only talks https, so check the parser path with the fake https refusal
        assert radio.read_track(f"http://127.0.0.1:{srv.getsockname()[1]}/x", schemes=("http", "https")) == \
            "Nusrat Fateh Ali Khan - Tere Bin"
    srv.close()


def test_home_has_add_to_home_screen_button_and_recent_box(client):
    html = client.get("/").get_data(as_text=True)
    assert 'id="a2hs"' in html and 'id="recent-box"' in html
    assert 'class="cat-tile"' not in html


def test_news_strip_replaces_the_price_strip(client):
    html = client.get("/").get_data(as_text=True)
    assert 'id="nw-ticker"' in html and 'data-ticker' not in html
    assert client.get("/api/headlines").get_json() == {"items": []}      # tests never touch the network
    from app import headlines
    xml = ("<rss><channel><item><title>Big news today - Dawn</title><link>https://news.google.com/rss/articles/x</link></item>"
           "<item><title>Bad link - X</title><link>http://insecure.example/a</link></item></channel></rss>")
    assert headlines.parse(xml) == [{"t": "Big news today", "s": "Dawn", "u": "https://news.google.com/rss/articles/x"}]
    assert headlines.parse("<!DOCTYPE x [<!ENTITY a 'b'>]><rss/>") == []
    assert "gl=IT" in headlines._feed_url("IT") and "ceid=PK%3Aen" in headlines._feed_url("PK")
    urls = headlines._feed_urls("PK")
    assert any("topic/BUSINESS" in u for u in urls) and any("topic/SPORTS" in u for u in urls) and any("bollywood" in u for u in urls)
    mixed = headlines.mix([[{"t": "a1"}, {"t": "a2"}], [{"t": "b1"}], [{"t": "a1"}, {"t": "c1"}]])
    assert [m["t"] for m in mixed] == ["a1", "b1", "a2", "c1"]


def test_song_name_is_clean_text():
    from app import radio
    enc = "Islam+Sobhi+%D8%A5%D8%B3%D9%84%D8%A7%D9%85+%D8%B5%D8%A8%D8%AD%D9%8A+-+%D8%B3%D9%88%D8%B1%D8%A9"
    assert radio.clean_title(enc) == "Islam Sobhi إسلام صبحي - سورة"
    assert radio.clean_title("Artist - Song") == "Artist - Song"
    assert radio.clean_title("http://example.com/x?a=1") == "" and radio.clean_title(" - ") == ""
    assert radio.parse_icy(b"StreamTitle='" + enc.encode() + b"';") == "Islam Sobhi إسلام صبحي - سورة"


def test_accessibility_tab_and_seo(client):
    home = client.get("/bollywood").get_data(as_text=True)
    assert 'data-tab="accessibility"' in home and 'data-sub="accessibility"' in home
    page = client.get("/accessibility").get_data(as_text=True)
    assert 'id="keyboard-shortcuts"' in page
    assert "FAQPage" in page and "radio for blind people" in page and "نابینا" in page
    import re
    title = re.search(r"<title>(.*?)</title>", page, re.S).group(1)
    import html as _h
    assert len(_h.unescape(title)) <= 60, title



def test_reviews_submit_approve_show(client, app):
    import re
    from conftest import login, post
    assert b"Write a review" in client.get("/reviews").data
    assert post(client, "/reviews", {"name": "A", "rating": "9", "body": "short"}, page="/reviews").status_code == 400
    assert post(client, "/reviews", {"name": "Sara", "rating": "5", "body": "Visit http://spam.example now"}, page="/reviews").status_code == 400
    assert post(client, "/reviews", {"name": "Bot", "rating": "5", "body": "Great radio for everyone", "website": "x"}, page="/reviews").status_code == 400
    r = post(client, "/reviews", {"name": "Sara", "rating": "5", "body": "Great free radio, easy to use."}, page="/reviews",
             follow_redirects=True)
    assert b"will appear after a quick check" in r.data
    assert b"Great free radio" not in client.get("/reviews").data
    login(client)
    admin = client.get("/admin/reviews").get_data(as_text=True)
    assert "Great free radio" in admin
    rid = re.search(r"/admin/reviews/(\d+)/approve", admin).group(1)
    post(client, f"/admin/reviews/{rid}/approve", {}, page="/admin/reviews")
    assert b"Great free radio" in client.get("/reviews").data
    assert b"/reviews" in client.get("/sitemap.xml").data


def test_home_filters_are_a_to_z_and_category_has_only_big_names(client):
    import re
    html = client.get("/").get_data(as_text=True)
    assert "<select" not in html.split('class="cat-row"', 1)[1].split("</nav>", 1)[0]       # Country and Language are in the header menus
    row = html.split('class="cat-row"', 1)[1].split("</nav>", 1)[0]
    assert re.findall(r'class="cat-box[^"]*" href="([^"]+)"', row) == [
        "/genre/religious", "/genre/music", "/genre/news", "/genre/business", "/genre/daily-life",
        "/genre/kids", "/genre/cooking", "/genre/technology", "/accessibility"]
    assert "<select" not in row                                    # six plain boxes; Religious types are shown on its own page
    rel = client.get("/genre/religious").get_data(as_text=True)
    assert 'class="chip' in rel and "/genre/islamic" in rel and "/genre/christian" in rel and "data-filter-list" in rel
    for url in ("/genre/music", "/genre/sports", "/genre/daily-life", "/genre/business", "/genre/talk", "/genre/religious", "/genre/islamic", "/genre/news", "/accessibility"):
        assert client.get(url).status_code == 200, url
    for slug in ("ghazal", "qawwali", "sufi", "old-songs", "pop"):      # the old pages stay for Google
        assert client.get(f"/genre/{slug}").status_code == 200


def test_channel_logo_http_is_upgraded_to_https():
    from app.radio import _logo
    assert _logo("http://example.com/logo.png") == "https://example.com/logo.png"
    assert _logo("https://example.com/logo.png") == "https://example.com/logo.png"
    assert _logo("") == "" and _logo("javascript:alert(1)") == "" and _logo(None) == ""


def test_lists_fall_back_to_the_saved_directory_when_the_online_one_is_down(app, monkeypatch):
    from app import radio
    pool = [{"uuid": f"u{i}", "name": f"Kids {i}", "url": "https://x.example/s", "favicon": "", "country": "Qatar",
             "tags": "kids, music", "language": "English", "bitrate": 128, "clicks": 100 - i} for i in range(40)]
    pool.append({"uuid": "other", "name": "Cars", "url": "https://x.example/c", "favicon": "", "country": "Qatar",
                 "tags": "cars", "language": "English", "bitrate": 128, "clicks": 999})
    monkeypatch.setattr(radio, "_local_all", pool)
    with app.app_context():
        out = radio._local_lists(["/json/stations/search?tag=kids&hidebroken=true"], None, 300)
        assert len(out) == 40 and out[0]["uuid"] == "u0" and all(s["uuid"] != "other" for s in out)
        assert radio._local_lists(["/json/stations/search?tag=nothing"], None, 300) == []


def test_local_radio_button_follows_the_visitor_country(client):
    r = client.get("/country/pakistan", headers={"Accept-Language": "en-IN"})
    assert 'href="/country/india"' in r.get_data(as_text=True) and "India radio stations" in r.get_data(as_text=True)
    r = client.get("/country/pakistan", headers={"Accept-Language": "ur-PK"})
    assert "Pakistan FM by frequency" in r.get_data(as_text=True)


def test_podcast_pages_and_strip_work(client):
    j = client.get("/api/podcasts").get_json()
    assert j["items"] and j["items"][0]["i"] == "1001"
    r = client.get("/podcasts"); assert r.status_code == 200 and "/podcasts/1001" in r.get_data(as_text=True)
    html = client.get("/podcasts/1001").get_data(as_text=True)
    assert "Sample episode 1" in html and 'class="st' in html
    assert client.get("/podcasts/999999").status_code == 404
    assert 'id="pd-ticker"' in client.get("/").get_data(as_text=True)


def test_podcast_category_pages_work(client):
    assert client.get("/podcasts/c/islamic-scholars").status_code == 200
    assert client.get("/podcasts/c/nope").status_code == 404
    assert "oldest first" in client.get("/podcasts/1001?order=old").get_data(as_text=True)


def test_podcast_seo_titles_sitemap_and_noindex(client):
    import re
    from app.podcasts import CATEGORIES
    for path in ["/podcasts"] + [f"/podcasts/c/{k}" for k in CATEGORIES]:
        html = client.get(path).get_data(as_text=True)
        import html as _h; t = _h.unescape(re.search(r"<title>(.*?)</title>", html).group(1))
        assert len(t) <= 60, (path, t)
        assert 'name="description"' in html and 'rel="canonical"' in html and "ItemList" in html
    assert "noindex" in client.get("/podcasts?q=zzz").get_data(as_text=True)
    sm = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/podcasts</loc>" in sm and "/podcasts/c/islamic-scholars</loc>" in sm and "/podcasts/1001" not in sm
