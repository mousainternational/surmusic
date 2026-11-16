from markupsafe import escape
import re

from app import blog


def test_every_guide_page_works(client):
    assert client.get("/blog").status_code == 200
    for p in blog.POSTS:
        r = client.get(f"/blog/{p['slug']}")
        html = r.get_data(as_text=True)
        assert r.status_code == 200
        assert str(escape(p["title"])) in html and '"@type": "Article"' in html
        assert 'rel="canonical" href="https://surmusic.example/blog/' + p["slug"] in html
        assert len(p["description"]) >= 70 and len(p["body"].split()) > 400
    assert client.get("/blog/does-not-exist").status_code == 404


def test_guides_are_in_the_sitemap_and_internal_links_are_followed(client):
    sm = client.get("/sitemap.xml").get_data(as_text=True)
    for p in blog.POSTS:
        assert f"/blog/{p['slug']}" in sm
    body = client.get("/blog/listen-quran-radio-online-free").get_data(as_text=True)
    assert 'href="/genre/quran"' in body and 'rel="nofollow noopener" href="/genre' not in body


def test_guide_links_point_to_real_pages(client):
    for p in blog.POSTS:
        for href in set(re.findall(r"\]\((/[^)#]*)\)", p["body"])):
            assert client.get(href).status_code == 200, (p["slug"], href)


def test_podcast_hub_guide_links_every_podcast_page_and_keeps_faiths_neutral(client):
    from app import podcasts
    slug = "podcasts-by-topic-speaker-and-faith-guide"
    assert slug in blog.BY_SLUG
    body = blog.BY_SLUG[slug]["body"]
    for cat in podcasts.CATEGORIES:                           # one link for every podcast category page
        assert f"](/podcasts/c/{cat})" in body, cat
    assert "](/podcasts)" in body
    pos = [body.index(f"](/podcasts/c/{c})") for c in ("buddhist", "christian", "hindu", "islamic", "jewish", "sikh")]
    assert pos == sorted(pos)                                 # faiths are listed A to Z: none is put first
    page = client.get(f"/blog/{slug}").get_data(as_text=True)
    assert "/podcasts/c/christian" in page and client.get("/sitemap.xml").get_data(as_text=True).count(f"/blog/{slug}") == 1


def test_public_pages_do_not_name_the_station_directory(client):
    """The shop window (home, About, llms.txt) names no outside source; the legal pages keep their disclaimer."""
    for path in ("/", "/about", "/llms.txt"):
        assert "Radio Browser" not in client.get(path).get_data(as_text=True), path
    assert "Every station is a public live stream broadcast by its owner." in client.get("/about").get_data(as_text=True)
