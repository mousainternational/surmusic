from app import podcasts

ROWS = [{"id": "1", "name": "The Joe Rogan Experience", "artist": "Joe Rogan"},
        {"id": "2", "name": "Tariq Jameel Bayan", "artist": "Maulana Tariq Jameel"},
        {"id": "3", "name": "Random Cooking Show", "artist": "Chef Bob"},
        {"id": "4", "name": "Mufti Tariq Masood Speeches", "artist": "Tariq Masood"}]


def names(q):
    return [r["name"] for r in podcasts.rank(ROWS, q)]


def test_a_name_with_a_typing_mistake_still_finds_the_right_show():
    assert names("joe rogen")[0] == "The Joe Rogan Experience"
    assert names("Tariq Masud")[0] == "Mufti Tariq Masood Speeches"
    assert names("tarik jameel")[0] == "Tariq Jameel Bayan"
    assert names("JOE   ROGAN!")[0] == "The Joe Rogan Experience"          # capitals, spaces and marks do not matter


def test_wrong_shows_are_left_out_when_one_matches_well():
    assert names("tariq masood") == ["Mufti Tariq Masood Speeches"]
    assert names("zzzzqq") == []
    assert "Random Cooking Show" not in names("joe rogan")


def test_search_repairs_a_name_with_the_names_the_site_knows(monkeypatch):
    asked = []
    def fake(term):
        asked.append(term)
        return [r for r in ROWS if "tariq" in r["name"].lower()] if "tariq" in term.lower() else []
    monkeypatch.setattr(podcasts, "_search_rows", fake)
    monkeypatch.setattr(podcasts, "_known_names", lambda: ["Maulana Tariq Jameel", "Mufti Tariq Masood"])
    out = podcasts.search("Maulna Tarik Jamil")
    assert out and out[0]["name"] == "Tariq Jameel Bayan"
    assert len(asked) > 1                                                    # the typed words, then the nearest known name


def test_demo_search_and_page_still_work(client):
    assert [r["name"] for r in podcasts.search("sample stories", True)][0] == "Sample Stories"
    assert podcasts.search("qqqqqq", True) == []
    assert client.get("/podcasts?q=sampel+news").status_code == 200
