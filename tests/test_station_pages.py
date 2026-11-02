"""Every station and every type (naat, qawwali…) has its own page, with ads and SEO."""
import json
import re

from conftest import api, login, post


def test_genre_pages(client):
    for slug in ("naat", "qawwali", "ghazal", "sufi", "punjabi", "quran", "news", "old-songs"):
        r = client.get(f"/genre/{slug}")
        assert r.status_code == 200, slug
        html = r.get_data(as_text=True)
        assert 'rel="canonical"' in html and "Listen by type" in html and 'aria-current="page"' in html
    assert "Naat Radio" in client.get("/genre/naat").get_data(as_text=True)
    assert client.get("/genre/nothing").status_code == 404
    home = client.get("/").get_data(as_text=True)
    strip = home.split("data-genre-chips", 1)[1].split('<div class="finder">', 1)[0]           # the quick buttons
    assert "naat" not in strip and "qawwali" not in strip and "sufi" not in strip
    menu = home.split('<div class="finder">', 1)[1].split("</nav>", 1)[0]                      # the drop-downs
    other = menu.split("Other</h3>", 1)[1].split("</ul>", 1)[0]
    for slug in ("naat", "qawwali", "sufi", "ghazal"):                                          # inside "Other"
        assert f'href="/genre/{slug}"' in other, slug
    assert "Choose your country" in menu and 'href="/country/usa"' in menu and 'href="/continent/europe"' in menu
    assert 'href="/genre/news"' in menu and 'href="/blog"' in home                              # Guides is in the menu
    assert 'href="/genre/quran"' in home


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
