"""Radio Browser client (server side) with a database cache.

Station lists are fetched by the server, cached, and rendered into the HTML (good for SEO
and speed). Only HTTPS streams are listed on the website, because browsers block insecure
(http) audio on an https page.
"""
import json
import re
import random
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from flask import current_app

from .db import get_db, utcnow
from .util import valid_url

COMMON = "hidebroken=true&order=clickcount&reverse=true&limit=300"
CATEGORIES = {
    "bollywood": {
        "title": "Bollywood Radio",
        "paths": [f"/json/stations/bytag/bollywood?{COMMON}", f"/json/stations/search?tag=hindi&{COMMON}",
                  f"/json/stations/search?tag=indian&{COMMON}",
                  f"/json/stations/search?name=vividh%20bharati&{COMMON}", f"/json/stations/search?name=radio%20mirchi&countrycode=IN&{COMMON}",
                  f"/json/stations/search?name=red%20fm&countrycode=IN&{COMMON}", f"/json/stations/search?name=fm%20rainbow&{COMMON}"],
    },
    "lollywood": {
        "title": "Lollywood & Pakistani Radio",
        "paths": [f"/json/stations/search?countrycode=PK&{COMMON}", f"/json/stations/search?tag=pakistani&{COMMON}",
                  f"/json/stations/search?tag=urdu&{COMMON}", f"/json/stations/search?language=urdu&{COMMON}",
                  f"/json/stations/search?name=fm%20100&countrycode=PK&{COMMON}", f"/json/stations/search?name=radio%20pakistan&{COMMON}",
                  f"/json/stations/search?name=mast%20fm&countrycode=PK&{COMMON}", f"/json/stations/search?name=city%20fm&countrycode=PK&{COMMON}",
                  f"/json/stations/search?name=hum%20fm&countrycode=PK&{COMMON}", f"/json/stations/search?name=power%2099&countrycode=PK&{COMMON}",
                  f"/json/stations/search?name=samaa&countrycode=PK&{COMMON}", f"/json/stations/search?name=apna&countrycode=PK&{COMMON}"],
    },
    "hollywood": {
        "title": "Hollywood & English Hits Radio",
        "paths": [f"/json/stations/search?tag=top%2040&{COMMON}", f"/json/stations/search?tag=hits&countrycode=US&{COMMON}",
                  f"/json/stations/search?tag=soundtrack&{COMMON}", f"/json/stations/search?tag=pop&countrycode=US&{COMMON}"],
    },
}
# Genre and country pages (/genre/<slug>, /country/<slug>): each has its own stations (see topics.py)
def _tag(t, extra=""):
    return f"/json/stations/search?tag={urllib.parse.quote(t)}{extra}&{COMMON}"


from .topics import TOPICS as _TOPICS  # noqa: E402

GENRES = {k: {"title": v["label"], "paths": v["paths"]} for k, v in _TOPICS.items()}
_bad_servers = {}


class RadioError(Exception):
    pass


def _user_agent():
    return "SurMusicWeb/1.0 (+Mousa International Software House)"


def _fetch_json(path):
    """GET one Radio Browser API path, trying the mirrors. Raises RadioError."""
    servers = list(current_app.config["RADIO_API_SERVERS"])
    random.shuffle(servers)
    now = time.time()
    servers.sort(key=lambda s: _bad_servers.get(s, 0) > now)  # skip recently failing mirrors last
    timeout = current_app.config["RADIO_TIMEOUT"]
    for s in servers:
        url = f"https://{s}.api.radio-browser.info{path}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _user_agent(), "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed https host)
                data = r.read(5 * 1024 * 1024 + 1)
            if len(data) > 5 * 1024 * 1024:
                raise RadioError("response too large")
            return json.loads(data.decode("utf-8"))
        except Exception:  # network error, bad JSON, HTTP error
            _bad_servers[s] = now + 120
    raise RadioError("The radio directory is not reachable right now.")


