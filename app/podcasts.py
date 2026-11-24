"""Podcasts from the free Apple Podcasts directory (search/lookup, no key) and the podcasters' own RSS feeds.

Nothing is stored on our server except a small in-memory cache: the audio always plays straight from the podcaster's
own server, and every show page names the podcaster. Every request has a time limit and a size limit."""
import ipaddress
from concurrent.futures import ThreadPoolExecutor
import json
import os
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
            ("Yasir Qadhi", "qadhi"), ("Dr Zakir Naik", "zakir"), ("Molana Tariq Jamil bayan", "jamil"),
            ("Sayed Ammar Nakshawani", "nakshawani"), ("Sheikh Mohammad Ali Shomali", "shomali"), ("Allama Syed Zameer Akhtar Naqvi", "naqvi"),
            ("Allama Talib Johri", "johri"), ("Maulana Syed Kalbe Jawad", "kalbe"), ("Maulana Syed Ali Raza Rizvi", "rizvi"), ("Hassan Allahyari", "allahyari")]
TAKE_TURNS = {"islamic"}      # pages whose searches are different kinds of shows (lectures, tafseer, seerah, majlis, Shia): they take turns, so every kind is near the top
# slug -> (page title, [recipe steps]). A step is ("scholars",), ("chart", country) or ("search", words, country).
CATEGORIES = {
    "islamic-scholars": ("Islamic scholars", [("scholars",), ("search", "urdu islamic bayan", "PK"), ("search", "islamic lectures urdu", "PK")]),
    "urdu": ("Urdu podcasts", [("search", "urdu podcast", "PK"), ("search", "pakistan podcast", "PK")]),
    "islamic": ("Islamic lectures & Quran", [("search", "islamic lectures", "US"), ("search", "quran tafseer", "US"), ("search", "seerah", "US"),
                                              ("search", "ahlulbayt majlis podcast", "US"), ("search", "shia islam podcast", "US")]),
    "hindi": ("Hindi podcasts", [("search", "hindi podcast", "IN"), ("search", "hindi talk show", "IN")]),
    "cricket": ("Cricket", [("search", "cricket podcast", "IN"), ("search", "cricket podcast", "PK")]),
    "bollywood": ("Bollywood & film", [("search", "bollywood podcast", "IN")]),
    "news": ("News & talk", [("search", "news podcast", "PK"), ("search", "news podcast", "US")]),
    "kids": ("Kids & stories", [("search", "kids stories podcast", "US"), ("search", "bachon ki kahaniyan", "PK")]),
    "celebrity": ("Celebrity & interview podcasts", [("search", "celebrity interviews podcast", "US"), ("search", "celebrity podcast", "US"), ("search", "urdu interviews podcast", "PK"), ("search", "bollywood celebrity interviews", "IN")]),
    "christian": ("Christian sermons & Bible", [("search", "christian sermons podcast", "US"), ("search", "bible study podcast", "US"), ("search", "gospel worship podcast", "US")]),
    "jewish": ("Jewish learning & Torah", [("search", "torah podcast", "US"), ("search", "jewish learning podcast", "US"), ("search", "judaism podcast", "IL")]),
    "hindu": ("Hindu spiritual talks", [("search", "bhagavad gita podcast", "IN"), ("search", "hindu spiritual talks podcast", "IN"), ("search", "bhajan kirtan podcast", "IN")]),
    "sikh": ("Sikh Gurbani & katha", [("search", "gurbani katha podcast", "IN"), ("search", "sikh podcast", "US")]),
    "buddhist": ("Buddhist dharma talks", [("search", "buddhist dharma talks podcast", "US"), ("search", "buddhism meditation podcast", "US")]),
    "business": ("Business", [("search", "business podcast", "US"), ("search", "entrepreneurship startup podcast", "US"), ("search", "business podcast", "PK"), ("search", "business podcast", "IN")]),
    "science": ("Science", [("search", "science podcast", "US"), ("search", "space astronomy podcast", "US"), ("search", "science podcast", "IN")]),
    "technology": ("Technology", [("search", "technology podcast", "US"), ("search", "tech news podcast", "US"), ("search", "technology podcast", "IN"), ("search", "technology podcast", "PK")]),
    "ai": ("Artificial intelligence", [("search", "artificial intelligence podcast", "US"), ("search", "AI machine learning podcast", "US"), ("search", "ChatGPT AI podcast", "IN")]),
    "education": ("Education & learning", [("search", "education podcast", "US"), ("search", "study tips learning podcast", "US"), ("search", "online courses skills podcast", "US")]),
    "health": ("Health & fitness", [("search", "health fitness podcast", "US"), ("search", "healthy lifestyle nutrition podcast", "US"), ("search", "mental health wellbeing podcast", "US")]),
    "motivation": ("Motivation & self-growth", [("search", "motivation podcast", "US"), ("search", "self improvement podcast", "US"), ("search", "success mindset podcast", "US")]),
    "languages": ("Learn languages", [("search", "learn english podcast", "US"), ("search", "learn languages podcast", "US"), ("search", "english speaking practice podcast", "IN")]),
    "arts": ("Arts & culture", [("search", "arts podcast", "US"), ("search", "books literature podcast", "US"), ("search", "arts culture podcast", "IN")]),
    "comedy": ("Comedy", [("search", "comedy podcast", "US"), ("search", "funny stories comedy podcast", "US"), ("search", "comedy podcast", "IN"), ("search", "comedy podcast", "PK")]),
    "fiction": ("Fiction & audio stories", [("search", "fiction audio drama podcast", "US"), ("search", "audio stories podcast", "US")]),
    "government": ("Government & politics", [("search", "politics podcast", "US"), ("search", "government policy podcast", "US"), ("search", "politics podcast", "PK")]),
    "history": ("History", [("search", "history podcast", "US"), ("search", "world history podcast", "US"), ("search", "history podcast", "IN")]),
    "leisure": ("Hobbies & leisure", [("search", "hobbies podcast", "US"), ("search", "travel food games podcast", "US")]),
    "music": ("Music talk & interviews", [("search", "music interviews podcast", "US"), ("search", "music podcast", "IN"), ("search", "music podcast", "PK")]),
    "society": ("Society & culture", [("search", "society culture podcast", "US"), ("search", "relationships family podcast", "US"), ("search", "society culture podcast", "PK")]),
    "sports": ("Sports", [("search", "sports podcast", "US"), ("search", "football podcast", "GB"), ("search", "sports podcast", "IN"), ("search", "sports podcast", "PK")]),
    "true-crime": ("True crime & mysteries", [("search", "true crime podcast", "US"), ("search", "mystery investigation podcast", "US")]),
    "tv-film": ("TV & film", [("search", "tv film podcast", "US"), ("search", "movie reviews podcast", "US"), ("search", "tv film podcast", "IN")]),
    "top-pakistan": ("Top podcasts in Pakistan", [("chart", "pk")]),
    "top-india": ("Top podcasts in India", [("chart", "in")]),
    "top-world": ("Top podcasts worldwide", [("chart", "us")]),
}
# Countries with their own Apple chart ("Top podcasts in <country>"): code -> name. A visitor is shown the chart of his own country.
_NEAR_THE = {"pk": "Pakistan", "in": "India", "us": "the United States", "gb": "the United Kingdom", "ca": "Canada", "au": "Australia",
        "ae": "the UAE", "sa": "Saudi Arabia", "qa": "Qatar", "kw": "Kuwait", "om": "Oman", "bh": "Bahrain", "eg": "Egypt", "tr": "Türkiye",
        "bd": "Bangladesh", "lk": "Sri Lanka", "np": "Nepal", "my": "Malaysia", "sg": "Singapore", "id": "Indonesia", "ph": "the Philippines",
        "de": "Germany", "fr": "France", "it": "Italy", "es": "Spain", "nl": "the Netherlands", "se": "Sweden", "no": "Norway", "ie": "Ireland",
        "br": "Brazil", "mx": "Mexico", "ar": "Argentina", "za": "South Africa", "ng": "Nigeria", "ke": "Kenya", "ma": "Morocco", "dz": "Algeria",
        "jo": "Jordan", "lb": "Lebanon", "il": "Israel", "jp": "Japan", "kr": "South Korea", "ru": "Russia", "ua": "Ukraine", "pl": "Poland"}
