import os


def _client():
    os.environ.setdefault("SECRET_KEY", "x" * 40)
    os.environ["RADIO_DEMO"] = "1"
    from app import create_app
    return create_app().test_client()


def test_category_and_episodes_json():
    c = _client()
    r = c.get("/api/podcasts/c/urdu")
    assert r.status_code == 200 and "items" in r.get_json()
    assert c.get("/api/podcasts/c/nope").status_code == 404
    items = c.get("/api/podcasts/c/top-world").get_json()["items"]
    if items:
        e = c.get(f"/api/podcasts/{items[0]['i']}/episodes")
        assert e.status_code == 200 and "items" in e.get_json()


def test_chart_and_search_rows_hide_adult_shows(monkeypatch):
    import json
    from app import podcasts
    chart = {"feed": {"results": [{"id": "1", "name": "AI Today", "artistName": "B", "artworkUrl100": "https://x/100x100bb.jpg"},
                                  {"id": "2", "name": "Sexy Stories", "artistName": "B", "artworkUrl100": "https://x/100x100bb.jpg"}]}}
    monkeypatch.setattr(podcasts, "_get", lambda u, limit, timeout=7: json.dumps(chart).encode())
    assert [r["name"] for r in podcasts._chart("us")] == ["AI Today"]
    row = {"collectionId": 5, "collectionName": "Sexy Stories", "artistName": "x", "artworkUrl100": "https://a/100x100.jpg"}
    assert podcasts._row(row) is None
    assert podcasts._row({**row, "collectionName": "Business Show"})["name"] == "Business Show"


def test_visitor_country_chart(client):
    r = client.get("/api/podcasts/near", headers={"CF-IPCountry": "GB"})
    assert r.get_json()["slug"] == "top-gb" and r.get_json()["title"] == "Top podcasts in the United Kingdom"
    assert "no-store" in r.headers["Cache-Control"]
    assert client.get("/api/podcasts/near", headers={"CF-IPCountry": "XX"}).get_json()["slug"] == "top-world"
    assert client.get("/api/podcasts/near").get_json()["slug"] == "top-world"
    assert client.get("/api/podcasts/c/top-gb").status_code == 200
    assert client.get("/podcasts/c/top-gb").status_code == 200
    assert client.get("/api/podcasts/c/top-zz").status_code == 404


def test_faith_row_is_neutral(client):
    for cc in ("IL", "US", "PK", "IN", "XX"):
        d = client.get("/api/podcasts/near", headers={"CF-IPCountry": cc}).get_json()
        assert d["faith"] == "faiths"                                                  # nobody's belief is guessed from the country
        assert d["faiths"][0]["slug"] == "faiths" and {f["slug"] for f in d["faiths"]} >= {"islamic-scholars", "christian", "jewish", "hindu", "sikh", "buddhist"}
    assert client.get("/api/podcasts/near", headers={"CF-IPCountry": "XX"}).get_json()["slug"] == "top-world"     # unknown country: the world chart
    for slug in ("faiths", "christian", "jewish", "hindu", "sikh", "buddhist"):
        assert client.get(f"/api/podcasts/c/{slug}").status_code == 200
    assert client.get("/podcasts/c/christian").status_code == 200


def test_show_page_opens_even_if_marked_explicit_or_feed_is_down(client, monkeypatch):
    from app import podcasts
    podcasts._shows.clear()
    result = {"collectionId": 777, "collectionName": "Bayan Show", "artistName": "A Scholar", "artworkUrl100": "https://a/100x100.jpg",
              "feedUrl": "https://feeds.example.org/f.xml", "collectionExplicitness": "explicit"}
    monkeypatch.setattr(podcasts, "_api", lambda path, **kw: {"results": [result]})
    monkeypatch.setattr(podcasts, "_get", lambda *a, **k: (_ for _ in ()).throw(OSError("feed is down")))
    app = client.application
    app.config["TESTING"] = False
    app.config["RADIO_DEMO"] = False
    try:
        r = client.get("/podcasts/777")
    finally:
        app.config["TESTING"] = True
    assert r.status_code == 200 and b"Bayan Show" in r.data and b"No episodes could be loaded" in r.data
    assert podcasts._row(result) is None and podcasts._row(result, False)["name"] == "Bayan Show"      # lists still leave explicit shows out


def test_empty_podcast_list_is_never_cached(client, monkeypatch):
    from app import podcasts
    monkeypatch.setattr(podcasts, "category", lambda slug, demo=False: [])
    r = client.get("/api/podcasts/c/top-pakistan")
    assert r.get_json() == {"items": []} and r.headers["Cache-Control"] == "no-store"
    monkeypatch.setattr(podcasts, "category", lambda slug, demo=False: [{"id": "1", "name": "N", "artist": "A", "img": "https://x/y.png"}])
    assert "max-age=600" in client.get("/api/podcasts/c/top-pakistan").headers["Cache-Control"]


