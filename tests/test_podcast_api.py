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
