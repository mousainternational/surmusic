import pytest

from app import markets


@pytest.fixture(autouse=True)
def clean_cache():
    for st in markets._cache.values():
        st.update(data={}, ts=0.0, next=0.0, busy=False)
    yield
    for st in markets._cache.values():
        st.update(data={}, ts=0.0, next=0.0, busy=False)


def fake_http(url, headers=None, timeout=6):
    if "coinbase" in url:
        return {"data": {"base": "BTC", "currency": "USD", "amount": "95000.5"}} if "BTC-USD" in url else \
            {"data": {"amount": "3200"}} if "ETH-USD" in url else {"errors": [{"id": "not_found"}]}
    if "gold-api" in url:
        return {"name": "Gold", "price": 3110.34768, "symbol": "XAU"} if url.endswith("XAU") else \
            {"name": "Silver", "price": 31.1034768, "symbol": "XAG"} if url.endswith("XAG") else {"error": "x"}
    if "er-api" in url:
        return {"result": "success", "rates": {"USD": 1, "PKR": 280.0, "INR": 84.0, "AED": 3.6725, "EUR": 0.9, "GBP": 0.8}}
    raise AssertionError(url)


CFG = {}


def test_prices_and_local_gold_math(monkeypatch):
    monkeypatch.setattr(markets, "_http_json", fake_http)
    markets.refresh_now(CFG)
    items = markets._all_items()
    assert items["btc"]["price"] == 95000.5 and items["eth"]["price"] == 3200 and "sol" not in items
    assert round(items["usd-pkr"]["price"], 1) == 280.0 and round(items["eur-usd"]["price"], 4) == round(1 / 0.9, 4)
    d = markets._derived(items)
    # 3110.34768 USD per ounce = 100 USD per gram; 280 PKR per USD; a tola is 11.6638 grams
    assert round(items["usd-pkr"]["price"] / items["usd-aed"]["price"], 3) == round(280 / 3.6725, 3)
    assert round(d["eur-pkr"]["price"], 2) == round(280 / 0.9, 2) and round(d["aed-pkr"]["price"], 2) == round(280 / 3.6725, 2)
    assert round(d["gold-pkr-gram"]["price"], 2) == 28000.0
    assert round(d["gold-pkr-tola"]["price"], 1) == round(28000 * 11.6638, 1)
    assert round(d["gold-inr-10g"]["price"]) == 84000
    payload = markets.api_payload()
    assert payload["items"]["btc"] == {"text": "95,000.50", "change": "", "dir": "", "spark": ""}
    assert payload["items"]["eth"]["text"] == "3,200.00" and payload["updated"].endswith("UTC")


def test_a_failing_source_hides_only_its_group(monkeypatch):
    def broken(url, headers=None, timeout=6):
        if "coinbase" in url:
            raise OSError("down")
        return fake_http(url, headers, timeout)
    monkeypatch.setattr(markets, "_http_json", broken)
    markets.refresh_now(CFG)
    secs = {s["key"]: s for s in markets.view()}
    assert not secs["crypto"]["ready"]
    assert secs["metals"]["ready"] and secs["forex"]["ready"] and secs["local"]["ready"]
    assert "energy" not in secs


def test_old_numbers_are_kept_when_a_refresh_fails(monkeypatch):
    monkeypatch.setattr(markets, "_http_json", fake_http)
    markets.refresh_now(CFG, ["crypto"])
    monkeypatch.setattr(markets, "_http_json", lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    markets.refresh_now(CFG, ["crypto"])
    assert markets._all_items()["btc"]["price"] == 95000.5


def test_pages_and_api(client, monkeypatch):
    monkeypatch.setattr(markets, "_http_json", fake_http)
    markets.refresh_now(CFG)
    html = client.get("/markets").get_data(as_text=True)
    assert "95,000.50" in html and "not financial advice" in html.lower() and "FAQPage" in html
    assert "Gold per tola (Pakistan)" in html and "Euro to Pakistani rupee" in html and 'rel="canonical" href="https://surmusic.example/markets"' in html
    from datetime import datetime, timezone
    assert f"Gold rate today {datetime.now(timezone.utc).year}" in html
    assert "95,000.50" in client.get("/").get_data(as_text=True)
    j = client.get("/api/markets").get_json()
    assert j["items"]["usd-pkr"]["text"] == "280.00"
    assert "/markets" in client.get("/sitemap.xml").get_data(as_text=True)


def test_markets_page_works_with_no_data_at_all(client):
    r = client.get("/markets")
    assert r.status_code == 200 and "Gold Rate Today" in r.get_data(as_text=True)
    assert client.get("/api/markets").get_json()["items"] == {}
    assert client.get("/").status_code == 200


def test_ticker_has_change_and_little_chart(monkeypatch):
    def http(url, headers=None, timeout=6):
        if "candles" in url:                      # newest first, like the exchange sends them
            return [[1000 + 3600 * i, 0, 0, 0, 100 + (23 - i)] for i in range(24)]
        return fake_http(url, headers, timeout)
    monkeypatch.setattr(markets, "_http_json", http)
    markets._sparks.clear()
    markets.refresh_now(CFG)
    row = {r["id"]: r for r in markets.ticker()}["btc"]
    assert row["text"] == "95,000.50" and row["dir"] == "up" and row["change"].startswith("+")
    assert len(row["spark"].split()) == 25 and "sol" not in {r["id"] for r in markets.ticker() if r["text"]}
    assert markets.spark_points([1]) == "" and markets.spark_points([1, 2, 3]).count(",") == 3


def test_ticker_strip_renders_on_every_page(client):
    html = client.get("/about").get_data(as_text=True) if client.get("/about").status_code == 200 else client.get("/").get_data(as_text=True)
    assert 'data-ticker' in html and 'class="mk-set"' in html


def test_price_strip_keeps_moving_on_slow_phones():
    css = open("app/static/css/site.css", encoding="utf-8").read()
    assert ".slow-net .mk-track" not in css and ".slow-net .mk-ticker" not in css      # a phone on mobile data must still see it move
    assert "animation: mk-scroll" in css