def _text(value, limit):
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", " ").split())[:limit]


def normalize(raw, https_only=True):
    seen, out = set(), []
    for s in raw if isinstance(raw, list) else []:
        if not isinstance(s, dict):
            continue
        url = s.get("url_resolved") or ""
        uuid = _text(s.get("stationuuid"), 64)
        if not uuid or uuid in seen or s.get("hls") == 1 or s.get("lastcheckok") != 1:
            continue
        if not valid_url(url, https_only=https_only):
            continue
        seen.add(uuid)
        fav = s.get("favicon") or ""
        home = s.get("homepage") if isinstance(s.get("homepage"), str) else ""
        out.append({
            "uuid": uuid,
            "name": _text(s.get("name"), 120) or "Unknown station",
            "url": url,
            "favicon": fav if valid_url(fav, https_only=True) else "",
            "country": _text(s.get("country"), 60),
            "tags": ", ".join(t.strip() for t in _text(s.get("tags"), 200).split(",")[:3] if t.strip()),
            "bitrate": s.get("bitrate") if isinstance(s.get("bitrate"), int) else 0,
            "clicks": s.get("clickcount") if isinstance(s.get("clickcount"), int) else 0,
            # extra details for the station page (like the big directories show)
            "homepage": home if valid_url(home, https_only=False) else "",
            "language": ", ".join(x.strip().title() for x in _text(s.get("language"), 80).split(",")[:2] if x.strip()),
            "state": _text(s.get("state"), 60),
            "codec": _text(s.get("codec"), 12).upper(),
            "votes": s.get("votes") if isinstance(s.get("votes"), int) else 0,
        })
    out.sort(key=lambda x: -x["clicks"])
    return out


def _cached(key, loader, ttl_minutes):
    from . import lowdb
    if lowdb.enabled():
        hit, value = lowdb.cache_get("radio:" + key)
        if hit:
            return value
        if key.startswith("q:"):                      # searches: memory only, never wake the database
            data = loader()
            lowdb.cache_set("radio:" + key, data, ttl_minutes * 60)
            return data
        try:
            data = loader()
        except RadioError:
            data = None
        if data is not None:
            lowdb.cache_set("radio:" + key, data, ttl_minutes * 60)
            seen, _ = lowdb.cache_get("radio-saved:" + key)
            if not seen:                              # keep a copy for cold starts, at most every 6 hours
                lowdb.cache_set("radio-saved:" + key, True, 6 * 3600)
                lowdb.defer("DELETE FROM station_cache WHERE cache_key = ?", (key,))
                lowdb.defer("INSERT INTO station_cache (cache_key, body, fetched_at) VALUES (?, ?, ?)",
                            (key, json.dumps(data), utcnow()))
            return data
    db = get_db()
    row = db.one("SELECT body, fetched_at FROM station_cache WHERE cache_key = ?", (key,))
    fresh_after = datetime.now(timezone.utc) - timedelta(minutes=ttl_minutes)
    if row and datetime.fromisoformat(row["fetched_at"]) > fresh_after:
        return json.loads(row["body"])
    try:
        data = loader()
    except RadioError:
        if row:  # serve stale data rather than nothing
            return json.loads(row["body"])
        raise
    db.execute("DELETE FROM station_cache WHERE cache_key = ?", (key,))
    db.execute("INSERT INTO station_cache (cache_key, body, fetched_at) VALUES (?, ?, ?)",
               (key, json.dumps(data), utcnow()))
    db.commit()
    return data


