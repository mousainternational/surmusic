import re
from app import podcasts


def _home_all_links(html):
    return dict(re.findall(r'<div class="pr-row" data-slug="([^"]+)" hidden>\s*<div class="section-head"><h2 class="h3">[^<]*</h2><a href="([^"]+)">All', html))


def test_all_link_of_every_podcast_row_opens_that_row_not_the_list_of_categories(client):
    links = _home_all_links(client.get("/").get_data(as_text=True))
    assert set(links) == {"top-world", "near", "faith", "technology", "ai", "business"}
    assert "/podcasts" not in links.values()                                    # "/podcasts" is the page with all categories
    assert links["near"] == "/podcasts/c/top-world" and links["faith"] == "/podcasts/c/faiths"
    for slug, href in links.items():
        assert href.startswith("/podcasts/c/")
        assert client.get(href).status_code == 200
    js = client.get("/static/js/podrows.js").data.decode()
    assert '"/podcasts/c/" + d.slug' in js and '"/podcasts/c/" + (cur ===' in js    # the visitor's own country / chosen faith replace the default


def test_islamic_page_mixes_every_kind_near_the_top(monkeypatch):
    kinds = {"islamic lectures": "L", "quran tafseer": "T", "seerah": "S", "ahlulbayt majlis podcast": "M", "shia islam podcast": "H"}
    def fake_api(path, **k):
        tag = kinds[k["term"]]
        return {"results": [{"collectionId": f"{ord(tag)}{i}", "collectionName": f"{tag} show {i}", "artistName": f"{tag}{i}",
                             "artworkUrl100": "https://example.com/100x100.jpg"} for i in range(6)]}
    monkeypatch.setattr(podcasts, "_api", fake_api)
    monkeypatch.setattr(podcasts, "index_search", lambda term, limit=20: [])
    first = [r["name"][0] for r in podcasts._build("islamic")[:5]]
    assert sorted(first) == sorted(kinds.values())                            # one of each kind in the first five, not the last ones
    assert len(podcasts._build("islamic")) >= 25


def test_pages_ask_for_more_shows_from_both_directories_and_the_app_gets_up_to_250(monkeypatch, client):
    seen = {}
    def fake_api(path, **k):
        seen["limit"] = k.get("limit"); return {"results": []}
    def fake_index(term, limit=20):
        seen["index"] = limit; return []
    monkeypatch.setattr(podcasts, "_api", fake_api); monkeypatch.setattr(podcasts, "index_search", fake_index)
    podcasts._build("urdu")
    assert seen == {"limit": 200, "index": 80}
    rows = [{"id": str(i), "name": f"Show {i}", "artist": f"A{i}", "img": "https://example.com/a.jpg", "feed": ""} for i in range(600)]
    monkeypatch.setattr(podcasts, "category", lambda slug, demo=False: rows)
    assert len(client.get("/api/podcasts/c/urdu").get_json()["items"]) == 600


def test_a_category_page_shows_its_podcasts_first_and_keeps_the_category_list_folded(client):
    html = client.get("/podcasts/c/islamic-scholars").get_data(as_text=True)
    box = html.split('<details class="pod-cats-box">', 1)[1].split("</details>", 1)[0]
    assert 'class="chip' in box and html.index("pod-cats-box") < html.index('class="pod-grid"')
    assert "<details class=\"pod-cats-box\" open" not in html                 # folded: the shows are the first thing seen
    assert "podcasts on this page" in html or "podcast on this page" in html
    index = client.get("/podcasts").get_data(as_text=True)
    assert "pod-cats-box" not in index and 'class="chip active" href="/podcasts"' in index   # the page of all categories keeps its chips
    assert 'cur === "islamic-scholars" ? "islamic"' in client.get("/static/js/podrows.js").data.decode()


def test_hassan_allahyari_is_looked_up_with_the_scholars_and_only_listed_if_he_has_a_show(monkeypatch):
    assert ("Hassan Allahyari", "allahyari") in podcasts.SCHOLARS
    hit = {"collectionId": "991", "collectionName": "Debates", "artistName": "Hassan Allahyari", "artworkUrl100": "https://example.com/100x100.jpg"}
    def fake_api(path, **k):
        return {"results": [hit]} if "allahyari" in k["term"].lower() else {"results": []}
    monkeypatch.setattr(podcasts, "_api", fake_api); monkeypatch.setattr(podcasts, "index_search", lambda t, limit=20: [])
    assert [r["id"] for r in podcasts._build("islamic-scholars")] == ["991"]          # found: listed
    monkeypatch.setattr(podcasts, "_api", lambda *a, **k: {"results": []})
    assert podcasts._build("islamic-scholars") == []                                  # no show found: nobody is listed without audio


def test_genre_pages_always_add_word_searches_after_a_chart_of_200(monkeypatch):
    assert podcasts.LIST_FULL > 200
    urls = []
    monkeypatch.setattr(podcasts, "_get", lambda url, cap=0, *a, **k: (urls.append(url), b'{"feed":{"entry":[]}}')[1])
    podcasts._chart_genre("us", 1489)
    assert "limit=200" in urls[0]
    terms = []
    monkeypatch.setattr(podcasts, "_chart_genre", lambda cc, gid: [{"id": str(i), "name": f"C{i}", "artist": f"A{i}", "img": "https://e.com/a.jpg", "feed": ""} for i in range(200)])
    monkeypatch.setattr(podcasts, "_api", lambda path, **k: (terms.append(k["term"]), {"results": []})[1])
    monkeypatch.setattr(podcasts, "index_search", lambda t, limit=20: [])
    podcasts._build("news")
    assert len(terms) >= 5 and "world news podcast" in terms                  # not skipped just because the chart was long


