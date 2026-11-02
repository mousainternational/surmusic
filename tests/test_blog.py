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
