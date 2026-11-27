"""Radio Browser client (server side) with a database cache.

Station lists are fetched by the server, cached, and rendered into the HTML (good for SEO
and speed). Only HTTPS streams are listed on the website, because browsers block insecure
(http) audio on an https page.
"""
import json
import re
import random
import threading
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
LISTED_GENRES = [k for k in GENRES if not _TOPICS[k].get("people")]      # the pages about people load only when visited
_bad_servers = {}


class RadioError(Exception):
    pass


def _user_agent():
    return "SurMusicWeb/1.0 (+Mousa International Software House)"


def _fetch_json(path):
    """GET one Radio Browser API path, trying the mirrors. Raises RadioError."""
    servers = list(current_app.config["RADIO_API_SERVERS"])
    for extra in ("de2", "all"):                       # de1 is retired by the directory; always also try its current mirrors
        if extra not in servers:
            servers.append(extra)
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
            "favicon": _logo(fav),
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


def _logo(fav):
    """Channel logo address: many stations list an http:// logo, which browsers block on our https site; try https."""
    if isinstance(fav, str) and fav.startswith("http://"):
        fav = "https://" + fav[len("http://"):]
    return fav if valid_url(fav, https_only=True) else ""


def _list_file(key):
    import os
    safe = re.sub(r"[^a-z0-9:_-]", "_", key.lower()).replace(":", "__")[:120]
    return os.path.join(current_app.config["STORAGE_DIR"], "lists", safe + ".json.gz")


def _disk_put(key, data):
    """A local copy of a station list: an expired list is then read from the server's own disk in milliseconds,
    instead of being rebuilt (dozens of directory searches) or fetched from the sleeping free database."""
    import gzip
    import os
    try:
        path = _list_file(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".part"
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except Exception:  # pragma: no cover - only a speed-up
        pass


def _disk_get(key):
    import gzip
    try:
        with gzip.open(_list_file(key), "rt", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


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
        _FALLBACK.used = False
        try:
            data = loader()
        except RadioError:
            data = None
        if data is not None and getattr(_FALLBACK, "used", False):
            return data                               # directory down: show the offline list now, but do not cache it
        if data is not None:
            lowdb.cache_set("radio:" + key, data, ttl_minutes * 60)
            if key.startswith(("genre:", "cat:")):
                _disk_put(key, data)
            g = GENRES.get(key[6:]) if key.startswith("genre:") else None
            if g and len(g["paths"]) >= 10:           # big lists (Islamic ~100 searches): keep a spare copy for a day,
                lowdb.cache_set("radio-peek:" + key, data, 24 * 3600)   # so an expired list never waits for the database
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
    _FALLBACK.used = False
    try:
        data = loader()
    except RadioError:
        if row:  # serve stale data rather than nothing
            return json.loads(row["body"])
        raise
    if getattr(_FALLBACK, "used", False):             # directory down: keep the last good copy, never store the offline list
        return json.loads(row["body"]) if row else data
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
            "favicon": "", "country": country, "tags": key, "language": "english", "bitrate": 128, "hls": 0,
            "lastcheckok": 1, "clickcount": 1000 - i} for i, n in enumerate(names)]
    return normalize(raw)


def _best(stations, cap):
    """Keep the stations people really listen to (clicks), not the long tail: faster pages and fewer dead streams.
    A small list is never emptied: at least the 30 best are always kept."""
    good = [s for s in stations if (s.get("clicks") or 0) >= 5]
    return (good if len(good) >= 30 else stations[:30])[:cap]


_local_all = []


def _local_lists(paths, per, cap):
    """Same search as the online directory (tag, and language when asked), but on the 30,000 stations saved in the code."""
    from urllib.parse import urlparse, parse_qs
    from . import directory
    try:
        if not _local_all:
            for n in directory.chunks():
                _local_all.extend(directory.chunk_stations(n))
        pool = _local_all
    except Exception:
        return []
    merged = []
    for p in paths:
        q = parse_qs(urlparse(p).query)
        tag = (q.get("tag") or [""])[0].lower()
        lang = (q.get("language") or [""])[0].lower()
        if not tag and not lang:
            continue
        hits = []
        for st in pool:
            tags = [t.strip().lower() for t in (st.get("tags") or "").split(",")]
            if tag and tag not in tags:
                continue
            if lang and lang not in (st.get("language") or "").lower():
                continue
            hits.append(st)
        hits.sort(key=lambda x: -(x.get("clicks") or 0))
        merged.extend(hits[:per] if per else hits[:300])
    seen, out = set(), []
    for st in sorted(merged, key=lambda x: -(x.get("clicks") or 0)):
        if st.get("uuid") not in seen:
            seen.add(st["uuid"]); out.append(st)
    return _best(out, cap) if out else []


