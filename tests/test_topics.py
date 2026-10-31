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
    for slug, t in TOPICS.items():
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
    assert 'href="/country/usa"' in home and 'href="/continent/europe"' in home and 'href="/accessibility"' in home
    assert 'id="sr-announce"' in home
    for slug in ("christian", "latin", "talk", "afrobeats"):
        assert client.get(f"/genre/{slug}").status_code == 200


def test_type_strip_follows_visitor_country(app):
    def chips(**headers):
        html = app.test_client().get("/", headers=headers).get_data(as_text=True)
        strip = html.split("data-genre-chips", 1)[1].split("</nav>", 1)[0]
        return re.findall(r'data-topic="([^"]+)"', strip)
    pk = chips(**{"Accept-Language": "ur-PK,ur;q=0.9"})
    us = chips(**{"Accept-Language": "en-US,en;q=0.9"})
    de = chips(**{"Accept-Language": "de-DE"})
    il = chips(**{"Accept-Language": "he-IL"})
    assert pk[0] == "pakistan" and "naat" in pk and "quran" in pk
    assert us[0] == "usa" and "christian" in us and "country-music" in us and "naat" not in us
    assert de[0] == "germany" and "dance" in de
    assert il[0] == "israel" and "jewish" in il
    assert "pop" in chips()                                     # unknown country: a mix for everyone
    # the time zone the browser reported wins over the language
    c = app.test_client()
    c.get("/")
    import json
    with c.session_transaction() as s:
        s["geo_c"] = "IN"
    html = c.get("/", headers={"Accept-Language": "en-US"}).get_data(as_text=True)
    strip = html.split("data-genre-chips", 1)[1].split("</nav>", 1)[0]
    assert re.findall(r'data-topic="([^"]+)"', strip)[:2] == ["india", "bhajan"]


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
