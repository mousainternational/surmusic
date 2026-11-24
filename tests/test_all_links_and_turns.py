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
    assert '"/podcasts/c/" + d.slug' in js and '"/podcasts/c/" + (cur ===' in js    # the visitor's own country / chosen faith replace the default


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
    assert seen == {"limit": 200, "index": 80}
    rows = [{"id": str(i), "name": f"Show {i}", "artist": f"A{i}", "img": "https://example.com/a.jpg", "feed": ""} for i in range(600)]
    monkeypatch.setattr(podcasts, "category", lambda slug, demo=False: rows)
    assert len(client.get("/api/podcasts/c/urdu").get_json()["items"]) == 400


def test_a_category_page_shows_its_podcasts_first_and_keeps_the_category_list_folded(client):
    html = client.get("/podcasts/c/islamic-scholars").get_data(as_text=True)
    box = html.split('<details class="pod-cats-box">', 1)[1].split("</details>", 1)[0]
    assert 'class="chip' in box and html.index("pod-cats-box") < html.index('class="pod-grid"')
    assert "<details class=\"pod-cats-box\" open" not in html                 # folded: the shows are the first thing seen
    assert "podcasts on this page" in html or "podcast on this page" in html
    index = client.get("/podcasts").get_data(as_text=True)
    assert "pod-cats-box" not in index and 'class="chip active" href="/podcasts"' in index   # the page of all categories keeps its chips
    assert 'cur === "islamic-scholars" ? "islamic"' in client.get("/static/js/podrows.js").data.decode()


def test_hassan_allahyari_is_looked_up_with_the_scholars_and_only_listed_if_he_has_a_show(monkeypatch):
    assert ("Hassan Allahyari", "allahyari") in podcasts.SCHOLARS
    hit = {"collectionId": "991", "collectionName": "Debates", "artistName": "Hassan Allahyari", "artworkUrl100": "https://example.com/100x100.jpg"}
    def fake_api(path, **k):
        return {"results": [hit]} if "allahyari" in k["term"].lower() else {"results": []}
    monkeypatch.setattr(podcasts, "_api", fake_api); monkeypatch.setattr(podcasts, "index_search", lambda t, limit=20: [])
    assert [r["id"] for r in podcasts._build("islamic-scholars")] == ["991"]          # found: listed
    monkeypatch.setattr(podcasts, "_api", lambda *a, **k: {"results": []})
    assert podcasts._build("islamic-scholars") == []                                  # no show found: nobody is listed without audio


def test_genre_pages_always_add_word_searches_after_a_chart_of_200(monkeypatch):
    assert podcasts.LIST_FULL > 200
    urls = []
    monkeypatch.setattr(podcasts, "_get", lambda url, cap=0, *a, **k: (urls.append(url), b'{"feed":{"entry":[]}}')[1])
    podcasts._chart_genre("us", 1489)
    assert "limit=200" in urls[0]
    terms = []
    monkeypatch.setattr(podcasts, "_chart_genre", lambda cc, gid: [{"id": str(i), "name": f"C{i}", "artist": f"A{i}", "img": "https://e.com/a.jpg", "feed": ""} for i in range(200)])
    monkeypatch.setattr(podcasts, "_api", lambda path, **k: (terms.append(k["term"]), {"results": []})[1])
    monkeypatch.setattr(podcasts, "index_search", lambda t, limit=20: [])
    podcasts._build("news")
    assert len(terms) >= 5 and "world news podcast" in terms                  # not skipped just because the chart was long