_FALLBACK = threading.local()   # set when _merge answered from our own saved copy (directory down): never cached


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
        local = _local_lists(paths, per, cap)          # the online directory is down: use our own saved copy of it
        if local:
            _FALLBACK.used = True
            return local
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


# Famous-channel pages keep only stations that really carry the channel's name (no look-alikes)
CHANNEL_WORDS = {
    "al-jazeera-live": ("jazeera", "الجزيرة"),
    "bbc-world-service": ("bbc",),
    "ary-news-live": ("ary news", "ary-news", "arynews"),
    "geo-news-live": ("geo news", "geo-news", "geonews", "geo tv", "جیو"),
    "cnn-live": ("cnn",),
    "fox-news-live": ("fox news", "foxnews"),
}


for _s, _t in _TOPICS.items():                      # famous people: a station must carry the name
    if _t.get("words"):
        CHANNEL_WORDS[_s] = tuple(_t["words"])


def _fits(slug, st):
    text = f"{st.get('name') or ''} {st.get('tags') or ''}"
    if slug in CHANNEL_WORDS:
        low = (st.get("name") or "").lower()
        return any(w in low for w in CHANNEL_WORDS[slug])
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
    if _TOPICS.get(slug, {}).get("people"):             # stations that carry the name; none yet: the best stations of that kind (never an empty page)
        own = [st for st in _genre_stations(slug) if _fits(slug, st)]
        return own or _genre_stations(_TOPICS[slug]["pool"])[:40]
    if slug in ("news", "english-news", "sports", "cricket", "football", "talk") or slug in CHANNEL_WORDS:
        return [st for st in _genre_stations(slug) if _fits(slug, st)]
    return _genre_stations(slug)


def _build_genre(slug):
    t = _TOPICS.get(slug, {})
    return _first(_merge(GENRES[slug]["paths"], t.get("per"), t.get("cap", 300)), _FIRST.get(slug))


def _islamic_fast(slug):
    """The Islamic page joins ~100 searches, so a cold open took very long. Show the last saved list at once
    (even if old) and refresh it in the background; only the very first load ever waits."""
    from . import lowdb
    if not lowdb.enabled():
        return None                                   # normal path below keeps its own cache
    key = "genre:" + slug
    hit, value = lowdb.cache_get("radio:" + key)
    if hit:
        return value
    old = _peek(key)
    if not old:
        return None
    app = current_app._get_current_object()
    flag = "radio-refresh:" + key
    if not lowdb.cache_get(flag)[0]:
        lowdb.cache_set(flag, True, 600)
        import threading

        def refresh():
            with app.app_context():
                try:
                    _cached(key, lambda: _build_genre(slug), app.config["RADIO_CACHE_MINUTES"])
                except Exception:
                    pass
        threading.Thread(target=refresh, daemon=True).start()
    return old


def start_list_warming(app):
    """Right after every start (each deploy restarts the server and empties its memory and disk), build the big
    lists (Islamic, news, Pakistan ... each joins 10 to 100+ searches) in the background, so the first visitor or
    Google does not wait 10+ seconds for them."""
    if app.config.get("TESTING") or app.config.get("RADIO_DEMO"):
        return None
    import threading
    big = sorted((k for k, v in GENRES.items() if len(v["paths"]) >= 10 and k in LISTED_GENRES), key=lambda k: -len(GENRES[k]["paths"]))

    def run():
        import os
        time.sleep(5)
        with app.app_context():
            for slug in big:
                try:
                    _cached(f"genre:{slug}", lambda s=slug: _build_genre(s), app.config["RADIO_CACHE_MINUTES"])
                except Exception:
                    pass
            # then every other country and category, slowly, onto the disk only (no memory): after a restart the whole
            # site is fast again within about half an hour, without paying for a permanent disk
            for slug in sorted(LISTED_GENRES):
                if slug in big or os.path.exists(_list_file(f"genre:{slug}")):
                    continue
                try:
                    data = _build_genre(slug)
                    if data:
                        _disk_put(f"genre:{slug}", data)
                except Exception:
                    pass
                time.sleep(2)
    t = threading.Thread(target=run, daemon=True, name="list-warm")
    t.start()
    return t


