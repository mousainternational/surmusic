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
