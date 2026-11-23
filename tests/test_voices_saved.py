from app import persist, public, radio


def test_famous_voices_list_comes_back_after_restart(app, monkeypatch):
    slug = "mishary-alafasy"
    shows = [{"id": "1", "name": "Talks", "artist": "X", "img": "https://i.test/a.jpg", "feed": ""}]
    saved = {}
    monkeypatch.setattr(persist, "enabled", lambda: True)
    monkeypatch.setattr(persist, "save_json", lambda name, obj: saved.update({name: obj}) or "pushed")
    with app.app_context():
        public._FOUND.clear()
        radio.seed_saved("pod:p3:" + slug, shows)
        public._note_found(slug, shows)
        public._VOICES_SAVED["n"] = 0
        assert public._voices_save() == "pushed"
        snap = saved["voices"]
        assert slug in snap["people"]
        # "restart": memory and database copy are gone
        public._FOUND.clear()
        radio.get_db().execute("DELETE FROM station_cache")
        radio.get_db().commit()
        monkeypatch.setattr(persist, "load_json", lambda name: snap)
        assert public._voices_restore() == 1
        assert slug in public._FOUND
        assert radio._peek("pod:p3:" + slug) == shows
        public._FOUND.clear()


def test_a_much_smaller_list_never_replaces_a_good_saved_copy(app, monkeypatch):
    called = []
    monkeypatch.setattr(persist, "save_json", lambda n, o: called.append(1) or "pushed")
    with app.app_context():
        public._FOUND.clear()
        public._VOICES_SAVED["n"] = 50
        assert public._voices_save() == "skipped" and not called
        public._VOICES_SAVED["n"] = 0


def test_second_directory_adds_shows_with_apple_id_and_is_safe_without_key(monkeypatch):
    import json as _json
    from app import podcasts
    monkeypatch.delenv("PODCASTINDEX_KEY", raising=False)
    assert podcasts.index_search("Someone Famous") == []
    monkeypatch.setenv("PODCASTINDEX_KEY", "k")
    monkeypatch.setenv("PODCASTINDEX_SECRET", "s")
    body = _json.dumps({"feeds": [
        {"itunesId": 123, "title": "Someone Famous Talks", "author": "Someone Famous", "artwork": "https://i.test/a.jpg", "url": "https://f.test/rss"},
        {"itunesId": None, "title": "No apple id", "author": "Someone Famous"},
        {"itunesId": 5, "title": "Bad", "author": "Someone Famous", "explicit": True}]}).encode()

    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n): return body
    monkeypatch.setattr(podcasts.urllib.request, "urlopen", lambda req, timeout=0: R())
    rows = podcasts.index_search("Someone Famous")
    assert [r["id"] for r in rows] == ["123"] and rows[0]["img"].startswith("https://")


def test_weather_asks_one_city_at_a_time_and_one_failure_keeps_the_rest():
    from app import weather
    from tests.test_topics import _met_block
    calls = []

    def fetch(url):
        calls.append(url)
        if len(calls) == 1:
            raise OSError("refused")
        return _met_block()
    weather._DATA.clear()
    got = weather.refresh_all(fetch)
    assert len(calls) == len(weather.CITIES) and got == len(weather.CITIES) - 1 and all("api.met.no" in u for u in calls)
    first = weather.get("lahore") or next(iter(weather._DATA.values()))
    assert first["text"] == "Light rain" and first["days"][0]["hi"] > first["days"][0]["lo"] and 8 < first["wind"] < 10
    weather._DATA.clear()


def test_no_menu_or_sitemap_link_to_a_person_without_audio(client):
    public._FOUND.clear()
    html = client.get("/").get_data(as_text=True)
    assert "/genre/adele" not in html and "/genre/mufti-menk" not in html
    assert "/genre/adele" not in client.get("/llms.txt").get_data(as_text=True)
    assert public._page_exists("adele") is False and public._page_exists("pakistan") is True
    public._note_found("mufti-menk", [{"id": "2", "name": "Menk", "artist": "x", "img": "https://i.test/m.jpg"}])
    assert public._page_exists("mufti-menk") is True
    public._FOUND.clear()


def test_a_page_with_real_headlines_stays_open_and_linked_and_headlines_survive_a_restart(app, client, monkeypatch):
    from app import persist
    news = [{"t": "A real headline", "s": "Paper", "u": "https://n.test/a"}]
    saved = {}
    monkeypatch.setattr(persist, "save_json", lambda name, obj: saved.update({name: obj}) or "pushed")
    with app.app_context():
        public._FOUND.clear()
        radio.seed_saved("keep:pn2:bill-nye", news)
        radio.seed_saved("keep:pn2:adele", [{"t": "", "s": "", "u": ""}])
        radio.seed_saved("pod:p3:bill-nye", [])
        assert public._page_exists("bill-nye") is True and public._page_exists("adele") is False
        assert "/genre/bill-nye" in client.get("/sitemap.xml").get_data(as_text=True)
        r = client.get("/genre/bill-nye")
        assert r.status_code == 200 and "A real headline" in r.get_data(as_text=True)
        public._FOUND["x-found"] = ("X", "https://i.test/x.jpg")
        public._VOICES_SAVED["n"] = 0
        monkeypatch.setattr(radio, "_peek", lambda key, _o=radio._peek: ([{"id": "1"}] if key == "pod:p3:x-found" else _o(key)))
        public._voices_save()
        assert saved["voices"]["news"]["bill-nye"][0]["t"] == "A real headline" and "adele" not in saved["voices"]["news"]
        public._FOUND.clear()
        public._VOICES_SAVED["n"] = 0
