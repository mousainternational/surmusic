import re
from app import podcasts


def _home_all_links(html):
    return dict(re.findall(r'<div class="pr-row" data-slug="([^"]+)" hidden>\s*<div class="section-head"><h2 class="h3">[^<]*</h2><a href="([^"]+)">All', html))


def test_all_link_of_every_podcast_row_opens_that_row_not_the_list_of_categories(client):
    links = _home_all_links(client.get("/").get_data(as_text=True))
    assert set(links) == {"top-world", "near", "faith", "technology", "ai", "business"}
    assert "/podcasts" not in links.values()                                    # "/podcasts" is the page with all categories
    assert links["near"] == "/podcasts/c/top-world" and links["faith"] == "/podcasts/c/faiths"
    for slug, href in links.items():
        assert href.startswith("/podcasts/c/")
        assert client.get(href).status_code == 200
    js = client.get("/static/js/podrows.js").data.decode()
    assert '"/podcasts/c/" + d.slug' in js and '"/podcasts/c/" + cur' in js    # the visitor's own country / chosen faith replace the default


def test_islamic_page_mixes_every_kind_near_the_top(monkeypatch):
    kinds = {"islamic lectures": "L", "quran tafseer": "T", "seerah": "S", "ahlulbayt majlis podcast": "M", "shia islam podcast": "H"}
    def fake_api(path, **k):
        tag = kinds[k["term"]]
        return {"results": [{"collectionId": f"{ord(tag)}{i}", "collectionName": f"{tag} show {i}", "artistName": f"{tag}{i}",
                             "artworkUrl100": "https://example.com/100x100.jpg"} for i in range(6)]}
    monkeypatch.setattr(podcasts, "_api", fake_api)
    monkeypatch.setattr(podcasts, "index_search", lambda term, limit=20: [])
    first = [r["name"][0] for r in podcasts._build("islamic")[:5]]
    assert sorted(first) == sorted(kinds.values())                            # one of each kind in the first five, not the last ones
    assert len(podcasts._build("islamic")) >= 25


def test_pages_ask_for_more_shows_from_both_directories_and_the_app_gets_up_to_250(monkeypatch, client):
    seen = {}
    def fake_api(path, **k):
        seen["limit"] = k.get("limit"); return {"results": []}
    def fake_index(term, limit=20):
        seen["index"] = limit; return []
    monkeypatch.setattr(podcasts, "_api", fake_api); monkeypatch.setattr(podcasts, "index_search", fake_index)
    podcasts._build("urdu")
    assert seen == {"limit": 100, "index": 40}
    rows = [{"id": str(i), "name": f"Show {i}", "artist": f"A{i}", "img": "https://example.com/a.jpg", "feed": ""} for i in range(400)]
    monkeypatch.setattr(podcasts, "category", lambda slug, demo=False: rows)
    assert len(client.get("/api/podcasts/c/urdu").get_json()["items"]) == 250
