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