from .topics import COUNTRY_PAGES as _CP                      # every country of the site: each gets its own "Top podcasts in <country>" chart
NEAR = {v["code"].lower(): v["label"] for v in _CP.values() if v.get("code")}
NEAR.update({k: n for k, n in _NEAR_THE.items() if k in NEAR or True})

# Religion on the home page is neutral: the row starts with a mix of all faiths and the visitor may choose one. Nobody's belief is guessed from the country.
FAITHS = [("islamic-scholars", "Islamic"), ("christian", "Christian"), ("jewish", "Jewish"), ("hindu", "Hindu"), ("sikh", "Sikh"), ("buddhist", "Buddhist")]
STRIP_ORDER = [("top-world", 12), ("celebrity", 10), ("faiths", 12), ("technology", 3), ("ai", 3), ("business", 3), ("science", 2), ("news", 3), ("cricket", 3), ("urdu", 3), ("hindi", 3), ("kids", 2)]
FEATURED_TTL, SHOW_TTL, MAX_SHOWS = 12 * 3600, 3600, 40
MAX_JSON, MAX_FEED = 1_000_000, 2_500_000

_errors = {}                                  # slug -> last error text (shown on /api/podcasts/status, so a problem can be seen)
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


def _cut_feed(data, limit):
    """A podcast feed bigger than the limit: keep the newest episodes (they come first) and close the XML after the last whole item."""
    head = data[:limit]
    end = head.rfind(b"</item>")
    if end < 0:
        raise ValueError("too large")
    return head[:end + len(b"</item>")] + b"</channel></rss>"