def test_big_countries_have_long_station_lists_and_the_others_stay_as_they_were():
    from app import topics
    for slug in ("china", "singapore", "thailand", "malaysia", "indonesia", "japan", "australia", "new-zealand", "morocco",
                 "usa", "uk", "turkey", "russia", "azerbaijan", "germany", "france", "nigeria", "switzerland"):
        t = topics.TOPICS[slug]
        assert t["cap"] == 1000 and all("limit=1000" in p and "limit=300" not in p for p in t["paths"]), slug
    assert "cap" not in topics.TOPICS["brazil"] and "limit=300" in topics.TOPICS["brazil"]["paths"][0]


def test_big_country_podcast_page_adds_the_category_charts_and_stops_when_apple_has_no_shop(monkeypatch):
    calls = []
    def chart(cc):
        calls.append(("chart", cc)); return [{"id": f"c{i}", "name": f"Chart {i}", "artist": f"A{i}", "img": "https://e.com/a.jpg", "feed": ""} for i in range(50)]
    def genre(cc, gid):
        calls.append(("genre", gid)); return [{"id": f"{gid}-{i}", "name": f"G{gid} show {i}", "artist": f"B{gid}{i}", "img": "https://e.com/a.jpg", "feed": ""} for i in range(40)]
    monkeypatch.setattr(podcasts, "_chart", chart); monkeypatch.setattr(podcasts, "_chart_genre", genre)
    assert len(podcasts._build("top-jp")) > 400 and ("genre", 1489) in calls
    calls.clear()
    monkeypatch.setattr(podcasts, "_chart", lambda cc: [])
    assert podcasts._build("top-fr") == [] and not calls
    calls.clear()
    podcasts._build("top-br")                                                    # not in the list: only its own chart, as before
    assert not [c for c in calls if c[0] == "genre"]
    assert {"jp", "sg", "az", "de", "ng", "ma"} <= podcasts.BIG_PODCAST and "br" not in podcasts.BIG_PODCAST


def test_a_device_the_owner_marked_is_never_counted_even_without_signing_in(app, client):
    from conftest import login, post
    from app.db import Database
    def events():
        db = Database(app.config["DATABASE_URL"]); n = db.scalar("SELECT COUNT(*) FROM events WHERE kind = 'page_view'"); db.close(); return n
    visit = lambda c: c.post("/api/track", json={"path": "/"}, headers={"X-CSRF-Token": __import__("conftest").csrf(c, "/")})
    guest = app.test_client()
    assert visit(guest).status_code == 200 and events() == 1                      # an ordinary visitor is counted
    owner = app.test_client()
    login(owner)
    html = owner.get("/admin/").get_data(as_text=True)
    assert "Do not count this device" in html
    r = post(owner, "/admin/not-me", {"mode": "on"}, page="/admin/")
    assert "sm_owner=" in r.headers.get("Set-Cookie", "")
    assert "Count this device again" in owner.get("/admin/").get_data(as_text=True)
    phone = app.test_client()                                                      # the phone only carries the cookie: it is not signed in
    phone.set_cookie("sm_owner", owner.get_cookie("sm_owner").value)
    assert visit(phone).status_code == 200 and events() == 1                      # not counted
    fake = app.test_client(); fake.set_cookie("sm_owner", "x" * 32)
    assert visit(fake).status_code == 200 and events() == 2                       # a guessed cookie does not hide anybody
    post(owner, "/admin/not-me", {"mode": "off"}, page="/admin/")
    assert "Do not count this device" in owner.get("/admin/").get_data(as_text=True)


def test_bad_bots_are_blocked_and_good_ones_are_not(client):
    for ua in ("Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html)",
               "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; KeenableBot/1.0; +https://keenable.ai/bot)",
               "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)", "CCBot/2.0 (https://commoncrawl.org/faq/)"):
        assert client.get("/", headers={"User-Agent": ua}).status_code == 403, ua
        assert client.get("/robots.txt", headers={"User-Agent": ua}).status_code == 200      # they may still read the rules
    for ua in ("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
               "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
               "Mozilla/5.0 AppleWebKit/537.36 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
               "facebookexternalhit/1.1", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit Safari"):
        assert client.get("/", headers={"User-Agent": ua}).status_code == 200, ua
    robots = client.get("/robots.txt").get_data(as_text=True)
    assert "User-agent: SemrushBot" in robots and "Disallow: /contact?*station=" in robots


def test_podcast_lists_kept_in_memory_are_limited(monkeypatch):
    monkeypatch.setattr(podcasts, "CAT_KEEP", 3)
    monkeypatch.setattr(podcasts, "_build", lambda slug: [{"id": slug, "name": slug, "artist": "a", "img": "", "feed": ""}])
    podcasts._cat.clear()
    for i in range(6):
        podcasts.category(f"x{i}@jp", False)
    assert len(podcasts._cat) <= 3
