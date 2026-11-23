from app import podcasts

APPLE_TOP_LEVEL = {"arts": 1301, "comedy": 1303, "fiction": 1483, "government": 1511, "history": 1487, "leisure": 1502,
                   "music": 1310, "society": 1324, "sports": 1545, "true-crime": 1488, "tv-film": 1309}


def test_every_apple_podcast_category_has_a_page_a_chart_and_a_country_form():
    for slug, gid in APPLE_TOP_LEVEL.items():
        assert slug in podcasts.CATEGORIES and podcasts.GENRES[slug] == gid
        assert podcasts.valid(slug) and podcasts.valid(slug + "@pk")          # also "<category> in Pakistan"
        assert podcasts.label(slug + "@pk").endswith("Pakistan")
        assert any(st[0] == "search" for st in podcasts.CATEGORIES[slug][1])  # words fill the page if Apple's chart is short


def test_new_category_pages_open_and_are_in_the_sitemap(client):
    sm = client.get("/sitemap.xml").get_data(as_text=True)
    for slug in APPLE_TOP_LEVEL:
        assert f"/podcasts/c/{slug}" in sm
        assert client.get(f"/podcasts/c/{slug}").status_code == 200
    assert client.get("/podcasts/c/religion").status_code == 404          # faiths stay on their own neutral pages


def test_second_directory_shows_fill_category_pages(monkeypatch):
    extra = [{"id": "777", "name": "Urdu Kahani Hour", "artist": "Kahani Studio", "img": "https://example.com/k.jpg", "feed": ""}]
    monkeypatch.setattr(podcasts, "_api", lambda *a, **k: {"results": []})
    monkeypatch.setattr(podcasts, "index_search", lambda term, limit=20: extra)
    assert [r["id"] for r in podcasts._build("urdu")] == ["777"]
    monkeypatch.setattr(podcasts, "index_search", lambda term, limit=20: [])      # no key: pages work as before
    assert podcasts._build("urdu") == []