def _get(url, limit, timeout=7, partial=False):
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" or not u.hostname or not _public_host(u.hostname):
        raise ValueError("blocked address")
    opener = urllib.request.build_opener(_Safe)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with opener.open(req, timeout=timeout) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        if partial:
            return _cut_feed(data, limit)
        raise ValueError("too large")
    return data


def _api(path, **params):
    return json.loads(_get(API + path + "?" + urllib.parse.urlencode(params), MAX_JSON).decode("utf-8", "replace"))


def _https(url):
    url = (url or "").strip()
    if url.startswith("http://"):
        url = "https://" + url[7:]
    return url if url.startswith("https://") and len(url) < 1000 else ""


_ADULT = re.compile(r"\b(sex|sexy|sexual|erotic|erotica|porn|xxx|nsfw|18\+|adult|kamasutra|hot stor|nude|fetish|dirty)", re.I)


def _family_ok(name, artist):
    """Family-friendly lists only: adult shows are never listed."""
    return not _ADULT.search(f"{name} {artist}")


def _row(r, strict=True):
    """One show. strict=True (lists): shows Apple marks explicit are left out. A show someone opens directly is always opened."""
    sid = str(r.get("collectionId") or "")
    if not sid.isdigit() or (strict and r.get("collectionExplicitness") == "explicit"):
        return None
    if not _family_ok(r.get("collectionName") or "", r.get("artistName") or ""):
        return None
    img = _https(r.get("artworkUrl100") or r.get("artworkUrl60") or "")
    return {"id": sid, "name": (r.get("collectionName") or "Podcast")[:120], "artist": (r.get("artistName") or "")[:100],
            "img": img.replace("100x100", "200x200") if img else "", "feed": _https(r.get("feedUrl") or "")}


def index_on():
    return bool(os.environ.get("PODCASTINDEX_KEY") and os.environ.get("PODCASTINDEX_SECRET"))


def index_search(term, limit=20):
    """A second free directory (podcastindex.org, needs the owner's free key). Returns show rows that also have an Apple id,
    so every show page keeps working. [] when no key or on any error."""
    if not index_on():
        return []
    try:
        import hashlib
        key, secret = os.environ["PODCASTINDEX_KEY"].strip(), os.environ["PODCASTINDEX_SECRET"].strip()
        stamp = str(int(time.time()))
        req = urllib.request.Request("https://api.podcastindex.org/api/1.0/search/byterm?" + urllib.parse.urlencode({"q": term, "max": limit}), headers={
            "User-Agent": UA, "X-Auth-Date": stamp, "X-Auth-Key": key,
            "Authorization": hashlib.sha1((key + secret + stamp).encode()).hexdigest()})
        with urllib.request.urlopen(req, timeout=8) as r:  # noqa: S310 (fixed https host)
            data = json.loads(r.read(MAX_JSON + 1).decode("utf-8", "replace"))
        out = []
        for f in data.get("feeds") or []:
            sid = str(f.get("itunesId") or "")
            if not sid.isdigit() or f.get("explicit"):
                continue
            title, author = (f.get("title") or ""), (f.get("author") or f.get("ownerName") or "")
            if not _family_ok(title, author):
                continue
            img = _https(f.get("artwork") or f.get("image") or "")
            out.append({"id": sid, "name": title[:120] or "Podcast", "artist": author[:100], "img": img, "feed": _https(f.get("url") or "")})
        return out
    except Exception:
        return []


def _txt(v):
    return v if isinstance(v, str) else ""


def _chart(cc):
    try:
        return _chart_v2(cc)
    except Exception:                                  # Apple's older chart address, used when the new one is slow or down
        data = json.loads(_get(f"https://itunes.apple.com/{cc}/rss/toppodcasts/limit=50/json", MAX_JSON).decode("utf-8", "replace"))
        out = []
        for e in data.get("feed", {}).get("entry", []):
            sid = str(((e.get("id") or {}).get("attributes") or {}).get("im:id") or "")
            imgs = e.get("im:image") or []
            img = _https((imgs[-1] or {}).get("label") if imgs else "")
            name = ((e.get("im:name") or {}).get("label") or "Podcast")
            artist = ((e.get("im:artist") or {}).get("label") or "")
            if sid.isdigit() and _family_ok(name, artist):
                out.append({"id": sid, "name": name[:120], "artist": artist[:100],
                            "img": re.sub(r"/\d+x\d+", "/200x200", img) if img else "", "feed": ""})
        return out


