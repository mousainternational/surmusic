"""Live market prices for the "Markets" gadget and page: gold, silver, crypto and exchange rates.

Prices are fetched in the background (never while a visitor waits), kept in memory and refreshed on a timer,
so a free server is not slowed down and the free data plans are not used up. Every group is optional: if a
source is unreachable or needs a key that was not set, that group is simply hidden. Nothing here is advice.
"""
import json
import threading
import time
import urllib.request
from datetime import datetime, timezone

from flask import current_app

OZ_GRAMS = 31.1034768        # grams in one troy ounce
TOLA_GRAMS = 11.6638         # grams in one tola (used in Pakistan and India)

# group -> (seconds between refreshes, seconds to wait after a failure)
TTL = {"crypto": (120, 300), "metals": (300, 300), "forex": (43200, 1800)}

CRYPTO = [("BTC", "btc", "Bitcoin (BTC)"), ("ETH", "eth", "Ethereum (ETH)"), ("BNB", "bnb", "BNB"),
          ("SOL", "sol", "Solana (SOL)"), ("XRP", "xrp", "XRP"), ("DOGE", "doge", "Dogecoin (DOGE)")]
METALS = [("XAU", "xau", "Gold"), ("XAG", "xag", "Silver"), ("XPT", "xpt", "Platinum"), ("XPD", "xpd", "Palladium")]
FOREX = [("PKR", "Pakistani rupee"), ("INR", "Indian rupee"), ("AED", "UAE dirham"), ("SAR", "Saudi riyal"),
         ("EUR", "Euro"), ("GBP", "British pound"), ("CAD", "Canadian dollar"), ("AUD", "Australian dollar"),
         ("CNY", "Chinese yuan"), ("JPY", "Japanese yen"), ("TRY", "Turkish lira"), ("BDT", "Bangladeshi taka"),
         ("EGP", "Egyptian pound"), ("MYR", "Malaysian ringgit"), ("IDR", "Indonesian rupiah")]

SOURCES = {
    "metals": ("Gold-API.com", "https://gold-api.com"),
    "crypto": ("Coinbase", "https://www.coinbase.com"),
    "forex": ("Exchange Rate API", "https://www.exchangerate-api.com"),
}

_lock = threading.Lock()
_cache = {g: {"data": {}, "ts": 0.0, "next": 0.0, "busy": False} for g in TTL}


class MarketError(Exception):
    pass


