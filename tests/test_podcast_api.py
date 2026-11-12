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
    assert client.get("/api/podcasts/near", headers={"CF-IPCountry": "XX"}).get_json()["slug"] == "top-pk"     # unknown: Pakistan
    assert client.get("/api/podcasts/near").get_json()["slug"] == "top-pk"
    assert client.get("/api/podcasts/c/top-gb").status_code == 200
    assert client.get("/podcasts/c/top-gb").status_code == 200
    assert client.get("/api/podcasts/c/top-zz").status_code == 404


def test_faith_row_defaults_and_choices(client):
    d = client.get("/api/podcasts/near", headers={"CF-IPCountry": "IL"}).get_json()
    assert d["faith"] == "jewish" and {f["slug"] for f in d["faiths"]} >= {"islamic-scholars", "christian", "jewish", "hindu", "sikh", "buddhist"}
    assert client.get("/api/podcasts/near", headers={"CF-IPCountry": "US"}).get_json()["faith"] == "christian"
    assert client.get("/api/podcasts/near", headers={"CF-IPCountry": "PK"}).get_json()["faith"] == "islamic-scholars"
    for slug in ("christian", "jewish", "hindu", "sikh", "buddhist"):
        assert client.get(f"/api/podcasts/c/{slug}").status_code == 200 and client.get(f"/podcasts/c/{slug}").status_code == 200
