"""Trending searches that update by themselves (Google Trends public feed, no key needed).

Every 30 minutes a background thread reads the "Trending now" feed for a few countries, keeps only the topics a
radio site can really help with (matches, news, elections, war, weather, debates, fuel, gold, the dollar, Bitcoin, songs and movies)
and drops the rest. The terms are shown on the /trending page and on the sports, news and home pages, each linked
to the radio or prices page that fits. If the feed cannot be read, the last good list stays; if there never was
one, the block is simply not shown.
"""
import re
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET

from flask import current_app

GEOS = [("PK", "Pakistan"), ("IN", "India"), ("BD", "Bangladesh"), ("AE", "UAE"), ("SA", "Saudi Arabia"),
        ("TR", "Turkey"), ("EG", "Egypt"), ("GB", "UK"), ("DE", "Germany"), ("FR", "France"), ("IT", "Italy"),
        ("ES", "Spain"), ("US", "USA"), ("CA", "Canada"), ("AU", "Australia"), ("NG", "Nigeria"),
        ("ZA", "South Africa"), ("ID", "Indonesia"), ("BR", "Brazil"), ("MX", "Mexico")]
TTL = 1800          # refresh every 30 minutes
RETRY = 600         # after a failure, wait 10 minutes

SPORT = re.compile(r"\b(vs|v)\b|cricket|\b(ipl|psl|bbl|t20|t20i|odi|test series|asia cup|world cup|champions league|"
                   r"premier league|la ?liga|serie a|bundesliga|ligue 1|fifa|uefa|nba|nfl|mlb|nhl|mls|f1|formula 1|"
                   r"ufc|wwe|olympics|ballon d'or|standings|fixtures|scorecard|live score|commentary|match)\b|\bfc\b",
                   re.I)
MONEY = re.compile(r"\b(gold|silver|dollar|usd|rupee|dirham|riyal|euro|pound|bitcoin|btc|ethereum|crypto|exchange rate|"
                   r"currency|stock market|psx|sensex|nifty|dow jones|nasdaq|petrol|diesel|fuel|petroleum|oil price|"
                   r"gas price|inflation|interest rate)\b", re.I)
DEBATE = re.compile(r"\b(debate|debates|town hall|interview|press conference|speech|address)\b", re.I)
NEWS = re.compile(r"\b(election|elections|midterm|midterms|vote|voting|poll|polls|results|senate|congress|parliament|"
                  r"government|minister|prime minister|president|summit|treaty|sanctions|protest|protests|strike|budget|"
                  r"war|ceasefire|nato|ukraine|russia|gaza|israel|iran|taiwan|military|troops|missile|"
                  r"earthquake|flood|floods|storm|hurricane|cyclone|typhoon|wildfire|weather|forecast|rain|heatwave|snow|"
                  r"temperature|smog|energy crisis|economy|tax|news|breaking|"
                  r"wetter|m[eé]t[eé]o|meteo|tiempo|elecciones|[eé]lections?|wahl|wahlen|guerre|krieg|guerra)\b", re.I)
MUSIC = re.compile(r"\b(song|songs|music|album|concert|tour|lyrics|singer|grammy|grammys|playlist|remix|"
                   r"new release|coke studio)\b", re.I)
MOVIE = re.compile(r"\b(movie|movies|film|films|trailer|box office|series|netflix|oscar|oscars|bollywood|hollywood|"
                   r"drama|episode|cast)\b", re.I)
BLOCK = re.compile(r"\b(sex|porn|nude|naked|leaked|scandal|rape|murder|suicide|killed|kills|dead|death|dies|died|"
                   r"shooting|bomb|bombing|terror|lottery|casino|betting|jackpot|ebola|virus)\b", re.I)

_lock = threading.Lock()
_state = {"data": {}, "ts": 0.0, "next": 0.0, "busy": False}


class TrendError(Exception):
    pass


def _http_text(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "SurMusic/1.0 (+https://surmusicradio.com)",
                                               "Accept": "application/rss+xml, application/xml, text/xml"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed https host)
        raw = r.read(512 * 1024 + 1)
    if len(raw) > 512 * 1024:
        raise TrendError("feed too large")
    return raw.decode("utf-8", "replace")


def parse_feed(text):
    """[(term, traffic_text)] from a Google Trends RSS feed. Refuses XML with entity tricks."""
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise TrendError("unsafe xml")
    root = ET.fromstring(text)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        traffic = ""
        for child in item:
            if child.tag.endswith("approx_traffic"):
                traffic = (child.text or "").strip()
        if title:
            out.append((title, traffic))
    return out


def classify(term):
    """(kind, link) for a term a radio site can help with, or None to drop it."""
    t = " ".join(term.split())
    if not t or len(t) > 60 or BLOCK.search(t) or not re.search(r"[A-Za-z]", t):
        return None
    if SPORT.search(t):
        return "sports", "/genre/sports"
    if MONEY.search(t):
        return "markets", "/markets"
    if DEBATE.search(t):
        return "debate", "/genre/talk"
    if NEWS.search(t):
        return "news", "/genre/news"
    if MOVIE.search(t):
        return "movies", "/bollywood" if re.search(r"bollywood|hindi|khan|kapoor", t, re.I) else "/hollywood"
    if MUSIC.search(t):
        return "music", "/lollywood" if re.search(r"urdu|pakistan|coke studio", t, re.I) else "/genre/pop"
    return None


def _clean(feed):
    seen, rows = set(), []
    for term, traffic in feed:
        c = classify(term)
        key = term.lower()
        if c and key not in seen:
            seen.add(key)
            rows.append({"term": " ".join(term.split()), "traffic": traffic, "kind": c[0], "href": c[1]})
    return rows[:10]


def refresh_now(fetch=None):
    fetch = fetch or _http_text
    data, ok = {}, 0
    for geo, name in GEOS:
        try:
            rows = _clean(parse_feed(fetch(f"https://trends.google.com/trending/rss?geo={geo}")))
            ok += 1
        except Exception:
            continue
        if rows:
            data[geo] = {"name": name, "rows": rows}
    with _lock:
        if ok:
            _state["data"], _state["ts"], _state["next"] = data, time.time(), time.time() + TTL
        else:
            _state["next"] = time.time() + RETRY       # keep the old list
        _state["busy"] = False


def trigger_refresh():
    cfg = current_app.config
    if not cfg.get("TRENDS_ENABLED", True) or cfg.get("TESTING"):
        return
    with _lock:
        if _state["busy"] or time.time() < _state["next"]:
            return
        _state["busy"] = True
    threading.Thread(target=refresh_now, daemon=True).start()


def by_country():
    """[{geo, name, rows}] for countries that have something, Pakistan first."""
    try:
        trigger_refresh()
    except Exception:
        pass
    with _lock:
        data = dict(_state["data"])
    return [dict(geo=g, **v) for g, v in data.items()]


def top(limit=8):
    """A short mixed list for a strip on other pages: the first terms of each country, no repeats."""
    out, seen = [], set()
    countries = by_country()
    for i in range(3):
        for c in countries:
            if i < len(c["rows"]):
                r = c["rows"][i]
                if r["term"].lower() not in seen:
                    seen.add(r["term"].lower())
                    out.append(dict(r, geo=c["name"]))
    return out[:limit]


def updated_text():
    with _lock:
        ts = _state["ts"]
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(ts)) if ts else ""