def _http_json(url, headers=None, timeout=6):
    req = urllib.request.Request(url, headers=dict({"User-Agent": "SurMusic/1.0 (+https://surmusicradio.com)",
                                                    "Accept": "application/json"}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed https hosts below)
        raw = r.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise MarketError("response too large")
    return json.loads(raw.decode("utf-8"))


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and 0 < f < 1e12 else None       # reject NaN, zero, negative and silly values


# ---------------------------------------------------------------- one fetcher per source

def _fetch_crypto(cfg):
    out = {}
    for sym, key, _ in CRYPTO:
        try:
            data = _http_json(f"https://api.coinbase.com/v2/prices/{sym}-USD/spot")
        except Exception:        # one coin missing must not hide the others
            continue
        price = _num(((data or {}).get("data") or {}).get("amount")) if isinstance(data, dict) else None
        if price:
            out[key] = {"price": price, "change": None}
    return out


def _fetch_metals(cfg):
    out = {}
    for sym, key, _ in METALS:
        try:
            data = _http_json(f"https://api.gold-api.com/price/{sym}")
        except Exception:        # one metal missing must not hide the others
            continue
        price = _num(data.get("price")) if isinstance(data, dict) else None
        if price:
            out[key] = {"price": price, "change": None}
    return out


def _fetch_forex(cfg):
    data = _http_json("https://open.er-api.com/v6/latest/USD")
    rates = data.get("rates") if isinstance(data, dict) and data.get("result") == "success" else None
    if not isinstance(rates, dict):
        raise MarketError("no rates")
    out = {}
    for code, _ in FOREX:
        r = _num(rates.get(code))
        if r:
            out[f"usd-{code.lower()}"] = {"price": r, "change": None}
    for code in ("EUR", "GBP"):
        r = _num(rates.get(code))
        if r:
            out[f"{code.lower()}-usd"] = {"price": 1 / r, "change": None}
    return out


FETCHERS = {"crypto": _fetch_crypto, "metals": _fetch_metals, "forex": _fetch_forex}


# ---------------------------------------------------------------- refreshing

def _config_copy():
    return {}


def _refresh_group(group, cfg):
    st = _cache[group]
    try:
        data = FETCHERS[group](cfg)
        with _lock:
            if data:
                st["data"], st["ts"], st["next"] = data, time.time(), time.time() + TTL[group][0]
            else:
                st["next"] = time.time() + TTL[group][1]
    except Exception:
        with _lock:
            st["next"] = time.time() + TTL[group][1]       # keep the last good numbers, try again later
    finally:
        with _lock:
            st["busy"] = False


def refresh_now(cfg=None, groups=None):
    """Fetch the given groups right now (used by tests and by the background thread)."""
    cfg = cfg if cfg is not None else _config_copy()
    for g in groups or TTL:
        _refresh_group(g, cfg)


def trigger_refresh():
    """Start a background fetch for every group that is due. Returns immediately."""
    cfg_all = current_app.config
    if not cfg_all.get("MARKETS_ENABLED", True) or cfg_all.get("TESTING"):
        return
    cfg = _config_copy()
    due = []
    now = time.time()
    with _lock:
        for g, st in _cache.items():
            if not st["busy"] and now >= st["next"]:
                st["busy"] = True
                due.append(g)
    if due:
        threading.Thread(target=refresh_now, args=(cfg, due), daemon=True).start()


# ---------------------------------------------------------------- what the page shows

def fmt(price):
    if price is None:
        return ""
    return f"{price:,.2f}" if price >= 1 else f"{price:.4f}"


def _chg(change):
    if change is None:
        return "", ""
    return f"{change:+.2f}%", ("up" if change > 0 else "down" if change < 0 else "flat")


def _all_items():
    items = {}
    with _lock:
        for st in _cache.values():
            items.update(st["data"])
    return items


def _derived(items):
    """Gold and silver in local units, from the international price and the daily exchange rate."""
    out = {}

    def per(metal, rate_id, grams):
        m, r = items.get(metal), items.get(rate_id)
        return m["price"] / OZ_GRAMS * r["price"] * grams if m and r else None

    pairs = {"gold-pkr-tola": ("xau", "usd-pkr", TOLA_GRAMS), "gold-pkr-gram": ("xau", "usd-pkr", 1),
             "gold-inr-10g": ("xau", "usd-inr", 10), "gold-aed-gram": ("xau", "usd-aed", 1),
             "gold-sar-gram": ("xau", "usd-sar", 1), "silver-pkr-tola": ("xag", "usd-pkr", TOLA_GRAMS)}
    pkr = items.get("usd-pkr")
    if pkr:
        for code in ("eur", "gbp"):
            r = items.get(f"{code}-usd")
            if r:
                out[f"{code}-pkr"] = {"price": r["price"] * pkr["price"], "change": None}
        for code in ("aed", "sar"):
            r = items.get(f"usd-{code}")
            if r:
                out[f"{code}-pkr"] = {"price": pkr["price"] / r["price"], "change": None}
    for key, (metal, rate, grams) in pairs.items():
        v = per(metal, rate, grams)
        if v:
            out[key] = {"price": v, "change": None}
    return out


def _row(items, rid, label, unit):
    it = items.get(rid)
    text = fmt(it["price"]) if it else ""
    ctext, cdir = _chg(it["change"]) if it else ("", "")
    return {"id": rid, "label": label, "unit": unit, "text": text, "change": ctext, "dir": cdir}


def sections():
    """The groups of rows, in display order. Rows without a price are present but empty (the page fills them in)."""
    items = _all_items()
    items.update(_derived(items))
    fx = [_row(items, "usd-pkr", "US dollar to Pakistani rupee", "PKR"), _row(items, "eur-pkr", "Euro to Pakistani rupee", "PKR"),
          _row(items, "gbp-pkr", "British pound to Pakistani rupee", "PKR"), _row(items, "aed-pkr", "UAE dirham to Pakistani rupee", "PKR"),
          _row(items, "sar-pkr", "Saudi riyal to Pakistani rupee", "PKR")]
    fx += [_row(items, f"usd-{c.lower()}", f"US dollar to {name}", c) for c, name in FOREX if c != "PKR"]
    fx += [_row(items, "eur-usd", "Euro to US dollar", "USD"), _row(items, "gbp-usd", "British pound to US dollar", "USD")]
    return [
        {"key": "metals", "title": "Gold, silver and metals", "rows": [
            _row(items, key, name, "USD per ounce") for _, key, name in METALS]},
        {"key": "local", "title": "Gold and silver in local money (approximate)", "rows": [
            _row(items, "gold-pkr-tola", "Gold per tola (Pakistan)", "PKR"),
            _row(items, "gold-pkr-gram", "Gold per gram (Pakistan)", "PKR"),
            _row(items, "silver-pkr-tola", "Silver per tola (Pakistan)", "PKR"),
            _row(items, "gold-inr-10g", "Gold per 10 grams (India)", "INR"),
            _row(items, "gold-aed-gram", "Gold per gram (UAE)", "AED"),
            _row(items, "gold-sar-gram", "Gold per gram (Saudi Arabia)", "SAR")]},
        {"key": "crypto", "title": "Crypto", "rows": [_row(items, key, name, "USD") for _, key, name in CRYPTO]},
        {"key": "forex", "title": "Dollar rate and currency rates today", "rows": fx},
    ]


def view():
    """Sections for a template (also starts a background refresh if the numbers are old)."""
    try:
        trigger_refresh()
    except Exception:
        pass
    secs = sections()
    for s in secs:
        s["ready"] = any(r["text"] for r in s["rows"])
        s["source"] = SOURCES.get(s["key"] if s["key"] != "local" else "metals")
    return secs


def api_payload():
    secs = view()
    items = {r["id"]: {"text": r["text"], "change": r["change"], "dir": r["dir"]}
             for s in secs for r in s["rows"] if r["text"]}
    stamps = [st["ts"] for st in _cache.values() if st["ts"]]
    updated = datetime.fromtimestamp(max(stamps), timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if stamps else ""
    return {"updated": updated, "items": items}