def _genre_stations(slug):
    fast = _islamic_fast(slug)                         # every list: show the last saved copy at once, refresh behind the scenes
    if fast:
        return fast
    t = _TOPICS.get(slug, {})
    return _cached(f"genre:{slug}", lambda: _first(_merge(GENRES[slug]["paths"], t.get("per"), t.get("cap", 300)),
                                                  _FIRST.get(slug)),
                   current_app.config["RADIO_CACHE_MINUTES"])


def keep(key, data):
    """Save a last-good copy of a list for cold starts (restarts), at most every 6 hours, so a restart never empties a strip."""
    from . import lowdb
    if not data:
        return
    if not lowdb.enabled():                           # no low-database mode (tests, small installs): write it straight away
        db = get_db()
        db.execute("DELETE FROM station_cache WHERE cache_key = ?", (key,))
        db.execute("INSERT INTO station_cache (cache_key, body, fetched_at) VALUES (?, ?, ?)", (key, json.dumps(data), utcnow()))
        db.commit()
        return
    seen, _ = lowdb.cache_get("radio-saved:" + key)
    if not seen:
        lowdb.cache_set("radio-saved:" + key, True, 6 * 3600)
        lowdb.defer("DELETE FROM station_cache WHERE cache_key = ?", (key,))
        lowdb.defer("INSERT INTO station_cache (cache_key, body, fetched_at) VALUES (?, ?, ?)", (key, json.dumps(data), utcnow()))


def seed_saved(key, data):
    """Put a copy that was saved outside the server (after a restart) back where _peek() finds it. Does nothing if a copy is already there."""
    from . import lowdb
    if not data or _peek(key):
        return False
    db = get_db()
    db.execute("DELETE FROM station_cache WHERE cache_key = ?", (key,))
    db.execute("INSERT INTO station_cache (cache_key, body, fetched_at) VALUES (?, ?, ?)", (key, json.dumps(data), utcnow()))
    db.commit()
    if lowdb.enabled():
        lowdb.cache_set("radio-peek:" + key, data, 1800)          # a 'nothing' answer cached a moment ago must not hide it
    return True


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
        data = _disk_get(key)
        if data:
            lowdb.cache_set("radio-peek:" + key, data, 1800)
            return data
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
    for slug in LISTED_GENRES:
        try:
            out.append((slug, genre_stations(slug)))
        except RadioError:
            pass
    return out


def known_stations():
    """Every station already cached on any list, no duplicates, best-listened first (never hits the network)."""
    seen, out = set(), []
    for key in ["cat:" + c for c in CATEGORIES] + ["genre:" + g for g in LISTED_GENRES]:
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


def memory_stations():
    """Every station of the lists already in memory (never touches the database or the network), best-listened first."""
    from . import lowdb
    seen, out = set(), []
    if not lowdb.enabled():
        return out
    for key in ["cat:" + c for c in CATEGORIES] + ["genre:" + g for g in LISTED_GENRES]:
        for prefix in ("radio:", "radio-peek:"):
            hit, value = lowdb.cache_get(prefix + key)
            for st in (value or []) if hit else []:
                if isinstance(st, dict) and st.get("uuid") and st["uuid"] not in seen:
                    seen.add(st["uuid"]); out.append(st)
    out.sort(key=lambda x: -(x.get("clicks") or 0))
    return out


def cached_station(uuid):
    """A station from the lists already in memory (never touches the database or the network), else None."""
    from . import lowdb
    if not uuid or not lowdb.enabled():
        return None
    for key in ["cat:" + c for c in CATEGORIES] + ["genre:" + g for g in LISTED_GENRES]:
        for prefix in ("radio:", "radio-peek:"):
            hit, value = lowdb.cache_get(prefix + key)
            for st in (value or []) if hit else []:
                if st.get("uuid") == uuid:
                    return st
    return None


# Corrections a station sent us itself (name, logo, working stream), on top of the public directory data,
# which can be out of date. "also" = extra words that find the station in search; never shown.
STATION_FIXES = {
    "dd10f037-269c-42e0-9bfb-c22726aa8a7c": {      # Radyo İLEF, Ankara University (their email, 21 Nov 2026)
        "name": "Radyo İLEF", "url": "https://radyoilef.ankara.edu.tr/live",
        "favicon": "https://radyoilef.ankara.edu.tr/radyo-ilef-logo.png",
        "homepage": "https://radyoilef.ankara.edu.tr/", "country": "Türkiye", "tags": "70's, 80s, anatolian rock",
        "also": "Ankara Üniversitesi Radyosu Radyo İlef FM 91.0",
        "about": "Radyo İLEF is the radio station of Ankara University (Ankara Üniversitesi Radyosu), on FM 91.0 in "
                 "Ankara, Türkiye: music in more than 40 languages from an archive of over 17,000 songs, plus podcasts."},
}


