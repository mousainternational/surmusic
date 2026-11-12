"""Podcasts from the free Apple Podcasts directory (search/lookup, no key) and the podcasters' own RSS feeds.

Nothing is stored on our server except a small in-memory cache: the audio always plays straight from the podcaster's
own server, and every show page names the podcaster. Every request has a time limit and a size limit."""
import ipaddress
from concurrent.futures import ThreadPoolExecutor
import json
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape

API = "https://itunes.apple.com"
UA = "SurMusicRadio/1.0 (+https://www.surmusicradio.com)"
# Pakistani and well-known Islamic scholars: (search words, a word that must be in the show or podcaster name).
# Only the ones that really have a podcast in the Apple directory are shown; the others are skipped by themselves.
SCHOLARS = [("Dr Israr Ahmed", "israr"), ("Engineer Muhammad Ali Mirza", "mirza"), ("Mufti Tariq Masood", "masood"),
            ("Maulana Tariq Jameel", "jameel"), ("Javed Ahmad Ghamidi", "ghamidi"), ("Mufti Taqi Usmani", "usmani"),
            ("Molana Ilyas Qadri", "qadri"), ("Maulana Ishaq", "ishaq"), ("Mufti Menk", "menk"), ("Nouman Ali Khan", "nouman"),
            ("Yasir Qadhi", "qadhi"), ("Dr Zakir Naik", "zakir"), ("Molana Tariq Jamil bayan", "jamil")]
# slug -> (page title, [recipe steps]). A step is ("scholars",), ("chart", country) or ("search", words, country).
CATEGORIES = {
    "islamic-scholars": ("Islamic scholars", [("scholars",), ("search", "urdu islamic bayan", "PK"), ("search", "islamic lectures urdu", "PK")]),
    "urdu": ("Urdu podcasts", [("search", "urdu podcast", "PK"), ("search", "pakistan podcast", "PK"), ("search", "urdu stories", "PK")]),
    "islamic": ("Islamic lectures & Quran", [("search", "islamic lectures", "US"), ("search", "quran tafseer", "US"), ("search", "seerah", "US")]),
    "hindi": ("Hindi podcasts", [("search", "hindi podcast", "IN"), ("search", "hindi stories", "IN")]),
    "cricket": ("Cricket", [("search", "cricket podcast", "IN"), ("search", "cricket podcast", "PK")]),
    "bollywood": ("Bollywood & film", [("search", "bollywood podcast", "IN")]),
    "news": ("News & talk", [("search", "news podcast", "PK"), ("search", "news podcast", "US")]),
    "kids": ("Kids & stories", [("search", "kids stories podcast", "US"), ("search", "bachon ki kahaniyan", "PK")]),
    "top-pakistan": ("Top podcasts in Pakistan", [("chart", "pk")]),
    "top-india": ("Top podcasts in India", [("chart", "in")]),
    "top-world": ("Top podcasts worldwide", [("chart", "us")]),
}
STRIP_ORDER = [("islamic-scholars", 12), ("top-pakistan", 8), ("urdu", 5), ("islamic", 5), ("hindi", 3), ("cricket", 3), ("news", 3), ("kids", 3)]
FEATURED_TTL, SHOW_TTL, MAX_SHOWS = 12 * 3600, 3600, 40
MAX_JSON, MAX_FEED = 1_000_000, 2_500_000

_lock = threading.Lock()
_building = set()
_cat = {}                                     # slug -> (time, rows)
_featured = {"at": 0.0, "rows": []}
_shows = {}                                   # id -> (time, show)

DEMO_SHOWS = [
    {"id": "1001", "name": "Sample Talk Show", "artist": "Demo Studio", "img": "https://example.com/a.jpg", "feed": ""},
    {"id": "1002", "name": "Sample Stories", "artist": "Demo Studio", "img": "https://example.com/b.jpg", "feed": ""},
    {"id": "1003", "name": "Sample News Hour", "artist": "Demo Studio", "img": "https://example.com/c.jpg", "feed": ""},
]