def _chart_v2(cc):
    data = json.loads(_get(f"https://rss.applemarketingtools.com/api/v2/{cc}/podcasts/top/50/podcasts.json", MAX_JSON).decode("utf-8", "replace"))
    out = []
    feed = data.get("feed") if isinstance(data, dict) else None
    for r in (feed.get("results") if isinstance(feed, dict) else None) or []:
        if not isinstance(r, dict):
            continue
        sid, name, artist = str(r.get("id") or ""), _txt(r.get("name")) or "Podcast", _txt(r.get("artistName"))
        img = _https(_txt(r.get("artworkUrl100")))
        if sid.isdigit() and _family_ok(name, artist):
            out.append({"id": sid, "name": name[:120], "artist": artist[:100],
                        "img": img.replace("100x100", "200x200") if img else "", "feed": ""})
    return out


# Learn a language: one list per language (taught in English) and one for people who want to learn from Urdu. Used by the Android app only.
LEARN_LANG = {
    "learn-english": ("Learn English", [("search", "learn english podcast", "US"), ("search", "english speaking practice podcast", "IN"), ("search", "learn english podcast", "GB")]),
    "learn-german": ("Learn German", [("search", "learn german podcast", "US"), ("search", "deutsch lernen podcast", "DE")]),
    "learn-french": ("Learn French", [("search", "learn french podcast", "US"), ("search", "apprendre le français podcast", "FR")]),
    "learn-spanish": ("Learn Spanish", [("search", "learn spanish podcast", "US"), ("search", "aprender español podcast", "ES")]),
    "learn-arabic": ("Learn Arabic", [("search", "learn arabic podcast", "US"), ("search", "arabic language lessons podcast", "AE")]),
    "learn-chinese": ("Learn Chinese", [("search", "learn chinese mandarin podcast", "US"), ("search", "learn chinese podcast", "SG")]),
    "learn-from-urdu": ("Learn languages in Urdu", [("search", "learn english in urdu", "PK"), ("search", "english seekhain urdu mein", "PK"), ("search", "learn german in urdu", "PK"), ("search", "learn arabic in urdu", "PK")]),
}
# Apple's category numbers: a category of a country starts with Apple's own chart of that category in that country,
# so Pakistan shows what Pakistan really listens to and not the same world list. The searches only fill up what is missing.
GENRES = {"news": 1489, "education": 1304, "business": 1321, "technology": 1318, "science": 1533, "health": 1512,
          "kids": 1305, "cricket": 1545, "bollywood": 1309, "motivation": 1500,
          "arts": 1301, "comedy": 1303, "fiction": 1483, "government": 1511, "history": 1487, "leisure": 1502, "music": 1310,
          "society": 1324, "sports": 1545, "true-crime": 1488, "tv-film": 1309}
# The worldwide page of a category starts with Apple's own chart too (a search for a word alone brings shows that only have the word in their name).
# Cricket and Bollywood are not whole Apple categories, so they stay searches. Extra charts are added where one chart is not the whole subject.
# The newer Apple categories are built when a visitor opens them (then kept 12 hours), not all at once at every start: the 512 MB free server stays calm.
ON_DEMAND = {"arts", "comedy", "fiction", "government", "history", "leisure", "music", "society", "sports", "true-crime", "tv-film"}
GLOBAL_GENRES = {k: v for k, v in GENRES.items() if k not in ("cricket", "bollywood")}
EXTRA_GENRES = {"motivation": [1517], "health": [1514, 1517]}
LIST_FULL = 30                                      # enough shows from the charts: the word searches are not needed
NO_COUNTRY = {"islamic-scholars"}


def _chart_genre(cc, gid):
    data = json.loads(_get(f"https://itunes.apple.com/{cc}/rss/toppodcasts/genre={int(gid)}/limit=50/json", MAX_JSON).decode("utf-8", "replace"))
    out = []
    for e in (data.get("feed", {}).get("entry", []) if isinstance(data, dict) else []):
        sid = str(((e.get("id") or {}).get("attributes") or {}).get("im:id") or "")
        imgs = e.get("im:image") or []
        img = _https((imgs[-1] or {}).get("label") if imgs else "")
        name = ((e.get("im:name") or {}).get("label") or "Podcast")
        artist = ((e.get("im:artist") or {}).get("label") or "")
        if sid.isdigit() and _family_ok(name, artist):
            out.append({"id": sid, "name": name[:120], "artist": artist[:100],
                        "img": re.sub(r"/\d+x\d+", "/200x200", img) if img else "", "feed": ""})
    return out