def _fold_name(text):
    """Lower-case without accents, so "İLEF", "ilef" and "Ilef" all match in search."""
    import unicodedata
    text = unicodedata.normalize("NFKD", (text or "").casefold())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def fix_station(st):
    """The station with the corrections its owner sent us (unchanged if there are none)."""
    fix = STATION_FIXES.get((st or {}).get("uuid")) if isinstance(st, dict) else None
    if not fix:
        return st
    return {**st, **{k: v for k, v in fix.items() if k != "also"}}


def station_by_uuid(uuid):
    """One station for its own page, with any corrections from its owner. Returns (station, list_key) or (None, '')."""
    st, key = _lookup_station(uuid)
    if st:
        return fix_station(st), key
    if uuid in STATION_FIXES:                        # gone from the public directory, but its owner gave us the details
        return fix_station({"uuid": uuid, "bitrate": 0, "clicks": 0, "language": "", "state": "", "codec": "",
                            "votes": 0}), ""
    return None, ""


def _lookup_station(uuid):
    """One station for its own page: first from the cached lists, otherwise from Radio Browser (cached).
    Returns (station, list_key) or (None, '')."""
    uuid = _text(uuid, 64)
    if not uuid:
        return None, ""
    import re as _re
    if not _re.fullmatch(r"[A-Za-z0-9-]+", uuid):
        return None, ""
    from . import lowdb
    keys = [("cat:" + c, c) for c in CATEGORIES] + [("genre:" + g, g) for g in LISTED_GENRES]
    names = dict(keys)
    if lowdb.enabled():                             # lists already in memory: no database at all
        for cache_key, key in keys:
            for prefix in ("radio:", "radio-peek:"):
                hit, value = lowdb.cache_get(prefix + cache_key)
                for st in (value or []) if hit else []:
                    if st.get("uuid") == uuid:
                        return st, key
    # the world directory: a local file on the disk (no database traffic at all)
    from . import directory
    try:
        st = directory.find(uuid)
    except Exception:
        st = None
    if st:
        return st, ""
    # one query over the saved lists: only the list NAMES come back, then the one matching list is read
    for row in get_db().all("SELECT cache_key FROM station_cache WHERE body LIKE ?", (f'%"{uuid}"%',)):
        if row["cache_key"] in names:
            body = get_db().one("SELECT body FROM station_cache WHERE cache_key = ?", (row["cache_key"],))
            for st in json.loads(body["body"]) if body else []:
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


def gone_station_country(uuid):
    """Country code of a station that no longer plays in a browser (http only, HLS or offline), so its old page,
    which Google may still list, can send visitors to that country's stations instead of a dead end. '' if unknown."""
    import re as _re
    if not _re.fullmatch(r"[A-Za-z0-9-]{8,64}", uuid or ""):
        return ""
    try:
        raw = _cached(f"gone:{uuid}", lambda: [{"cc": _text(x.get("countrycode"), 2).upper()} for x in
                                                _fetch_json(f"/json/stations/byuuid/{urllib.parse.quote(uuid)}")
                                                if isinstance(x, dict)], 1440)
    except RadioError:
        return ""
    return raw[0]["cc"] if raw else ""


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
    found = _cached(f"q:{q.lower()}", lambda: _first(_merge(paths), words)[:60], 15)
    wanted = _fold_name(q)
    fixed = [fix_station({"uuid": uuid, "bitrate": 0, "clicks": 0}) for uuid, fix in STATION_FIXES.items()
             if wanted in _fold_name(fix["name"] + " " + fix.get("also", ""))]
    ids = {st["uuid"] for st in fixed}
    return fixed + [fix_station(st) for st in found if st.get("uuid") not in ids]


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
        "favicon": _logo(fav),
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


def only_pool(slug, stations):
    """True when a page about a person shows the ordinary list of its kind because no station carries the name."""
    return bool(_TOPICS.get(slug, {}).get("people")) and not any(_fits(slug, st) for st in stations)