def test_category_in_a_country(client, monkeypatch):
    from app import podcasts
    asked = []
    monkeypatch.setattr(podcasts, "_api", lambda path, **kw: asked.append(kw.get("country")) or {"results": []})
    assert podcasts.valid("business@gb") and podcasts.valid("kids@pk")
    assert not podcasts.valid("business@zz") and not podcasts.valid("islamic-scholars@pk") and not podcasts.valid("top-world@pk")
    assert podcasts.label("business@gb") == "Business in the United Kingdom"
    podcasts._build("business@gb")
    assert asked and asked[0] == "GB"                           # the category is asked in the chosen country first
    assert client.get("/api/podcasts/c/business@zz").status_code == 404


def test_category_in_small_country_is_never_empty(client, monkeypatch):
    from app import podcasts
    row = lambda i: {"collectionId": i, "collectionName": f"Show {i}", "artistName": f"A{i}", "artworkUrl100": "https://a/100x100.jpg"}
    def fake(path, **kw):
        return {"results": []} if kw.get("country") == "NP" else {"results": [row(i) for i in range(1, 6)]}
    monkeypatch.setattr(podcasts, "_api", fake)
    monkeypatch.setattr(podcasts, "_chart", lambda cc: [])
    assert len(podcasts._build("business@np")) >= 3


def test_learning_categories(client):
    from app import podcasts
    for slug in ("education", "health", "motivation", "languages"):
        assert podcasts.valid(slug) and podcasts.valid(slug + "@gb")
        assert client.get(f"/api/podcasts/c/{slug}").status_code == 200


def test_category_of_a_country_starts_with_the_country_chart(client, monkeypatch):
    from app import podcasts
    asked = []
    chart = [{"id": str(100 + i), "name": f"Local {i}", "artist": f"L{i}", "img": "https://a/200x200.jpg", "feed": ""} for i in range(14)]
    monkeypatch.setattr(podcasts, "_chart_genre", lambda cc, gid: asked.append((cc, gid)) or chart)
    monkeypatch.setattr(podcasts, "_api", lambda path, **kw: asked.append(("search", kw.get("country"))) or {"results": []})
    rows = podcasts._build("news@pk")
    assert asked[0] == ("pk", 1489)                              # Apple's News chart of Pakistan comes first
    assert [r["name"] for r in rows[:2]] == ["Local 0", "Local 1"]
    assert not [a for a in asked if a[0] == "search"]            # a full country chart is not mixed with the world's searches
    # chart down or empty: the old searches still fill the list (nothing breaks)
    asked.clear()
    monkeypatch.setattr(podcasts, "_chart_genre", lambda cc, gid: (_ for _ in ()).throw(OSError("down")))
    row = lambda i: {"collectionId": i, "collectionName": f"Show {i}", "artistName": f"A{i}", "artworkUrl100": "https://a/100x100.jpg"}
    monkeypatch.setattr(podcasts, "_api", lambda path, **kw: {"results": [row(i) for i in range(1, 9)]})
    assert len(podcasts._build("news@pk")) >= 3


def test_language_lists_are_per_language_and_not_per_country(client, monkeypatch):
    from app import podcasts
    for slug in ("learn-english", "learn-german", "learn-french", "learn-spanish", "learn-arabic", "learn-chinese", "learn-from-urdu"):
        assert podcasts.valid(slug) and not podcasts.valid(slug + "@pk")
        assert client.get(f"/api/podcasts/c/{slug}").status_code == 200
        assert client.get(f"/api/podcasts/c/{slug}@pk").status_code == 404
    assert podcasts.label("learn-german") == "Learn German"
    assert podcasts.valid("languages") and podcasts.valid("languages@gb")     # the old list stays for the old app versions
    asked = []
    monkeypatch.setattr(podcasts, "_api", lambda path, **kw: asked.append(kw.get("term")) or {"results": []})
    podcasts._build("learn-german")
    assert any("german" in (t or "").lower() or "deutsch" in (t or "").lower() for t in asked)


def test_genre_chart_rows_are_read_and_adult_ones_hidden(monkeypatch):
    import json
    from app import podcasts
    feed = {"feed": {"entry": [
        {"id": {"attributes": {"im:id": "11"}}, "im:name": {"label": "News Hour"}, "im:artist": {"label": "A"}, "im:image": [{"label": "https://x/55x55bb.png"}, {"label": "https://x/170x170bb.png"}]},
        {"id": {"attributes": {"im:id": "12"}}, "im:name": {"label": "Sexy Talk"}, "im:artist": {"label": "B"}, "im:image": []}]}}
    seen = []
    monkeypatch.setattr(podcasts, "_get", lambda u, limit, timeout=7: seen.append(u) or json.dumps(feed).encode())
    rows = podcasts._chart_genre("pk", 1489)
    assert [r["name"] for r in rows] == ["News Hour"] and rows[0]["img"].endswith("200x200bb.png")
    assert "/pk/rss/toppodcasts/genre=1489/" in seen[0]