DEMO_NAMES = {
    "bollywood": ["Bollywood Hits 24/7", "Retro Hindi Classics", "Desi Romance Radio", "Filmi Masala FM",
                  "90s Bollywood Gold", "Sufi Nights Radio", "Arijit & Friends Mix", "Bhangra Beats",
                  "Old Is Gold Hindi", "Mumbai Melody FM", "Love Songs Hindi", "Bollywood Dance Party"],
    "lollywood": ["Lahore Sur FM", "Karachi Melody Radio", "Qawwali Live 24/7", "Punjabi Dhol Beats",
                  "Ghazal Shaam", "Lollywood Evergreen", "Islamabad Pop FM", "Sindhi Sur Radio"],
    "hollywood": ["Top 40 USA Hits", "Movie Soundtracks Radio", "Chill Pop Lounge", "80s & 90s Hit Machine",
                  "Dance Floor FM", "Acoustic Mornings"],
    "naat": ["Madina Naat Radio", "Naat Sharif 24/7", "Hamd o Naat FM"],
    "qawwali": ["Qawwali Mehfil Radio", "Nusrat Forever", "Sabri Qawwali FM"],
    "ghazal": ["Ghazal Raat", "Mehdi Hassan Classics", "Jagjit Ghazal Radio"],
    "sufi": ["Sufi Rang Radio", "Dhamal Sufi FM"],
    "punjabi": ["Punjabi Virsa Radio", "Bhangra Nation FM", "Lok Geet Punjab"],
    "quran": ["Quran Tilawat Radio", "Islamic Voice FM"],
    "news": ["Urdu News 24", "Khabar FM"],
    "old-songs": ["Purane Geet Radio", "Golden Era Melodies"],
}
DEMO_COUNTRY = {"bollywood": "India", "hollywood": "United States", "news": "Pakistan"}


def _demo(paths):
    key = next((k for k, v in list(CATEGORIES.items()) + list(GENRES.items()) if v["paths"] == paths), "bollywood")
    names = DEMO_NAMES.get(key) or ([f"{GENRES[key]['title']} Live {i}" for i in (1, 2, 3)] if key in GENRES
                                    else DEMO_NAMES["bollywood"])
    country = DEMO_COUNTRY.get(key, "Pakistan")
    raw = [{"stationuuid": f"demo-{key}-{i}", "name": n, "url_resolved": f"https://stream.example.com/{key}/{i}",
            "favicon": "", "country": country, "tags": key, "bitrate": 128, "hls": 0, "lastcheckok": 1,
            "clickcount": 1000 - i} for i, n in enumerate(names)]
    return normalize(raw)


def _best(stations, cap):
    """Keep the stations people really listen to (clicks), not the long tail: faster pages and fewer dead streams.
    A small list is never emptied: at least the 30 best are always kept."""
    good = [s for s in stations if (s.get("clicks") or 0) >= 5]
    return (good if len(good) >= 30 else stations[:30])[:cap]


def _merge(paths, per=None, cap=300):
    if current_app.config.get("RADIO_DEMO"):
        return _demo(paths)
    app = current_app._get_current_object()

    def run(p):
        with app.app_context():
            try:
                return _fetch_json(p)
            except RadioError:
                return None

    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(run, paths))
    if all(r is None for r in results):
        raise RadioError("The radio directory is not reachable right now.")
    merged = []
    for r in results:
        if isinstance(r, list):
            merged.extend(r[:per] if per else r)
    return _best(normalize(merged), cap)


# On these pages the stations named like this come first (Quran Majeed before everything else)
_QURAN_WORDS = ("quran", "qur'an", "qur an", "koran", "قرآن", "قران", "tilawat", "majeed", "kareem")
_FIRST = {"quran": _QURAN_WORDS, "islamic": _QURAN_WORDS}


def _first(stations, words):
    if not words:
        return stations
    return sorted(stations, key=lambda st: 0 if any(w in st["name"].lower() for w in words) else 1)


def category_stations(cat):
    if cat not in CATEGORIES:
        raise KeyError(cat)
    return _cached(f"cat:{cat}", lambda: _merge(CATEGORIES[cat]["paths"]),
                   current_app.config["RADIO_CACHE_MINUTES"])