def _cat_country(slug):
    """'<category>@<country code>' (e.g. 'business@pk') -> (category, code), or None. Islamic scholars is a fixed list, so it has no country form."""
    cat, _, cc = slug.partition("@")
    if cc and cat in CATEGORIES and not cat.startswith("top-") and cat not in NO_COUNTRY and cc in NEAR:
        return cat, cc
    return None


def valid(slug):
    return slug in CATEGORIES or slug in LEARN_LANG or slug == "faiths" or (slug.startswith("top-") and slug[4:] in NEAR) or _cat_country(slug) is not None


def label(slug):
    if slug == "faiths":
        return "Religion & spirituality (all faiths)"
    if _cat_country(slug):
        cat, cc = _cat_country(slug)
        return f"{CATEGORIES[cat][0]} in {NEAR[cc]}"
    if slug in LEARN_LANG:
        return LEARN_LANG[slug][0]
    return CATEGORIES[slug][0] if slug in CATEGORIES else f"Top podcasts in {NEAR[slug[4:]]}"


def _build(slug):
    out, seen = [], set()
    if _cat_country(slug):                                # the same searches of the category, asked in the shop of the chosen country
        cat, cc = _cat_country(slug)
        steps = list(dict.fromkeys(("search", st[1], cc.upper()) for st in CATEGORIES[cat][1] if st[0] == "search"))
        if cat in GENRES:
            steps.insert(0, ("genre", GENRES[cat], cc))
    else:
        steps = CATEGORIES[slug][1] if slug in CATEGORIES else LEARN_LANG[slug][1] if slug in LEARN_LANG else [("chart", slug[4:])]
        if slug in GLOBAL_GENRES:
            steps = [("genre", g, "us") for g in [GLOBAL_GENRES[slug]] + EXTRA_GENRES.get(slug, [])] + list(steps)
    full = 12 if _cat_country(slug) else LIST_FULL if slug in GLOBAL_GENRES else 0
    names, turns = set(), []
    for step in steps:
        if step[0] == "search" and full and len(out) >= full:      # the charts are already full: no word searches
            break
        try:
            if step[0] == "chart":
                rows = _chart(step[1])
            elif step[0] == "genre":
                rows = _chart_genre(step[2], step[1])
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
                data = _api("/search", term=step[1], media="podcast", limit=200, country=step[2])
                rows = [x for x in (_row(r) for r in data.get("results", [])) if x]
                rows += index_search(step[1], 80)                  # the second directory (Podcast Index) adds its shows when its key is set
        except Exception as e:
            _errors[slug] = f"{step[0]}: {type(e).__name__}: {str(e)[:150]}"
            continue
        if slug in TAKE_TURNS:                                # the page mixes several kinds: each kind gets a place near the top
            turns.append(rows)
            continue
        for row in rows:
            key = re.sub(r"\W+", "", row["name"].lower())      # "Education podcast" and "Education Podcast" are one show shown twice
            if row["id"] not in seen and row["img"] and key not in names:
                seen.add(row["id"]); names.add(key); out.append(row)
    for row in [r for i in range(max((len(t) for t in turns), default=0)) for t in turns for r in t[i:i + 1]]:
        key = re.sub(r"\W+", "", row["name"].lower())
        if row["id"] not in seen and row["img"] and key not in names:
            seen.add(row["id"]); names.add(key); out.append(row)
    if _cat_country(slug) and len(out) < 8:               # a small country has few shows of this kind: fill up with the same category from the wider list, then with the country chart
        cat, cc = _cat_country(slug)
        more = [("chart", cc)] if not out else []
        for st in list(CATEGORIES[cat][1]) + more:
            if len(out) >= 12:
                break
            try:
                rows = _chart(st[1]) if st[0] == "chart" else [x for x in (_row(r) for r in _api("/search", term=st[1], media="podcast", limit=12, country=st[2]).get("results", [])) if x]
            except Exception:
                continue
            for row in rows:
                if row["id"] not in seen and row["img"]:
                    seen.add(row["id"]); out.append(row)
    if slug.startswith("top-"):
        return out
    per, kept = {}, []                                   # never more than two shows of one podcaster on one page
    for row in out:
        who = (row["artist"] or row["name"]).lower()
        if per.get(who, 0) < 2:
            per[who] = per.get(who, 0) + 1; kept.append(row)
    return kept


