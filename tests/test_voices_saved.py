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