# Each list keeps only its own kind of channel: no Quran or song stations under News, no songs under Talk or Sports.
_RELIGIOUS_RE = re.compile(r"quran|qur'an|koran|قرآن|قران|islam|naat|nasheed|tilawat|bayan|sunnah|hadith|masjid|"
                           r"madina|makkah|mecca|gospel|christian|church|jesus|bhajan|kirtan|gurbani|sikh|bible|worship", re.I)
_MUSIC_RE = re.compile(r"music|songs?\b|hits|bollywood|lollywood|ghazal|qawwali|\bpop\b|rock|jazz|lofi|lo-fi|classical|melod|"
                       r"gaana|geet|naghm|dance|house|deep|chart|retro|[0-9]0'?s|mix\b|remix|oldies|club|ibiza|\bedm\b|"
                       r"top ?40|radio mirchi|\bfm ?(8|9|10)[0-9]", re.I)
_NEWS_RE = re.compile(r"news|khabar|akhbar|خبر|أخبار|samachar|current affair|world service|\bcnn\b|\bbbc\b|\bnpr\b|"
                      r"\blbc\b|sky news|al jazeera|al arabiya|france 24|\bdw\b|\bvoa\b|haber|times radio|bloomberg|reuters", re.I)
_SPORT_RE = re.compile(r"sport|cricket|football|soccer|talksport|espn|\bnba\b|\bnfl\b|\bf1\b", re.I)


def _fits(slug, st):
    text = f"{st.get('name') or ''} {st.get('tags') or ''}"
    if slug in ("news", "english-news"):
        return not _RELIGIOUS_RE.search(text) and (bool(_NEWS_RE.search(text)) or not _MUSIC_RE.search(text)) \
            and not _MUSIC_RE.search(st.get("name") or "") and not _SPORT_RE.search(st.get("name") or "")
    if slug in ("sports", "cricket", "football"):
        return not _RELIGIOUS_RE.search(text) and (bool(_SPORT_RE.search(text)) or not _MUSIC_RE.search(text))
    if slug == "talk":
        return not _RELIGIOUS_RE.search(text) and not _MUSIC_RE.search(st.get("name") or "")
    return True


def genre_stations(slug):
    if slug not in GENRES:
        raise KeyError(slug)
    if slug in ("news", "english-news", "sports", "cricket", "football", "talk"):
        return [st for st in _genre_stations(slug) if _fits(slug, st)]
    return _genre_stations(slug)


def _genre_stations(slug):
    t = _TOPICS.get(slug, {})
    return _cached(f"genre:{slug}", lambda: _first(_merge(GENRES[slug]["paths"], t.get("per"), t.get("cap", 300)),
                                                  _FIRST.get(slug)),
                   current_app.config["RADIO_CACHE_MINUTES"])


def _peek(key):
    """A cached list without fetching anything (memory first, then the database copy, even if old)."""
    from . import lowdb
    if lowdb.enabled():
        hit, value = lowdb.cache_get("radio:" + key)
        if hit:
            return value
        hit, value = lowdb.cache_get("radio-peek:" + key)
        if hit:
            return value
    row = get_db().one("SELECT body FROM station_cache WHERE cache_key = ?", (key,))
    data = json.loads(row["body"]) if row else None
    if lowdb.enabled():
        lowdb.cache_set("radio-peek:" + key, data, 1800)
    return data


def all_lists():
    """(key, stations) for every category and genre list that can be loaded (cached)."""
    out = []
    for cat in CATEGORIES:
        try:
            out.append((cat, category_stations(cat)))
        except RadioError:
            pass
    for slug in GENRES:
        try:
            out.append((slug, genre_stations(slug)))
        except RadioError:
            pass
    return out


def known_stations():
    """Every station already cached on any list, no duplicates, best-listened first (never hits the network)."""
    seen, out = set(), []
    for key in ["cat:" + c for c in CATEGORIES] + ["genre:" + g for g in GENRES]:
        try:
            data = _peek(key)
        except Exception:
            data = None
        for st in data or []:
            if isinstance(st, dict) and st.get("uuid") and st["uuid"] not in seen:
                seen.add(st["uuid"])
                out.append(st)
    out.sort(key=lambda x: -(x.get("clicks") or 0))
    return out