def category(slug, demo=False):
    """Shows of one page (e.g. Islamic scholars, top in Pakistan). Refreshed every 12 hours by itself; the last good copy
    is kept if Apple is slow."""
    if not valid(slug):
        return []
    if slug == "faiths":                                    # a mix: the first shows of every faith, taking turns
        lists = [category(k, demo)[:4] for k, _n in FAITHS]
        return [r for i in range(4) for rows in lists for r in rows[i:i + 1]]
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
    first = {"top-world", "islamic-scholars", "top-pakistan"}          # these three are fetched now; the rest join the strip once they are ready,
    def part(sn):                                                      # so a cold start never makes the page wait for thirteen lists
        slug, n = sn
        if slug in first:
            return category(slug)[:n]
        with _lock:
            hit = _cat.get(slug)
            fresh = bool(hit and hit[1])
        if not fresh:
            threading.Thread(target=category, args=(slug,), daemon=True).start()
        return (hit[1] if fresh else [])[:n]
    with ThreadPoolExecutor(8) as pool:
        lists = list(pool.map(part, STRIP_ORDER))
    out, seen, per = [], set(), {}
    for row in lists[0][:10]:                                          # the 10 most famous podcasts in the world come first, with their pictures
        if row["id"] not in seen and row["img"]:
            seen.add(row["id"]); per[(row["artist"] or row["name"]).lower()] = 1; out.append(row)
    for i in range(max((len(x) for x in lists[1:]), default=0)):      # then take turns between the pages, so every kind shows early
        for rows in lists[1:]:
            if i < len(rows):
                row = rows[i]
                who = (row["artist"] or row["name"]).lower()
                if row["id"] in seen or per.get(who, 0) >= 1:           # one show per podcaster in the strip
                    continue
                seen.add(row["id"]); per[who] = per.get(who, 0) + 1; out.append(row)
    return out


def _norm(text):
    """Lower case, accents removed, only letters and digits (any script) separated by single spaces."""
    import unicodedata
    t = unicodedata.normalize("NFKD", str(text or "")).lower()
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^\w]+", " ", t, flags=re.UNICODE).replace("_", " ").split())


def _text_score(nq, field):
    """0..1: how well one name matches the typed words (a wrong letter or two still scores high)."""
    import difflib
    if not nq or not field:
        return 0.0
    if field == nq or field.startswith(nq + " "):
        return 1.0
    if nq in field:
        return 0.95
    qt, ft = nq.split(), field.split()
    per = [max(difflib.SequenceMatcher(None, w, f).ratio() for f in ft) for w in qt]
    words = sum(per) / len(per) if min(per) >= 0.72 else 0.0
    best = difflib.SequenceMatcher(None, nq, field).ratio()
    if len(ft) > len(qt):                                   # the typed words may be the start of a longer show name
        best = max(best, max(difflib.SequenceMatcher(None, nq, " ".join(ft[i:i + len(qt)])).ratio() for i in range(len(ft) - len(qt) + 1)))
    return max(0.9 * words, best)


def _score(row, q):
    nq = _norm(q)
    return max(_text_score(nq, _norm(row.get("name"))), _text_score(nq, _norm(row.get("artist"))))


def _known_names():
    """Names the site already knows: famous people, scholars and the shows it has listed. Used to repair a typed name."""
    names = [w for w, _m in SCHOLARS]
    try:
        from .topics import TOPICS
        names += [(t.get("h1") or "").split(" — ")[0] for t in TOPICS.values() if t.get("people")]
    except Exception:
        pass
    with _lock:
        for _t, rows in list(_cat.values()):
            for r in rows:
                names += [r.get("name") or "", r.get("artist") or ""]
        for _t, val in list(_shows.values()):
            names.append((val[0] or {}).get("name") or "" if isinstance(val, tuple) and val else "")
    seen, out = set(), []
    for n in names:
        k = _norm(n)
        if k and k not in seen:
            seen.add(k); out.append(n)
    return out


def _corrections(q):
    """Other spellings to try when the typed name finds nothing close: the nearest known names, and the word without doubled letters."""
    import difflib
    nq = _norm(q)
    known = {_norm(n): n for n in _known_names()}
    out = [known[k] for k in difflib.get_close_matches(nq, list(known), n=3, cutoff=0.6)]
    single = re.sub(r"(.)\1+", r"\1", nq)
    if single != nq and single not in [_norm(x) for x in out]:
        out.append(single)
    return [x for x in out if _norm(x) != nq][:4]


def _search_rows(term):
    rows = []
    try:
        data = _api("/search", term=term, media="podcast", limit=24)
        rows = [x for x in (_row(r) for r in data.get("results", [])) if x]
    except Exception:
        pass
    seen = {r["id"] for r in rows}
    return rows + [r for r in index_search(term[:60], 15) if r["id"] not in seen]


def rank(rows, q):
    """Best match first; when something matches well, the wrong ones are left out. A typed name never fills the page with strangers."""
    scored = sorted(((_score(r, q), i, r) for i, r in enumerate(rows)), key=lambda x: (-x[0], x[1]))
    if not scored:
        return []
    top = scored[0][0]
    floor = 0.6 if top >= 0.7 else 0.4
    return [r for sc, _i, r in scored if sc >= floor][:24]


