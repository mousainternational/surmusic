"""Radio Browser client (server side) with a database cache.

Station lists are fetched by the server, cached, and rendered into the HTML (good for SEO
and speed). Only HTTPS streams are listed on the website, because browsers block insecure
(http) audio on an https page.
"""
import json
import random
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from flask import current_app

from .db import get_db, utcnow
from .util import valid_url

COMMON = "hidebroken=true&order=clickcount&reverse=true&limit=100"
CATEGORIES = {
    "bollywood": {
        "title": "Bollywood Radio",
        "paths": [f"/json/stations/bytag/bollywood?{COMMON}", f"/json/stations/search?tag=hindi&{COMMON}"],
    },
    "lollywood": {
        "title": "Lollywood & Pakistani Radio",
        "paths": [f"/json/stations/search?countrycode=PK&{COMMON}", f"/json/stations/search?tag=pakistani&{COMMON}",
                  f"/json/stations/search?tag=urdu&{COMMON}"],
    },
    "hollywood": {
        "title": "Hollywood & English Hits Radio",
        "paths": [f"/json/stations/search?tag=top%2040&{COMMON}", f"/json/stations/search?tag=hits&countrycode=US&{COMMON}",
                  f"/json/stations/search?tag=soundtrack&{COMMON}"],
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
        out.append({
            "uuid": uuid,
            "name": _text(s.get("name"), 120) or "Unknown station",
            "url": url,
            "favicon": fav if valid_url(fav, https_only=True) else "",
            "country": _text(s.get("country"), 60),
            "tags": ", ".join(t.strip() for t in _text(s.get("tags"), 200).split(",")[:3] if t.strip()),
            "bitrate": s.get("bitrate") if isinstance(s.get("bitrate"), int) else 0,
            "clicks": s.get("clickcount") if isinstance(s.get("clickcount"), int) else 0,
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


def _merge(paths):
    if current_app.config.get("RADIO_DEMO"):
        return _demo(paths)
    app = current_app._get_current_object()

    def run(p):
        with app.app_context():
            try:
                return _fetch_json(p)
            except RadioError:
                return None

    with ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(run, paths))
    if all(r is None for r in results):
        raise RadioError("The radio directory is not reachable right now.")
    merged = []
    for r in results:
        if isinstance(r, list):
            merged.extend(r)
    return normalize(merged)[:120]


def category_stations(cat):
    if cat not in CATEGORIES:
        raise KeyError(cat)
    return _cached(f"cat:{cat}", lambda: _merge(CATEGORIES[cat]["paths"]),
                   current_app.config["RADIO_CACHE_MINUTES"])


def genre_stations(slug):
    if slug not in GENRES:
        raise KeyError(slug)
    return _cached(f"genre:{slug}", lambda: _merge(GENRES[slug]["paths"]),
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
    # one query over the saved lists (never fetch dozens of lists here)
    for row in get_db().all("SELECT cache_key, body FROM station_cache WHERE body LIKE ?", (f'%"{uuid}"%',)):
        if row["cache_key"] in names:
            for st in json.loads(row["body"]) or []:
                if st.get("uuid") == uuid:
                    return st, names[row["cache_key"]]
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
    return _cached(f"q:{q.lower()}", lambda: _merge([f"/json/stations/search?name={enc}&{COMMON}",
                                                     f"/json/stations/search?tag={enc}&{COMMON}"])[:60], 15)


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
