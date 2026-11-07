"""World news headlines for the strip under the header, chosen by the visitor's country.

The headlines come from Google News' public RSS feed for that country (English edition). Nothing is stored in the
database: the last good list for each country stays in memory for 15 minutes and is refreshed in the background, so a
slow or blocked feed never slows a page down. If the feed cannot be read the strip simply stays hidden.
"""
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

TTL = 15 * 60
_ENGLISH_EDITIONS = {"US", "GB", "IN", "AU", "CA", "NZ", "IE", "SG", "ZA", "NG", "KE", "GH", "PK", "PH", "MY", "BD",
                     "TZ", "UG", "ZW", "NA", "BW", "ET", "LB", "SA", "AE", "IL", "HK"}
_SKIP = re.compile(r"\b(porn|pornography|sex tape|nude|naked|onlyfans|escort)\b", re.I)
_lock = threading.Lock()
_cache = {}          # country code -> (fetched_at, items)
_busy = set()


def _edition(cc):
    hl = f"en-{cc}" if cc in _ENGLISH_EDITIONS else "en"
    return urllib.parse.urlencode({"hl": hl, "gl": cc, "ceid": f"{cc}:en"})


def _feed_url(cc):
    cc = cc if re.fullmatch(r"[A-Z]{2}", cc or "") else "US"
    return f"https://news.google.com/rss?{_edition(cc)}"


# What the strip mixes: top stories, politics, business, entertainment (film and showbiz), sports; Bollywood and
# Lollywood stories too for readers in South Asia.
_TOPICS = ["NATION", "BUSINESS", "ENTERTAINMENT", "SPORTS"]


def _feed_urls(cc):
    cc = cc if re.fullmatch(r"[A-Z]{2}", cc or "") else "US"
    ed = _edition(cc)
    urls = [f"https://news.google.com/rss?{ed}"]
    urls += [f"https://news.google.com/rss/headlines/section/topic/{t}?{ed}" for t in _TOPICS]
    if cc in ("PK", "IN", "BD", "AE", "SA", "GB", "US", "CA", "AU"):
        q = urllib.parse.quote("bollywood OR lollywood OR hollywood when:2d")
        urls.append(f"https://news.google.com/rss/search?q={q}&{ed}")
    return urls


def parse(text, limit=14):
    """[{t: headline, s: source, u: link}] from an RSS feed. Refuses XML with entity tricks."""
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    out = []
    for item in root.iter("item"):
        title = " ".join((item.findtext("title") or "").split())
        link = (item.findtext("link") or "").strip()
        if not title or not link.startswith("https://") or len(link) > 600 or _SKIP.search(title):
            continue
        head, _, source = title.rpartition(" - ")
        if not head:
            head, source = title, ""
        out.append({"t": head[:140], "s": source[:40], "u": link})
        if len(out) >= limit:
            break
    return out


def _fetch(url):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "SurMusic/1.0 (+https://surmusicradio.com)", "Accept": "application/rss+xml, application/xml"})
        with urllib.request.urlopen(req, timeout=5) as r:  # noqa: S310 (fixed https host)
            raw = r.read(600 * 1024 + 1)
        return parse(raw.decode("utf-8", "replace"), limit=6) if len(raw) <= 600 * 1024 else []
    except Exception:
        return []


def mix(lists, limit=24):
    """Round-robin over the feeds (so politics, film, business and sports all appear), without repeats."""
    out, seen = [], set()
    for i in range(max((len(x) for x in lists), default=0)):
        for lst in lists:
            if i < len(lst):
                key = lst[i]["t"].lower()[:60]
                if key not in seen:
                    seen.add(key)
                    out.append(lst[i])
    return out[:limit]


def _load(cc):
    # Fetch the small RSS feeds in parallel so the header ticker does not wait through
    # several sequential network timeouts before the first headlines become available.
    urls = _feed_urls(cc)
    with ThreadPoolExecutor(max_workers=min(4, len(urls))) as ex:
        lists = list(ex.map(_fetch, urls))
    items = mix(lists)
    with _lock:
        if items or cc not in _cache:
            _cache[cc] = (time.time(), items)
        else:                                   # keep the last good list, try again in a while
            _cache[cc] = (time.time() - TTL + 120, _cache[cc][1])
        _busy.discard(cc)
        if len(_cache) > 120:
            for k in sorted(_cache, key=lambda k: _cache[k][0])[:20]:
                _cache.pop(k, None)


def get(cc):
    """Headlines for a country (or the world when unknown). Never waits for the network."""
    cc = cc if re.fullmatch(r"[A-Z]{2}", cc or "") else "US"
    with _lock:
        hit = _cache.get(cc)
        stale = not hit or time.time() - hit[0] > TTL
        start = stale and cc not in _busy
        if start:
            _busy.add(cc)
    if start:
        threading.Thread(target=_load, args=(cc,), daemon=True).start()
    return hit[1] if hit else []