def search(q, demo=False):
    q = (q or "").strip()[:60]
    if not q:
        return []
    if demo:
        return rank([s for s in DEMO_SHOWS], q) if any(_score(s, q) >= 0.6 for s in DEMO_SHOWS) else []
    rows = _search_rows(q)
    cors = []
    if not rows or max(_score(r, q) for r in rows) < 0.75:         # nothing close: maybe a typing mistake, so ask for the right spelling too
        seen = {r["id"] for r in rows}
        cors = _corrections(q)
        for term in cors:
            for r in _search_rows(term):
                if r["id"] not in seen:
                    seen.add(r["id"]); rows.append(r)
            if rows and max(_score(r, q) for r in rows) >= 0.85:
                break
    if rows and cors and max(_score(r, q) for r in rows) < 0.75:   # the right spelling may be what matches: rank against the closest one
        q = max(((max(_score(r, c) for r in rows), c) for c in cors))[1]
    return rank(rows, q)


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
        row = next((x for x in (_row(r, False) for r in data.get("results", [])) if x), None)
        if not row or not row["feed"]:
            return (hit[1] if hit else ((row, []) if row else (None, [])))
        try:
            _title, eps, art = parse_feed(_get(row["feed"], MAX_FEED, timeout=9, partial=True), sid)
        except Exception:                                  # the podcaster's own server is slow or down: still open the show page, without episodes
            return hit[1] if hit else (row, [])
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