def cached_station(uuid):
    """A station from the lists already in memory (never touches the database or the network), else None."""
    from . import lowdb
    if not uuid or not lowdb.enabled():
        return None
    for key in ["cat:" + c for c in CATEGORIES] + ["genre:" + g for g in GENRES]:
        for prefix in ("radio:", "radio-peek:"):
            hit, value = lowdb.cache_get(prefix + key)
            for st in (value or []) if hit else []:
                if st.get("uuid") == uuid:
                    return st
    return None


def station_by_uuid(uuid):
    """One station for its own page: first from the cached lists, otherwise from Radio Browser (cached).
    Returns (station, list_key) or (None, '')."""
    uuid = _text(uuid, 64)
    if not uuid:
        return None, ""
    import re as _re
    if not _re.fullmatch(r"[A-Za-z0-9-]+", uuid):
        return None, ""
    from . import lowdb
    keys = [("cat:" + c, c) for c in CATEGORIES] + [("genre:" + g, g) for g in GENRES]
    names = dict(keys)
    if lowdb.enabled():                             # lists already in memory: no database at all
        for cache_key, key in keys:
            for prefix in ("radio:", "radio-peek:"):
                hit, value = lowdb.cache_get(prefix + cache_key)
                for st in (value or []) if hit else []:
                    if st.get("uuid") == uuid:
                        return st, key
        hit, value = lowdb.cache_get("st-hit:" + uuid)   # found here before (world directory pages)
        if hit and value:
            return value[0], value[1]
    # one query over the saved lists (never fetch dozens of lists here)
    for row in get_db().all("SELECT cache_key, body FROM station_cache WHERE body LIKE ?", (f'%"{uuid}"%',)):
        if row["cache_key"] in names or row["cache_key"].startswith("dir:"):   # a list, or the world directory
            for st in json.loads(row["body"]) or []:
                if st.get("uuid") == uuid:
                    if lowdb.enabled():
                        lowdb.cache_set("st-hit:" + uuid, [st, names.get(row["cache_key"], "")], 6 * 3600)
                    return st, names.get(row["cache_key"], "")
    if current_app.config.get("RADIO_DEMO"):
        for key, stations in all_lists():
            for st in stations:
                if st["uuid"] == uuid:
                    return st, key
        return None, ""
    try:
        found = _cached(f"st:{uuid}", lambda: normalize(_fetch_json(
            f"/json/stations/byuuid/{urllib.parse.quote(uuid)}")), 360)
    except RadioError:
        return None, ""
    return (found[0], "") if found else (None, "")


def search_stations(q):
    q = " ".join(q.split())[:60]
    if len(q) < 2:
        return []
    enc = urllib.parse.quote(q)
    words = _QURAN_WORDS if q.lower() in ("quran", "qur'an", "koran", "quran majeed", "quran pak", "quran kareem",
                                          "قرآن", "قران", "قرآن مجید", "قران مجید") else (q.lower(),)
    paths = [f"/json/stations/search?name={enc}&{COMMON}", f"/json/stations/search?tag={enc}&{COMMON}"]
    if words is _QURAN_WORDS:
        paths.append(f"/json/stations/search?tag=quran&{COMMON}")
    return _cached(f"q:{q.lower()}", lambda: _first(_merge(paths), words)[:60], 15)


def clean_station(data):
    """Validate a station object sent by the browser (favourites, play counts)."""
    if not isinstance(data, dict):
        return None
    url = data.get("url") if isinstance(data.get("url"), str) else ""
    if not valid_url(url, https_only=True):
        return None
    uuid = _text(data.get("uuid"), 64)
    if not uuid:
        return None
    fav = data.get("favicon") if isinstance(data.get("favicon"), str) else ""
    bitrate = data.get("bitrate")
    return {
        "uuid": uuid,
        "name": _text(data.get("name"), 120) or "Radio station",
        "url": url,
        "favicon": fav if valid_url(fav, https_only=True) else "",
        "country": _text(data.get("country"), 60),
        "tags": _text(data.get("tags"), 120),
        "bitrate": bitrate if isinstance(bitrate, int) and 0 <= bitrate < 10000 else 0,
    }