def _public_host(host):
    """True when the name only points to public internet addresses (never our own network)."""
    try:
        for fam, _t, _p, _c, sa in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP):
            ip = ipaddress.ip_address(sa[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except (OSError, ValueError):
        return False


class _Safe(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urllib.parse.urlsplit(newurl)
        if u.scheme != "https" or not u.hostname or not _public_host(u.hostname):
            raise urllib.error.URLError("redirect not allowed")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _get(url, limit, timeout=7):
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" or not u.hostname or not _public_host(u.hostname):
        raise ValueError("blocked address")
    opener = urllib.request.build_opener(_Safe)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with opener.open(req, timeout=timeout) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError("too large")
    return data


def _api(path, **params):
    return json.loads(_get(API + path + "?" + urllib.parse.urlencode(params), MAX_JSON).decode("utf-8", "replace"))


def _https(url):
    url = (url or "").strip()
    if url.startswith("http://"):
        url = "https://" + url[7:]
    return url if url.startswith("https://") and len(url) < 1000 else ""


def _row(r):
    sid = str(r.get("collectionId") or "")
    if not sid.isdigit():
        return None
    img = _https(r.get("artworkUrl100") or r.get("artworkUrl60") or "")
    return {"id": sid, "name": (r.get("collectionName") or "Podcast")[:120], "artist": (r.get("artistName") or "")[:100],
            "img": img.replace("100x100", "200x200") if img else "", "feed": _https(r.get("feedUrl") or "")}


def _chart(cc):
    data = json.loads(_get(f"https://rss.applemarketingtools.com/api/v2/{cc}/podcasts/top/30/podcasts.json", MAX_JSON).decode("utf-8", "replace"))
    out = []
    for r in data.get("feed", {}).get("results", []):
        sid = str(r.get("id") or "")
        img = _https(r.get("artworkUrl100") or "")
        if sid.isdigit():
            out.append({"id": sid, "name": (r.get("name") or "Podcast")[:120], "artist": (r.get("artistName") or "")[:100],
                        "img": img.replace("100x100", "200x200") if img else "", "feed": ""})
    return out


def _build(slug):
    out, seen = [], set()
    for step in CATEGORIES[slug][1]:
        try:
            if step[0] == "chart":
                rows = _chart(step[1])
            elif step[0] == "scholars":
                def one(pair):
                    words, must = pair
                    try:
                        data = _api("/search", term=words, media="podcast", limit=5, country="US")
                    except Exception:
                        return None
                    for r in data.get("results", []):
                        row = _row(r)
                        if row and must in (row["name"] + " " + row["artist"]).lower():
                            return row
                    return None
                with ThreadPoolExecutor(6) as pool:
                    rows = [x for x in pool.map(one, SCHOLARS) if x]
            else:
                data = _api("/search", term=step[1], media="podcast", limit=12, country=step[2])
                rows = [x for x in (_row(r) for r in data.get("results", [])) if x]
        except Exception:
            continue
        for row in rows:
            if row["id"] not in seen and row["img"]:
                seen.add(row["id"]); out.append(row)
    return out


def category(slug, demo=False):
    """Shows of one page (e.g. Islamic scholars, top in Pakistan). Refreshed every 12 hours by itself; the last good copy
    is kept if Apple is slow."""
    if slug not in CATEGORIES:
        return []
    if demo:
        return DEMO_SHOWS
    with _lock:
        hit = _cat.get(slug)
        if hit and time.time() - hit[0] < FEATURED_TTL and hit[1]:
            return hit[1]
        if slug in _building:                       # someone else is already fetching it: use the old copy, no second fetch
            return hit[1] if hit else []
        _building.add(slug)
    try:
        rows = _build(slug)
    finally:
        with _lock:
            _building.discard(slug)
    with _lock:
        if rows:
            _cat[slug] = (time.time(), rows)
        elif hit:
            _cat[slug] = (time.time() - FEATURED_TTL + 120, hit[1])      # keep the old list, try again in two minutes
        return _cat[slug][1] if slug in _cat else []


def featured(demo=False):
    """The moving strip: Islamic scholars first, then the charts and a few of each page."""
    if demo:
        return DEMO_SHOWS
    with ThreadPoolExecutor(8) as pool:
        lists = list(pool.map(lambda sn: category(sn[0])[:sn[1]], STRIP_ORDER))
    out, seen = [], set()
    for rows in lists:
        for row in rows:
            if row["id"] not in seen:
                seen.add(row["id"]); out.append(row)
    return out


def search(q, demo=False):
    q = (q or "").strip()[:60]
    if not q:
        return []
    if demo:
        return [s for s in DEMO_SHOWS if q.lower() in s["name"].lower()]
    try:
        data = _api("/search", term=q, media="podcast", limit=24)
    except Exception:
        return []
    return [x for x in (_row(r) for r in data.get("results", [])) if x]


def _text(el, tag):
    found = el.find(tag)
    return (found.text or "").strip() if found is not None and found.text else ""


def _clean(html, n):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html or ""))).strip()[:n]


