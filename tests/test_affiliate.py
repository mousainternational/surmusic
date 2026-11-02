"""Partner (affiliate) offers: added by the owner, clearly labelled, clicks counted, no open redirect."""
import re

from conftest import login, post


def _add(client, **kw):
    data = {"action": "add", "title": "Wireless Earbuds", "url": "https://amzn.to/abc123", "price": "Rs 2,499",
            "note": "Long battery", "store": "Amazon", "place": "all"}
    data.update(kw)
    return post(client, "/admin/offers", data, page="/admin/offers", follow_redirects=True)


def test_owner_adds_offer_and_visitors_see_it(client, app):
    anon = app.test_client()
    assert "Partner offers" not in anon.get("/hollywood").get_data(as_text=True)      # nothing until added
    assert anon.get("/admin/offers").status_code in (302, 403)                       # owner only
    login(client)
    r = _add(client)
    assert b"Offer added" in r.data
    assert b"must start with https" in _add(client, url="http://bad.example/x").data
    assert b"must start with https" in _add(client, url="javascript:alert(1)").data
    for path in ("/", "/hollywood", "/genre/naat", "/deals"):
        html = anon.get(path).get_data(as_text=True)
        assert "Wireless Earbuds" in html and ("Affiliate" in html or "affiliate links" in html), path
        assert 'rel="sponsored nofollow noopener"' in html, path
    href = re.search(r'href="(/go/[0-9a-f]+)"', anon.get("/deals").get_data(as_text=True)).group(1)
    go = anon.get(href)
    assert go.status_code == 302 and go.headers["Location"] == "https://amzn.to/abc123"
    assert anon.get("/go/ffffffff").status_code == 404                                 # only stored links
    page = client.get("/admin/offers").get_data(as_text=True)
    assert re.search(r"<td>1</td>", page)                                              # 1 click counted
    assert "As an Amazon Associate" in anon.get("/disclaimer").get_data(as_text=True)


def test_place_and_switches(client, app):
    login(client)
    _add(client, title="Speaker Deal", place="station")
    anon = app.test_client()
    assert "Speaker Deal" not in anon.get("/hollywood").get_data(as_text=True)        # station pages only
    assert "Speaker Deal" in anon.get("/deals").get_data(as_text=True)
    oid = re.search(r'name="id" value="([0-9a-f]+)"', client.get("/admin/offers").get_data(as_text=True)).group(1)
    post(client, "/admin/offers", {"action": "toggle", "id": oid}, page="/admin/offers")
    assert "Speaker Deal" not in anon.get("/deals").get_data(as_text=True)            # hidden
    post(client, "/admin/offers", {"action": "toggle", "id": oid}, page="/admin/offers")
    post(client, "/admin/offers", {"action": "switch"}, page="/admin/offers")          # whole feature off
    assert "Speaker Deal" not in anon.get("/deals").get_data(as_text=True)
    assert anon.get(f"/go/{oid}").status_code == 404
