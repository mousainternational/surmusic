from app import public


def test_app_weather_lists_only_cities_with_data(client, monkeypatch):
    monkeypatch.setattr(public, "_weather_start", lambda: None)
    monkeypatch.setattr(public, "_weather_data", lambda slug: {"temp": 21, "text": "Clear", "t": 0, "days": [
        {"lo": 10, "hi": 24, "text": "Clear", "rain": None, "nested": {"x": 1}}]} if slug == "lahore" else None)
    d = client.get("/api/app/weather").get_json()
    assert [c["name"] for c in d["cities"]] == ["Lahore"] and d["cities"][0]["temp"] == 21
    assert "nested" not in d["cities"][0]["days"][0]


def test_app_news_empty_until_enough_sections(client, monkeypatch):
    monkeypatch.setattr(public.today_news, "start", lambda *a, **k: None)
    monkeypatch.setattr(public.today_news, "get", lambda: {"sections": {"World": [{"t": "A", "s": "BBC"}]}, "t": 0})
    assert client.get("/api/app/news").get_json() == {"sections": []}
    monkeypatch.setattr(public.today_news, "get", lambda: {"sections": {k: [{"t": k + " headline", "s": "x"}] for k in ("World", "Sport", "Tech")}, "t": 0})
    d = client.get("/api/app/news").get_json()
    assert [s["name"] for s in d["sections"]] == ["World", "Sport", "Tech"] and d["sections"][0]["items"][0]["t"] == "World headline"


def test_app_voices_only_people_with_audio(client, monkeypatch):
    monkeypatch.setattr(public, "_spawn_found_refresh", lambda: None)
    people = [k for k, t in public.TOPICS.items() if t.get("people")][:2]
    monkeypatch.setattr(public, "_FOUND", {people[0]: ("Person One", "https://img.example/a.jpg")})
    monkeypatch.setattr(public, "_person_shows", lambda slug, remember=True: [{"id": 7, "name": "Talk", "artist": "Host", "img": "https://img.example/t.jpg"}])
    d = client.get("/api/app/voices").get_json()
    assert d["items"] == [{"slug": people[0], "n": "Person One", "m": "https://img.example/a.jpg"}]
    shows = client.get(f"/api/app/voices/{people[0]}").get_json()
    assert shows["items"] == [{"i": 7, "n": "Talk", "a": "Host", "m": "https://img.example/t.jpg"}]
    assert client.get(f"/api/app/voices/{people[1]}").status_code == 404        # no audio found: not offered