# Words for each page (search engines and people both read them). Honest: lists come from the Apple directory and change by themselves.
PAGE_TEXT = {
    "": ("Listen to free podcasts on Sur Music: Urdu, Islamic lectures, Hindi, cricket, business, technology, AI, science and news. Press play, no app needed.",
         "Browse free podcasts in Urdu, Hindi and English: Islamic lectures and bayan, cricket, Bollywood, news and stories for children. Pick a show, press play on any episode, and listen in your browser on any phone or computer. Each podcast belongs to its podcaster and plays from the podcaster's own server.",
         [("Are the podcasts free?", "Yes. Listening on Sur Music is free. Each podcast belongs to its podcaster, and the audio plays from the podcaster's own server."),
          ("Do I need an app to listen?", "No. Episodes play in your browser on any phone or computer. The free Android app adds background play with the screen off."),
          ("How often is the list updated?", "The list of shows refreshes by itself about every 12 hours, and each show's episodes are read again about every hour, so new episodes appear without any action.")]),
    "islamic-scholars": ("Podcasts of Islamic scholars: bayan, dars and talks, including well-known Pakistani scholars, when they publish a podcast. Free, in your browser.",
         "Bayan, dars and talks by well-known Islamic scholars, including Pakistani scholars, gathered from the Apple Podcasts directory. Many scholars publish only on YouTube, so this page shows the ones that have a real podcast feed, and it updates by itself as new shows appear. Press play on any episode, or open a show and choose oldest first to find older lectures.",
         [("Which Islamic scholars are on this page?", "The page looks for well-known scholars such as Dr Israr Ahmed, Engineer Muhammad Ali Mirza, Mufti Tariq Masood, Maulana Tariq Jameel, Javed Ahmad Ghamidi, Mufti Menk and Nouman Ali Khan. Only those with a podcast in the Apple directory are shown."),
          ("Can I listen to old lectures?", "Yes. Open a show and choose oldest first to see older episodes, up to the last 120 in the podcast's feed."),
          ("Who owns these lectures?", "Each lecture belongs to its scholar or publisher. Sur Music only links to the podcast and plays it from the original server.")]),
    "urdu": ("Urdu podcasts: talks and discussion in Urdu from Pakistan and around the world. Press play, free, no app needed.",
             "Urdu podcasts on talks, stories, society, religion and daily life from Pakistan and the Urdu-speaking world. The list comes from the Apple Podcasts directory and refreshes by itself. Press play on any episode.", []),
    "islamic": ("Islamic lectures and Quran podcasts: tafseer, seerah, bayan and reminders. Press play on any episode, free in your browser.",
                "Islamic lectures, Quran tafseer, seerah, majlis and Ahl-e-Bait talks, and short reminders from many podcasters. Choose a show and press play, or open the show to see the newest and the oldest episodes.", []),
    "hindi": ("Hindi podcasts: stories, talks and discussion in Hindi. Press play on any episode, free in your browser.",
              "Hindi podcasts on stories, talks, film and daily life, from the Apple Podcasts directory. The list refreshes by itself.", []),
    "cricket": ("Cricket podcasts: match talk, analysis and stories from Pakistan, India and the world. Press play, free in your browser.",
                "Cricket podcasts with match talk, analysis and stories from Pakistan, India and the world. New episodes appear by themselves. For live ball-by-ball radio commentary, see the live cricket radio page on Sur Music.", []),
    "bollywood": ("Bollywood podcasts: film talk, music and stars. Press play on any episode, free in your browser.",
                  "Bollywood podcasts about films, songs and the stars, from the Apple Podcasts directory. For live Bollywood songs, open the Bollywood radio on Sur Music.", []),
    "news": ("News and talk podcasts: daily news, current affairs and discussion. Press play, free in your browser.",
             "News and talk podcasts with daily headlines and current affairs from Pakistan and the world. For live news radio, see the live news page on Sur Music.", []),
    "kids": ("Kids story podcasts: bedtime stories and learning for children. Press play on any episode, free in your browser.",
             "Story podcasts for children: bedtime tales, learning and fun. Parents can press play on any episode. Each podcast belongs to its podcaster.", []),
    "celebrity": ("Celebrity and interview podcasts: well-known hosts and guests, in English, Urdu and Hindi. Press play, free in your browser.",
                  "Podcasts hosted by well-known people or built around celebrity interviews, in English, Urdu and Hindi. The list comes from the Apple Podcasts directory and refreshes by itself. Press play on any episode.", []),
    "business": ("Business podcasts: entrepreneurship, startups, money and careers. Press play on any episode, free in your browser.",
                 "Business podcasts about entrepreneurship, startups, investing, money and careers, from the Apple Podcasts directory. The list refreshes by itself.", []),
    "science": ("Science podcasts: space, nature, health and discovery. Press play on any episode, free in your browser.",
                "Science podcasts about space, nature, the human body and new discoveries, from the Apple Podcasts directory. The list refreshes by itself.", []),
    "technology": ("Technology podcasts: gadgets, software, the internet and tech news. Press play on any episode, free in your browser.",
                   "Technology podcasts about gadgets, software, the internet and the latest tech news, from the Apple Podcasts directory. The list refreshes by itself.", []),
    "ai": ("Artificial intelligence podcasts: AI news, ChatGPT, machine learning and the future of work. Press play, free in your browser.",
           "Podcasts about artificial intelligence: AI news, tools such as ChatGPT, machine learning and how AI changes work and life. The list refreshes by itself.", []),
    "christian": ("Christian podcasts: sermons, Bible study, gospel and worship. Press play, free in your browser.",
                  "Christian sermons, Bible study, gospel and worship podcasts from the Apple Podcasts directory. The list refreshes by itself.", []),
    "jewish": ("Jewish podcasts: Torah learning, Jewish thought and culture. Press play, free in your browser.",
               "Torah learning, Jewish thought, history and culture podcasts from the Apple Podcasts directory. The list refreshes by itself.", []),
    "hindu": ("Hindu spiritual podcasts: Bhagavad Gita, bhajan, kirtan and talks. Press play, free in your browser.",
              "Hindu spiritual talks, Bhagavad Gita study, bhajan and kirtan podcasts from the Apple Podcasts directory. The list refreshes by itself.", []),
    "sikh": ("Sikh podcasts: Gurbani, katha and Sikh history. Press play, free in your browser.",
             "Gurbani, katha and Sikh history podcasts from the Apple Podcasts directory. The list refreshes by itself.", []),
    "buddhist": ("Buddhist podcasts: dharma talks and meditation. Press play, free in your browser.",
                 "Buddhist dharma talks and meditation podcasts from the Apple Podcasts directory. The list refreshes by itself.", []),
    "top-pakistan": ("The top podcasts in Pakistan right now, from Apple's own chart. Press play on any episode, free in your browser.",
                     "The most listened podcasts in Pakistan right now, taken from Apple's own chart, which updates by itself. Press play on any episode.", []),
    "top-india": ("The top podcasts in India right now, from Apple's own chart. Press play on any episode, free in your browser.",
                  "The most listened podcasts in India right now, taken from Apple's own chart, which updates by itself. Press play on any episode.", []),
    "top-world": ("The top podcasts worldwide right now, from Apple's own chart. Press play on any episode, free in your browser.",
                  "The most listened podcasts worldwide right now, taken from Apple's own chart, which updates by itself. Press play on any episode.", []),
}


def warm():
    """Right after every start, build all podcast lists at once in the background (four at a time), so a first-time visitor
    finds them ready. The most important lists are built first."""
    order = ["top-world", "top-pk", "top-in", "top-us", "top-gb", "top-ae", "top-sa", "top-bd"] + [k for k in CATEGORIES if not k.startswith("top-") and k not in ON_DEMAND]
    def one(slug):
        try:
            category(slug)
        except Exception:
            pass
    time.sleep(2)
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(one, order))


def start_warming(app):
    if app.config.get("TESTING") or app.config.get("RADIO_DEMO"):
        return
    threading.Thread(target=warm, daemon=True, name="podcast-warm").start()