def country_counts():
    """{ISO code: number of stations} from Radio Browser (cached for a day), or None if not known.
    Used to list only countries that really have stations, so no page promises what it does not have."""
    if current_app.config.get("RADIO_DEMO"):
        return None
    try:
        rows = _cached("countries", lambda: _fetch_json("/json/countries"), 24 * 60)
    except RadioError:
        return None
    out = {}
    for r in rows or []:
        if isinstance(r, dict):
            code = str(r.get("iso_3166_1") or "").upper()
            try:
                out[code] = out.get(code, 0) + int(r.get("stationcount") or 0)
            except (TypeError, ValueError):
                pass
    return out or None


def known_empty(key):
    """True when this list was loaded and had no playable station (memory only, never wakes the database)."""
    from . import lowdb
    if not lowdb.enabled():
        return False
    for prefix in ("radio:genre:", "radio-peek:genre:"):
        hit, value = lowdb.cache_get(prefix + key)
        if hit and value is not None:
            return not value
    return False


# ---------------------------------------------------------------- "what is playing now" (the song name in the stream)
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def _public_host(host):
    """True only when the host name resolves to public internet addresses (never our own network)."""
    import ipaddress
    import socket
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    return bool(infos) and all(ipaddress.ip_address(i[4][0]).is_global for i in infos)


def parse_icy(block):
    """StreamTitle='Artist - Song'; → 'Artist - Song' ('' when empty)."""
    import re as _re
    text = block.rstrip(b"\0").decode("utf-8", "replace") if block else ""
    m = _re.search(r"StreamTitle='(.*?)';", text, _re.S) or _re.search(r"StreamTitle='(.*)", text, _re.S)
    return clean_title(m.group(1)) if m else ""


def clean_title(raw):
    """A song name fit for people: decode %D8%A5-style text, drop links and leftover codes."""
    import re as _re
    t = raw or ""
    if _re.search(r"%[0-9A-Fa-f]{2}", t):
        try:
            t = urllib.parse.unquote_plus(t, errors="replace")
        except Exception:
            return ""
    t = _text(t, 140)
    if not t or _re.search(r"https?://|www\.|[=&]\w+=|\ufffd", t) or _re.fullmatch(r"[\W_]*", t):
        return ""
    return t


def read_track(url, timeout=6, schemes=("https",)):
    """Open the stream, ask for ICY metadata, read just past the first metadata block and close. '' when none."""
    from urllib.parse import urlparse
    u = urlparse(url or "")
    if u.scheme not in schemes or not u.hostname or not _public_host(u.hostname):
        return ""
    req = urllib.request.Request(url, headers={"Icy-MetaData": "1", "User-Agent": _user_agent(), "Accept": "*/*"})
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as r:
            try:
                every = int(r.headers.get("icy-metaint") or 0)
            except ValueError:
                every = 0
            if not 0 < every <= 65536:
                return ""
            left = every
            while left > 0:
                chunk = r.read(min(left, 8192))
                if not chunk:
                    return ""
                left -= len(chunk)
            size = r.read(1)
            if not size or size[0] == 0:
                return ""
            return parse_icy(r.read(size[0] * 16))
    except Exception:
        return ""


def now_playing(url):
    """The current song name for a stream, cached for 25 seconds so many listeners cost one request."""
    from . import lowdb
    key = "np:" + url
    if lowdb.enabled():
        hit, value = lowdb.cache_get(key)
        if hit:
            return value
    title = read_track(url)
    if lowdb.enabled():
        lowdb.cache_set(key, title, 25)
    return title
