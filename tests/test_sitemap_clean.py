"""The sitemap lists each page once, and only lists A–Z station pages that really have stations."""
import re

from app import public, radio
from app import directory


def _locs(xml):
    return re.findall(r"<loc>([^<]+)</loc>", xml)


def test_sitemap_lists_each_page_only_once(client, monkeypatch):
    real = public._listed_types

    def doubled(visible_only=False):
        return [(g, items + items) for g, items in real(visible_only)]

    monkeypatch.setattr(public, "_listed_types", doubled)
    locs = _locs(client.get("/sitemap.xml").get_data(as_text=True))
    assert locs, "sitemap is empty"
    assert len(locs) == len(set(locs)), [u for u in set(locs) if locs.count(u) > 1][:5]


def test_letter_pages_not_in_sitemap_when_empty(client, monkeypatch):
    monkeypatch.setattr(directory, "by_letter", lambda letter, limit=200, offset=0, app=None: ([], 0))
    monkeypatch.setattr(radio, "known_stations", lambda: [])
    locs = _locs(client.get("/sitemap.xml").get_data(as_text=True))
    assert not [u for u in locs if "/stations/" in u]


def test_letter_page_listed_when_it_has_stations(client, monkeypatch):
    monkeypatch.setattr(directory, "by_letter",
                        lambda letter, limit=200, offset=0, app=None: ([{"name": "x"}], 1) if letter == "q" else ([], 0))
    monkeypatch.setattr(radio, "known_stations", lambda: [])
    locs = _locs(client.get("/sitemap.xml").get_data(as_text=True))
    assert [u for u in locs if u.endswith("/stations/q")]
    assert not [u for u in locs if u.endswith("/stations/a")]