def parse_feed(xml_bytes, sid):
    """Episodes from an RSS feed: [{uuid, name, url, favicon, country, tags, ...}] as the player expects, newest first."""
    root = ET.fromstring(xml_bytes)
    ch = root.find("channel")
    if ch is None:
        return "", [], ""
    title = _text(ch, "title")[:120]
    art = ""
    for el in ch.iter():
        if el.tag.endswith("}image") and el.get("href"):
            art = _https(el.get("href")); break
    if not art:
        im = ch.find("image/url")
        art = _https(im.text if im is not None and im.text else "")
    eps = []
    for i, it in enumerate(ch.findall("item")[:120]):
        enc = it.find("enclosure")
        url = _https(enc.get("url") if enc is not None else "")
        if not url or "audio" not in ((enc.get("type") or "audio") if enc is not None else "audio"):
            continue
        eps.append({"uuid": f"pod-{sid}-{i}", "name": (_text(it, "title") or "Episode")[:140], "url": url,
                    "favicon": art, "country": title, "tags": "podcast", "bitrate": 0, "clicks": 0,
                    "date": _text(it, "pubDate")[:16], "about": _clean(_text(it, "description"), 220)})
    return title, eps, art


def show(sid, demo=False):
    """(show row, episodes) or (None, [])"""
    if not str(sid).isdigit():
        return None, []
    sid = str(sid)
    if demo:
        row = next((s for s in DEMO_SHOWS if s["id"] == sid), None)
        eps = [{"uuid": f"pod-{sid}-{i}", "name": f"Sample episode {i + 1}", "url": f"https://example.com/{i}.mp3",
                "favicon": "", "country": row["name"], "tags": "podcast", "bitrate": 0, "clicks": 0, "date": "", "about": ""}
               for i in range(3)] if row else []
        return row, eps
    with _lock:
        hit = _shows.get(sid)
    if hit and time.time() - hit[0] < SHOW_TTL:
        return hit[1]
    try:
        data = _api("/lookup", id=sid, entity="podcast")
        row = next((x for x in (_row(r) for r in data.get("results", [])) if x), None)
        if not row or not row["feed"]:
            return (hit[1] if hit else (None, []))
        _title, eps, art = parse_feed(_get(row["feed"], MAX_FEED, timeout=9), sid)
        if art and not row["img"]:
            row["img"] = art
        value = (row, eps)
    except Exception:
        return hit[1] if hit else (None, [])
    with _lock:
        _shows[sid] = (time.time(), value)
        while len(_shows) > MAX_SHOWS:
            _shows.pop(min(_shows, key=lambda k: _shows[k][0]))
    return value
