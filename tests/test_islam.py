import re

from app import islam


def test_islam_page_has_names_questions_and_schema(client):
    r = client.get("/islam")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    for name in ("Mishary Rashid Alafasy", "Abdul Basit Abdus Samad", "Nusrat Fateh Ali Khan", "Owais Raza Qadri"):
        assert name in html
    assert "FAQPage" in html and html.count("<h1") == 1
    assert 'rel="canonical" href="https://surmusic.example/islam"' in html
    assert "/islam" in client.get("/sitemap.xml").get_data(as_text=True)


def test_links_on_islam_page_and_questions_are_real(client):
    texts = [client.get("/islam").get_data(as_text=True), islam.ISLAM_FAQ, islam.HOME_FAQ, islam.MARKETS_FAQ, islam.LIVE_NEWS_FAQ,
             client.get("/live-news").get_data(as_text=True)]
    hrefs = set()
    for t in texts:
        hrefs |= set(re.findall(r'href="(/[^"#?]*)"', t)) | set(re.findall(r"\]\((/[^)#?]*)\)", t))
    assert len(hrefs) > 20
    for h in hrefs:
        assert client.get(h).status_code == 200, h


def test_home_has_brand_questions_and_islam_link(client):
    html = client.get("/").get_data(as_text=True)
    assert "What is Sur Music?" in html and 'href="/islam"' in html and "FAQPage" in html
    assert "Arijit Singh" in client.get("/bollywood").get_data(as_text=True)
    assert "Mishary Rashid Alafasy" in client.get("/genre/quran").get_data(as_text=True)
    assert "Dubai radio online" in client.get("/country/uae").get_data(as_text=True)


def test_live_news_page(client):
    html = client.get("/live-news").get_data(as_text=True)
    assert "midterm" in html.lower() and "FAQPage" in html and html.count("<h1") == 1
    assert "/live-news" in client.get("/sitemap.xml").get_data(as_text=True)
