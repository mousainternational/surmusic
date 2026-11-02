import pytest

from app import trends

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:ht="https://trends.google.com/trending/rss"><channel><title>Daily Search Trends</title>
<item><title>pak vs eng</title><ht:approx_traffic>500K+</ht:approx_traffic><pubDate>Mon, 02 Nov 2026 03:00:00 +0000</pubDate></item>
<item><title>petrol price in pakistan</title><ht:approx_traffic>5K+</ht:approx_traffic></item>
<item><title>gold rate today</title><ht:approx_traffic>2K+</ht:approx_traffic></item>
<item><title>brazil presidential election results</title><ht:approx_traffic>200+</ht:approx_traffic></item>
<item><title>us midterm election results</title><ht:approx_traffic>200K+</ht:approx_traffic></item>
<item><title>weather forecast lahore</title></item>
<item><title>presidential debate</title></item>
<item><title>bollywood new movie trailer</title></item>
<item><title>new song lyrics</title></item>
<item><title>wedding</title><ht:approx_traffic>2K+</ht:approx_traffic></item>
<item><title>mawra hocane</title><ht:approx_traffic>200+</ht:approx_traffic></item>
<item><title>player killed in match</title><ht:approx_traffic>1K+</ht:approx_traffic></item>
<item><title>PAK VS ENG</title></item>
</channel></rss>"""


@pytest.fixture(autouse=True)
def clean():
    trends._state.update(data={}, ts=0.0, next=0.0, busy=False)
    yield
    trends._state.update(data={}, ts=0.0, next=0.0, busy=False)


def test_broad_but_safe_topics_are_kept():
    rows = trends._clean(trends.parse_feed(FEED))
    terms = [r["term"] for r in rows]
    for want in ("pak vs eng", "petrol price in pakistan", "gold rate today", "brazil presidential election results",
                 "us midterm election results", "weather forecast lahore", "presidential debate",
                 "bollywood new movie trailer", "new song lyrics"):
        assert want in terms, want
    for drop in ("wedding", "mawra hocane", "player killed in match"):
        assert drop not in terms
    hrefs = {r["term"]: r["href"] for r in rows}
    assert hrefs["pak vs eng"] == "/genre/sports" and hrefs["gold rate today"] == "/markets"
    assert hrefs["us midterm election results"] == "/genre/news" and hrefs["presidential debate"] == "/genre/talk"
    assert hrefs["bollywood new movie trailer"] == "/bollywood" and hrefs["new song lyrics"] == "/genre/pop"


def test_unsafe_xml_is_refused():
    with pytest.raises(trends.TrendError):
        trends.parse_feed('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><rss><channel/></rss>')


def test_pages_show_the_list_and_survive_a_broken_feed(client):
    trends.refresh_now(lambda url, timeout=8: FEED)
    html = client.get("/trending").get_data(as_text=True)
    assert "Trending in Pakistan" in html and "pak vs eng" in html and "Google Trends" in html
    assert "pak vs eng" in client.get("/genre/sports").get_data(as_text=True)
    assert "pak vs eng" in client.get("/").get_data(as_text=True)
    assert "pak vs eng" not in client.get("/genre/quran").get_data(as_text=True)
    def broken(url, timeout=8):
        raise OSError("down")
    trends.refresh_now(broken)                              # the old list stays
    assert "pak vs eng" in client.get("/trending").get_data(as_text=True)


def test_empty_trending_page_is_not_indexed(client):
    r = client.get("/trending")
    assert r.status_code == 200 and "noindex" in r.get_data(as_text=True)
    assert client.get("/genre/sports").status_code == 200


def test_trending_is_in_the_sitemap_only_when_it_has_data(client):
    assert "/trending" not in client.get("/sitemap.xml").get_data(as_text=True)
