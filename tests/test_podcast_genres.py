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


def test_home_has_a_dropdown_of_every_podcast_category(client):
    html = client.get("/").get_data(as_text=True)
    assert 'id="pr-cat-sel"' in html
    sel = html.split('id="pr-cat-sel"', 1)[1].split("</select>", 1)[0]
    for slug in podcasts.CATEGORIES:
        assert (f'value="{slug}"' in sel) == (not slug.startswith("top-"))
    names = [x.split("<", 1)[0] for x in sel.split(">")[2:] if x.split("<", 1)[0]]
    assert names[0].startswith("Choose") and names[1:] == sorted(names[1:], key=str.lower)      # A to Z: no faith or topic is put first
    js = client.get("/static/js/podrows.js").data
    assert b"pr-cat-sel" in js and b"/podcasts/c/" in js


def test_start_up_warming_skips_the_on_demand_categories(monkeypatch):
    built = []
    monkeypatch.setattr(podcasts, "category", lambda slug, demo=False: built.append(slug) or [])
    monkeypatch.setattr(podcasts.time, "sleep", lambda s: None)
    podcasts.warm()
    assert "urdu" in built and "top-world" in built
    assert not (set(built) & podcasts.ON_DEMAND) and podcasts.ON_DEMAND == set(APPLE_TOP_LEVEL) | {"ahl-e-bait"}


def test_ahl_e_bait_page_and_shia_scholars_are_listed(client):
    assert podcasts.valid("ahl-e-bait") and podcasts.valid("ahl-e-bait@pk")
    assert client.get("/podcasts/c/ahl-e-bait").status_code == 200
    assert "/podcasts/c/ahl-e-bait" in client.get("/sitemap.xml").get_data(as_text=True)
    assert "Majlis" in podcasts.PAGE_TEXT["ahl-e-bait"][1]
    words = {m for _w, m in podcasts.SCHOLARS}
    assert {"nakshawani", "shomali", "naqvi"} <= words and {"qadhi", "israr"} <= words          # the list stays mixed: every school has its names
