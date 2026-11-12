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
    "urdu": ("Urdu podcasts", [("search", "urdu podcast", "PK"), ("search", "pakistan podcast", "PK")]),
    "islamic": ("Islamic lectures & Quran", [("search", "islamic lectures", "US"), ("search", "quran tafseer", "US"), ("search", "seerah", "US")]),
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
    "top-pakistan": ("Top podcasts in Pakistan", [("chart", "pk")]),
    "top-india": ("Top podcasts in India", [("chart", "in")]),
    "top-world": ("Top podcasts worldwide", [("chart", "us")]),
}
# Countries with their own Apple chart ("Top podcasts in <country>"): code -> name. A visitor is shown the chart of his own country.
NEAR = {"pk": "Pakistan", "in": "India", "us": "the United States", "gb": "the United Kingdom", "ca": "Canada", "au": "Australia",
        "ae": "the UAE", "sa": "Saudi Arabia", "qa": "Qatar", "kw": "Kuwait", "om": "Oman", "bh": "Bahrain", "eg": "Egypt", "tr": "Türkiye",
        "bd": "Bangladesh", "lk": "Sri Lanka", "np": "Nepal", "my": "Malaysia", "sg": "Singapore", "id": "Indonesia", "ph": "the Philippines",
        "de": "Germany", "fr": "France", "it": "Italy", "es": "Spain", "nl": "the Netherlands", "se": "Sweden", "no": "Norway", "ie": "Ireland",
        "br": "Brazil", "mx": "Mexico", "ar": "Argentina", "za": "South Africa", "ng": "Nigeria", "ke": "Kenya", "ma": "Morocco", "dz": "Algeria",
        "jo": "Jordan", "lb": "Lebanon", "il": "Israel", "jp": "Japan", "kr": "South Korea", "ru": "Russia", "ua": "Ukraine", "pl": "Poland"}
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


_ADULT = re.compile(r"\b(sex|sexy|sexual|erotic|erotica|porn|xxx|nsfw|18\+|adult|kamasutra|hot stor|nude|fetish|dirty)", re.I)


def _family_ok(name, artist):
    """Family-friendly lists only: adult shows are never listed."""
    return not _ADULT.search(f"{name} {artist}")


def _row(r):
    sid = str(r.get("collectionId") or "")
    if not sid.isdigit() or r.get("collectionExplicitness") == "explicit":
        return None
    if not _family_ok(r.get("collectionName") or "", r.get("artistName") or ""):
        return None
    img = _https(r.get("artworkUrl100") or r.get("artworkUrl60") or "")
    return {"id": sid, "name": (r.get("collectionName") or "Podcast")[:120], "artist": (r.get("artistName") or "")[:100],
            "img": img.replace("100x100", "200x200") if img else "", "feed": _https(r.get("feedUrl") or "")}


def _txt(v):
    return v if isinstance(v, str) else ""


def _chart(cc):
    try:
        return _chart_v2(cc)
    except Exception:                                  # Apple's older chart address, used when the new one is slow or down
        data = json.loads(_get(f"https://itunes.apple.com/{cc}/rss/toppodcasts/limit=30/json", MAX_JSON).decode("utf-8", "replace"))
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
    data = json.loads(_get(f"https://rss.applemarketingtools.com/api/v2/{cc}/podcasts/top/30/podcasts.json", MAX_JSON).decode("utf-8", "replace"))
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


def valid(slug):
    return slug in CATEGORIES or slug == "faiths" or (slug.startswith("top-") and slug[4:] in NEAR)


def label(slug):
    if slug == "faiths":
        return "Religion & spirituality (all faiths)"
    return CATEGORIES[slug][0] if slug in CATEGORIES else f"Top podcasts in {NEAR[slug[4:]]}"


def _build(slug):
    out, seen = [], set()
    for step in (CATEGORIES[slug][1] if slug in CATEGORIES else [("chart", slug[4:])]):
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
        except Exception as e:
            _errors[slug] = f"{step[0]}: {type(e).__name__}: {str(e)[:150]}"
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
                "Islamic lectures, Quran tafseer, seerah and short reminders from many podcasters. Choose a show and press play, or open the show to see the newest and the oldest episodes.", []),
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
