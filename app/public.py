"""Public pages, the station JSON API, favourites, downloads and infrastructure routes."""
import json
import threading
import re
import time
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

import os
from urllib.parse import quote, urlencode
from markupsafe import escape as html_escape
from flask import (Blueprint, Response, abort, current_app, flash, g, jsonify, make_response, redirect, render_template, send_from_directory,
                   request, send_file, session, url_for)

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from . import analytics, radio
from .db import get_db, utcnow
from .mailer import send_mail
from .security import csp_nonce, current_user, ip_hash, rate_limited
from . import blog as blog_data
from . import islam as islam_data
from . import markets
from . import trends
from . import digest
from . import weather
from . import today as today_news
from .seo import (absolute, article_ld, breadcrumb_ld, build_meta, collection_ld, faq_items_ld, faq_ld, topic_keywords, media_url, organization_ld, page_ld, station_ld, webapp_ld, android_app_ld,
                  website_ld)
from .settings import (ADSENSE_CLIENT_RE, ads_active, affiliate_offers, donation_method, get_settings, is_blocked,
                       offers_for, sponsored_stations, without_blocked)
from .storage import file_path, media_bytes, media_path, software_mime
from .util import plain_text, slugify, valid_email, valid_url

bp = Blueprint("public", __name__)

CATEGORY_PAGES = {
    "bollywood": {
        "h1": "Bollywood Radio — Live Hindi Songs",
        "seo_title": "Bollywood Radio Live — Hindi Film Songs Online Free",
        "description": "Listen to live Bollywood radio free: Hindi film songs, romantic hits, 90s classics and new releases from stations in India and around the world.",
        "more": "Also searched as Bollywood radio live, Hindi songs online, Hindi radio online free, Bollywood songs FM, old Hindi songs, romantic Hindi songs, 90s Bollywood songs, Punjabi and Bollywood remix. Fans of Arijit Singh, Lata Mangeshkar, Kishore Kumar, Mohammed Rafi, Asha Bhosle, Shreya Ghoshal, Sonu Nigam, Atif Aslam and Rahat Fateh Ali Khan will find stations playing Hindi film hits and classics. Listeners in the USA, UK, UAE, Canada, Australia and Saudi Arabia use this page to hear Bollywood radio from Mumbai and Delhi.",
        "intro": "Tune in to the best live Bollywood radio stations, all in one place. From the golden voices of Lata Mangeshkar and Kishore Kumar to today's chart-toppers, these stations play Hindi film music around the clock — romantic songs, dance numbers, 90s classics and devotional music. Pick a station, press play, and keep browsing: the music keeps going.",
    },
    "lollywood": {
        "h1": "Lollywood & Pakistani Radio — Urdu, Punjabi, Ghazal & Qawwali",
        "seo_title": "Pakistani Radio Live — Urdu Songs, Ghazal & Qawwali",
        "description": "Listen to live Pakistani radio free: Lollywood film songs, Urdu pop, Punjabi music, ghazals, qawwali and FM stations from Pakistan.",
        "more": "Also searched as Pakistani radio live, Lollywood songs, Urdu songs online, Pakistani FM radio, FM 100, FM 101 and FM 91 live, Punjabi songs, Urdu radio, Pakistani drama songs and Coke Studio style music. Listeners looking for Noor Jehan, Mehdi Hassan, Nazia Hassan, Atif Aslam, Ali Zafar, Rahat Fateh Ali Khan, Abida Parveen and Nusrat Fateh Ali Khan will find Pakistani music stations here. Pakistanis in the UK, USA, UAE, Saudi Arabia and Canada use this page to hear radio from Lahore, Karachi and Islamabad.",
        "intro": "Listen to live Pakistani radio from Lahore, Karachi, Islamabad and beyond. These stations play Lollywood film songs, Urdu and Punjabi pop, timeless ghazals, Sufi music and qawwali, plus news and talk from FM stations across Pakistan. Wherever you are in the world, stay connected to the sound of home.",
    },
    "hollywood": {
        "h1": "Hollywood & English Hits Radio — Top 40, Pop & Soundtracks",
        "seo_title": "English Radio Live — Top 40 Hits & Pop Online",
        "description": "Listen to live English radio free: Top 40 hits, pop, 80s and 90s classics and Hollywood movie soundtracks from stations worldwide.",
        "more": "Also searched as Hollywood songs online, English radio live, Top 40 radio, pop radio online, English songs free, 80s and 90s hits, movie soundtracks and US and UK chart radio. Fans of Taylor Swift, Ed Sheeran, The Weeknd, Dua Lipa, Billie Eilish, Coldplay, Adele and Bruno Mars will find pop and hits stations here. Listeners in the USA, UK, Canada, Australia, the UAE and South Africa use this page for English hit radio.",
        "intro": "Enjoy live English music radio: Top 40 chart hits, pop and dance, timeless 80s and 90s classics, and Hollywood movie soundtracks from stations around the world. Perfect for work, study, workouts and long drives — free, with no download and no sign-up needed.",
    },
}


from .about_text import COUNTRY_ABOUT, GENRE_ABOUT  # noqa: E402
from .neighbours import NEIGHBOURS  # noqa: E402
from .topics import CONTINENTS, COUNTRY_PAGES, GENRE_PAGES, TOPIC_ALIASES, TOPICS, countries_in, grouped, topic_path  # noqa: E402


def station_path(st):
    """Address of a station's own page, e.g. /station/9617a9-…/geo-fm-100."""
    import re as _re
    slug = _re.sub(r"[^a-z0-9]+", "-", (st.get("name") or "station").lower()).strip("-")[:60] or "station"
    return f"/station/{st['uuid']}/{slug}"


@bp.app_template_global("chip_active")
def _chip_active(slug):
    """On Quran, Naat, bayan … pages the highlighted button is "Islamic" (they all live under it)."""
    from .topics import ISLAMIC_FAMILY
    return "islamic" if slug in ISLAMIC_FAMILY else slug


@bp.app_template_global("nav_tabs")
def _nav_tabs(active=""):
    """The category tabs (Music, News, Sports …) with what opens under each. [{key,label,on,items:[(href,label,on)]}]"""
    from .topics import CAT_PAGES, NAV, TAB_COUNTRIES, TAB_OF, ISLAMIC_FAMILY
    real = active
    slug = "islamic" if active in ISLAMIC_FAMILY else active
    if slug in COUNTRY_PAGES or request.path.startswith("/continent/"):
        current = "countries"
    else:
        current = TAB_OF.get(slug) or ("music" if slug in CAT_PAGES or not slug else "music")
    tabs = []
    for key, label, slugs in NAV:
        if key in ("languages", "countries"):          # these two are already in the header menus (Language, Country)
            continue
        items = []
        if key == "countries":
            items = [(f"/continent/{c}", CONTINENTS[c][0], request.path == f"/continent/{c}") for c in CONTINENTS]
            items = [("/near-me", "Near me", False)] + items
            items += [(topic_path(c), TOPICS[c]["label"], c == slug) for c in TAB_COUNTRIES if c in TOPICS]
        else:
            for sl in slugs:
                if sl in CAT_PAGES:
                    items.append((f"/{sl}", CAT_PAGES[sl], sl == slug))
                elif sl in TOPICS and not radio.known_empty(sl):
                    items.append((topic_path(sl), TOPICS[sl]["label"], sl == slug))
        if key == "news":                                     # News: the news channels themselves, not one more "News" button
            items = _news_channels(slug) or [(topic_path("news"), "All news channels", slug == "news")]
        tabs.append({"key": key, "label": label, "on": key == current, "subs": items})
    # A tab for blind and low-vision listeners: how-to page first, then the stations that are easy to follow by ear.
    here_a11y = request.path == "/accessibility"
    if here_a11y:
        for t in tabs:
            t["on"] = False
    subs = [("/accessibility", "Blind-friendly guide", here_a11y),
            ("/accessibility#keyboard-shortcuts", "Keyboard shortcuts", False)]
    for sl, lb in (("news", "News"), ("talk", "Talk"), ("sports", "Sports & cricket"),
                   ("english-news", "World news")):
        if sl in TOPICS and not radio.known_empty(sl):
            subs.append((topic_path(sl), lb, False))
    tabs.append({"key": "accessibility", "label": "Accessibility", "on": here_a11y, "subs": subs})
    # A–Z directory next to the categories (like the big directories): every letter, plus Top 100 and Pakistan FM.
    here_az = request.path.startswith("/stations/") or request.path == "/top-100"
    if here_az:
        for t in tabs:
            t["on"] = False
    az = [("/top-100", "Top 100", request.path == "/top-100")]     # Pakistan FM lives on the Pakistan pages, not here
    az += [(f"/stations/{c}", c.upper(), request.path == f"/stations/{c}") for c in LETTERS]
    az.append(("/stations/0", "0–9", request.path == "/stations/0"))
    tabs.append({"key": "az", "label": "A–Z", "on": here_az, "subs": az})
    return tabs


# News tab: real news-only channels that play in the browser (checked by hand on Radio Browser, Nov 2026).
# Radio Pakistan's city channels and Samaa FM mostly play songs, so they are not here.
NEWS_CHANNELS = [
    ("34cdd9d2-fba9-4a1e-a0d0-35d70252d349", "Radio Pakistan News (Lahore)"),
    ("7423d8e7-7da9-4e0c-bc66-32e2f22830ef", "Radio Pakistan World Service"),
    ("a347209e-6ce6-4c94-81ed-003c1275188f", "BBC World Service"),
    ("33178054-56cd-449c-8cf7-412cc7be936a", "CNN"),
    ("7094b698-b1ac-4f08-a6cd-ac35f906765d", "CNN International"),
    ("1653b791-7005-4e95-be20-4e7b626a4a20", "Sky News"),
    ("9a8f2d50-fca3-4d7c-99ee-c5e0e97f4d1b", "Times Radio (UK)"),
    ("8e32c763-b926-4e57-9b8f-d60f1c5b48e3", "LBC News (UK)"),
    ("9ed85a92-9fb4-4ae8-baca-59347adc782c", "TRT Haber (Turkey)"),
]


def _news_channels(slug):
    """The News tab: Pakistan's news channels first, then world news, then 'All news channels'."""
    here = request.path
    items = [(station_path({"uuid": u, "name": n}), n, here.startswith(f"/station/{u}")) for u, n in NEWS_CHANNELS]
    items.append((topic_path("news"), "All news channels →", slug == "news"))
    return items


@bp.app_template_global("topic_href")
def _topic_href(slug):
    return topic_path(slug)


def visitor_country():
    """The visitor's country code (from the IP address / Cloudflare, else the browser's time zone remembered in the
    session, else the browser language such as "en-GB"). Used only to choose which radio types to show first."""
    if "sm_cc" in g:
        return g.sm_cc
    code = ""
    try:
        code = analytics._location()[0]
    except Exception:
        code = ""
    if not code:
        import re as _re
        m = _re.search(r"[a-z]{2,3}-([A-Z]{2})\b", request.headers.get("Accept-Language", ""))
        code = m.group(1) if m else ""
    g.sm_cc = code.upper()
    return g.sm_cc


@bp.route("/near-me")
def near_me():
    """Radio for the visitor's own country (from the connection's country, else the browser language)."""
    from .topics import CODE_TO_COUNTRY
    slug = CODE_TO_COUNTRY.get(visitor_country())
    resp = redirect(topic_path(slug) if slug in TOPICS else "/radio-stations", code=302)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@bp.app_template_global("local_radio_link")
def _local_radio_link():
    """The button next to "Play top station": the visitor's own country (Pakistan FM page for Pakistan, else that country's page)."""
    from .topics import CODE_TO_COUNTRY
    code = visitor_country()
    slug = CODE_TO_COUNTRY.get(code)
    if code == "PK" or slug not in TOPICS:
        return {"label": "Pakistan FM by frequency & city", "href": "/pakistan-fm-radio"}
    return {"label": TOPICS[slug].get("label", slug.title()) + " radio stations", "href": topic_path(slug)}


@bp.app_template_global("chips_here")
def _chips_here():
    from .topics import chips_for
    return chips_for(visitor_country())


_TYPE_GROUPS = [          # (key, icon, title, types)
    ("entertainment", "🎬", "Entertainment", ["pop", "rock", "hip-hop", "dance", "lofi", "jazz", "classical",
                                              "country-music", "latin", "80s-90s", "reggae", "afrobeats", "k-pop",
                                              "metal", "old-songs", "comedy"]),
    ("religious", "🕌", "Religious", ["islamic", "christian", "bhajan", "gurbani", "jewish"]),
    ("news", "📰", "News", ["news", "business"]),
    ("debates", "🎙️", "Debates and talk", ["debates", "talk"]),
    ("sports", "🏏", "Sports", ["sports", "cricket", "football"]),
    ("health", "🩺", "Health and calm", ["health", "meditation", "relax-sleep", "sleep-music", "rain-sounds", "nature-sounds", "white-noise", "calm-piano", "ambient-music", "spa-music"]),
    ("cooking", "🍳", "Cooking and food", ["cooking"]),
    ("kids", "🧒", "Kids and learning", ["kids", "education", "technology"]),
    ("other", "✨", "Other", ["qawwali", "sufi", "ghazal"]),
]
_LANG_GROUPS = [
    ("South Asia", ["hindi", "urdu", "punjabi", "pashto", "sindhi", "bengali", "tamil", "telugu", "malayalam", "marathi",
                    "gujarati"]),
    ("Middle East", ["arabic", "persian", "turkish", "hebrew"]),
    ("Europe and Americas", ["english", "spanish", "french", "german", "italian", "portuguese", "russian", "dutch",
                             "polish", "greek"]),
    ("Asia-Pacific and Africa", ["chinese", "japanese", "korean", "indonesian", "thai", "vietnamese", "swahili"]),
]
_POPULAR_COUNTRIES = ["usa", "uk", "canada", "australia", "germany", "france", "pakistan", "india", "uae",
                      "saudi-arabia", "turkey"]


@bp.app_template_global("footer_places")
def _footer_places():
    """Footer lists like the big directories: popular countries, and Pakistan's provinces."""
    from .topics import PROVINCE_SLUGS
    countries = [(topic_path(s), TOPICS[s]["label"]) for s in
                 ["pakistan", "india", "saudi-arabia", "uae", "uk", "usa", "canada", "bangladesh", "afghanistan", "turkey"]
                 if s in TOPICS]
    # neutral: Indian states and Pakistani provinces side by side
    pk = [s for s in PROVINCE_SLUGS if "Pakistan" in TOPICS[s].get("description", "")]
    other = [s for s in PROVINCE_SLUGS if s not in pk]
    mixed = [x for pair in zip(other, pk) for x in pair] + other[len(pk):] + pk[len(other):]
    provinces = [(topic_path(s), TOPICS[s]["label"]) for s in mixed[:10]]
    return countries, provinces


@bp.app_template_global("market_ticker")
def _market_ticker():
    return markets.ticker()


@bp.app_template_global("type_menu")
def _type_menu():
    """Every radio type in short groups: [(key, icon, title, [(href, label)])]. Nothing is left out."""
    languages = {s for _, slugs in _LANG_GROUPS for s in slugs}
    from .topics import ISLAMIC_FAMILY, SECT_PAGES
    placed = {s for _, _, _, slugs in _TYPE_GROUPS for s in slugs} | languages | set(ISLAMIC_FAMILY) | set(SECT_PAGES)   # these live under "Islamic" / "News"
    out = [("film", "🎞️", "Film and pop radio", [("/bollywood", "Bollywood"), ("/lollywood", "Pakistani (Lollywood)"),
                                                  ("/hollywood", "English hits (Hollywood)")])]
    for key, icon, title, slugs in _TYPE_GROUPS:
        out.append((key, icon, title, [(topic_path(s), TOPICS[s]["label"]) for s in slugs
                                       if s in TOPICS and not radio.known_empty(s)]))
    out[-1][3].extend((topic_path(k), v["label"]) for k, v in GENRE_PAGES.items()
                      if k not in placed and not radio.known_empty(k) and _page_exists(k))
    return [g for g in out if g[3]]


@bp.app_template_global("language_menu")
def _language_menu():
    """The "Language" button: stations by the language they speak or sing in."""
    out = []
    for title, slugs in _LANG_GROUPS:
        items = [(topic_path(s), TOPICS[s]["label"]) for s in slugs if s in TOPICS and not radio.known_empty(s)]
        if items:
            out.append((title, items))
    return out


@bp.app_template_global("country_menu")
def _country_menu():
    """Popular countries, the continents and every country that has stations, for the drop-down."""
    popular = [(topic_path(s), TOPICS[s]["label"]) for s in _POPULAR_COUNTRIES if s in TOPICS]
    regions = [(f"/continent/{c}", CONTINENTS[c][0]) for c in CONTINENTS]
    groups = []
    for c in CONTINENTS:
        items = [(topic_path(slug), t["label"]) for slug, t, _ in _listed_countries(c)]
        if items:
            groups.append((CONTINENTS[c][0], items))
    return popular, regions, groups


@bp.app_context_processor
def _topic_globals():
    return {"TOPICS": TOPICS}


@bp.app_template_global()
def station_href(st):
    if not isinstance(st, dict) or st.get("sponsored") or not st.get("uuid") or str(st["uuid"]).startswith("pod-"):
        return ""
    return station_path(st)


# ---------------------------------------------------------------- helpers

def _sponsored(cat):
    out = []
    for i, s in enumerate(sponsored_stations()):
        if not isinstance(s, dict) or s.get("category") not in (cat, "all"):
            continue
        st = radio.clean_station(dict(s, uuid=f"sponsored-{i}"))
        if st:
            st["sponsored"] = True
            out.append(st)
    return out


def _stations_for(cat):
    try:
        return without_blocked(_sponsored(cat) + radio.category_stations(cat)), None
    except radio.RadioError as exc:
        return without_blocked(_sponsored(cat)), str(exc)


def _user_favorite_ids():
    u = current_user()
    if not u:
        return []
    return [r["station_uuid"] for r in get_db().all("SELECT station_uuid FROM favorites WHERE user_id = ?", (u["id"],))]


_RELIGIOUS = re.compile(r"quran|qur'an|koran|tilawat|tilawa|recitation|naat|na'at|nasheed|islam|islamic|azan|adhan|"
                        r"madani|hadith|bayan|qaseeda|qasida|makkah|mecca|madinah|medina|قرآن|القرآن|اسلام|نعت", re.I)
_QURAN = re.compile(r"quran|qur'an|koran|tilawat|tilawa|recitation|قرآن|القرآن", re.I)
_RELIGIOUS_CATS = {"quran", "naat", "islamic", "islam", "bayan", "hadith", "madani", "majlis", "nasheed", "religious"}


def _popular(days=7, limit=8):
    from . import lowdb
    if lowdb.enabled():
        hit, value = lowdb.cache_get("popular")
        if hit:
            return value
        value = _popular_query(days, limit)
        lowdb.cache_set("popular", value, 1800)
        return value
    return _popular_query(days, limit)


def _popular_query(days=7, limit=8):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    # one row per station (the same station played from two pages used to appear twice)
    rows = get_db().all("SELECT station_name, MAX(station_uuid) AS station_uuid, "
                        "COUNT(*) AS n FROM plays WHERE created_at > ? GROUP BY station_name "
                        "ORDER BY n DESC LIMIT ?", (since, limit + 5))
    # the type each station was played under most often (not the alphabetically last one)
    cats = {}
    for c in get_db().all("SELECT station_name, category, COUNT(*) AS n FROM plays WHERE created_at > ? "
                          "AND category != '' GROUP BY station_name, category ORDER BY n DESC", (since,)):
        cats.setdefault(c["station_name"], c["category"])
    import re as _re
    out = []
    for r in rows:
        r = dict(r)
        r["category"] = cats.get(r["station_name"], "")
        if _RELIGIOUS.search(r["station_name"] or "") and r["category"] not in _RELIGIOUS_CATS:
            # Quran, Naat and other religious stations are never shown under film or music types
            r["category"] = "quran" if _QURAN.search(r["station_name"] or "") else ""
        if is_blocked({"name": r["station_name"], "uuid": r.get("station_uuid") or ""}):
            continue
        uuid = r.get("station_uuid") or ""
        # its own page only when the station is still listed (no broken links); otherwise a search for its name
        st = radio.cached_station(uuid) if _re.fullmatch(r"[0-9a-f-]{36}", uuid) else None
        r["href"] = station_path(st) if st else url_for("public.search", q=r["station_name"][:60])
        out.append(r)
    return out[:limit]


def _json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400)
    return data


# ---------------------------------------------------------------- sign-in to listen

def gate_active():
    return get_settings().get("play_requires_login") == "1"


def _fernet():
    key = hashlib.sha256((current_app.config["SECRET_KEY"] + "|stream-url").encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def protect(stations):
    """For signed-out visitors (when sign-in is required) replace each stream URL with an encrypted token,
    so the page source does not reveal playable links."""
    if not gate_active() or current_user():
        return stations
    f = _fernet()
    out = []
    for st in stations:
        c = dict(st)
        c["token"] = f.encrypt(c.pop("url", "").encode()).decode()
        out.append(c)
    return out


def _unlock(raw):
    """Station from the browser → add the real URL back from its token (if it has one)."""
    if not isinstance(raw, dict):
        return None
    if not raw.get("url") and isinstance(raw.get("token"), str) and len(raw["token"]) < 4000:
        try:
            raw = dict(raw, url=_fernet().decrypt(raw["token"].encode()).decode())
        except (InvalidToken, ValueError):
            return None
    return radio.clean_station(raw)


# ---------------------------------------------------------------- pages

@bp.app_template_global("country_az")
def _country_az():
    """Every country page, A to Z, grouped by first letter: [(letter, [(href, name)])] (header Country menu)."""
    import unicodedata
    fold = lambda x: unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode().lower() or x.lower()
    rows = sorted(((t["label"], topic_path(k), t.get("code")) for k, t in TOPICS.items() if t["kind"] == "country"),
                  key=lambda x: fold(x[0]))
    out = {}
    for name, href, fl in rows:
        out.setdefault((fold(name)[:1] or "#").upper(), []).append((href, name, fl))
    return list(out.items())


@bp.app_template_global("religious_types")
def _religious_types():
    from .topics import RELIGIOUS_TYPES
    return sorted(((topic_path(k), TOPICS[k]["label"]) for k in RELIGIOUS_TYPES if k in TOPICS), key=lambda x: x[1])


RELAX_TYPES = ["rain-sounds", "nature-sounds", "sleep-music", "meditation", "calm-piano", "ambient-music", "white-noise", "spa-music"]


FAMOUS_NEWS = ["al-jazeera-live", "bbc-world-service", "ary-news-live", "geo-news-live", "cnn-live", "fox-news-live"]


@bp.app_template_global("famous_news")
def _famous_news():
    """The big news channels that really have a stream in our directory (an empty one is left out)."""
    return [(topic_path(k), TOPICS[k]["label"]) for k in FAMOUS_NEWS
            if k in TOPICS and not radio.known_empty(k)]


_TOP = {"t": 0, "v": []}


@bp.app_template_global("top_stations")
def _top_stations(n=24):
    """The most listened stations of the world that have a logo, from the saved lists (no network), one per name, kept 30 minutes."""
    import time
    if time.time() - _TOP["t"] > (1800 if _TOP["v"] else 20):
        seen, out = set(), []
        for st in radio.memory_stations():
            key = (st.get("name") or "").strip().lower()
            if st.get("favicon") and st.get("uuid") and key and key not in seen:
                seen.add(key); out.append({"name": st["name"], "favicon": st["favicon"], "href": station_path(st)})
            if len(out) >= 60:
                break
        _TOP.update(t=time.time(), v=out)
    return _TOP["v"][:n]


def _person_shows(slug, remember=True):
    """Podcasts, talks and shows by this person (their name must be in the show or the podcaster's name).
    [] = checked, there are none; None = could not check right now. Kept in the database copy for a week."""
    t = TOPICS.get(slug) or {}
    if not t.get("people"):
        return []
    from . import podcasts
    full = (t.get("h1") or "").split(" — ")[0]
    low = full.lower()
    demo = bool(current_app.config.get("TESTING") or current_app.config.get("RADIO_DEMO"))
    if t.get("pkind") == "music":                      # songs are not offered here, and a band name can match a stranger's show
        return []

    def by_person(r):
        art, nm = (r.get("artist") or "").lower(), (r.get("name") or "").lower()
        if " " not in low:                             # one-word names are too easy to confuse: the podcaster's name must be exactly it
            return art == low
        return low in art                              # the podcaster is the person (not a stranger's episode that only mentions the name)

    def load():
        if demo:
            rows = podcasts.search(full, True)
        else:
            try:
                data = podcasts._api("/search", term=full[:60], media="podcast", limit=24)
            except Exception:
                raise radio.RadioError("podcast directory not reachable")
            rows = [x for x in (podcasts._row(r) for r in data.get("results", [])) if x]
            seen = {r["id"] for r in rows}
            rows += [r for r in podcasts.index_search(full[:60]) if r["id"] not in seen]       # a second free directory
        return [r for r in rows if by_person(r)][:12]
    if not remember:
        return radio._peek("pod:p3:" + slug)
    value = radio._cached("pod:p3:" + slug, load, 7 * 24 * 60)
    _note_found(slug, value)
    return value


def _person_news(slug, wait=True, upcoming=False):
    """Newest headlines about a person. wait=False (a visitor's page): only what is already saved, never the network.
    wait=True (the background check): fetch, save the list (or a 'checked, nothing' mark) and return it."""
    t = TOPICS.get(slug) or {}
    if not t.get("people"):
        return []
    key = ("keep:pu2:" if upcoming else "keep:pn2:") + slug
    if not wait:
        try:
            return [x for x in (radio._peek(key) or []) if x.get("t")]
        except Exception:
            return []
    from . import headlines
    demo = bool(current_app.config.get("TESTING") or current_app.config.get("RADIO_DEMO"))
    fetch = headlines.demo_person_news if demo else headlines.person_news          # tests never touch the network
    items = fetch((t.get("h1") or "").split(" — ")[0], upcoming)
    if items is None:                                  # the news feed failed: say nothing is saved, so the next round tries again
        return []
    radio.keep(key, items or [{"t": "", "s": "", "u": ""}])
    return items or []


def _stored_checked(slug):
    """True when the news of this person has been looked up before (even if it found nothing)."""
    try:
        return radio._peek("keep:pn2:" + slug) is not None
    except Exception:
        return False


_CHECKING = set()


def _check_person_soon(slug):
    """A visitor reached a person who is not checked yet: look them up in the background (once), so the next visit has the page."""
    import threading
    if slug in _CHECKING or len(_CHECKING) > 5:
        return
    _CHECKING.add(slug)
    app = current_app._get_current_object()

    def run():
        try:
            with app.app_context():
                _person_shows(slug)
                _person_news(slug, wait=True)
                _person_news(slug, wait=True, upcoming=True)
        except Exception:
            pass
        finally:
            _CHECKING.discard(slug)
    threading.Thread(target=run, daemon=True, name="person-check").start()


_FOUND = {}                  # people whose podcasts or talks really exist: slug -> (label, cover picture)


_CITY_INDEX = {}


def _cities():
    """{country code: [(city slug, city label)]} and {(code, city name lower): slug}, from each city page's own search."""
    if not _CITY_INDEX:
        import re as _re
        by_code, by_name = {}, {}
        for k, t in TOPICS.items():
            if t.get("group") != "Cities":
                continue
            m = _re.search(r"countrycode=([A-Z]{2})", " ".join(t.get("paths") or []))
            if m:
                by_code.setdefault(m.group(1), []).append((k, t["label"]))
                by_name[(m.group(1), t["label"].lower())] = k
        _CITY_INDEX.update(code=by_code, name=by_name,
                           country={t["label"].lower(): k for k, t in TOPICS.items() if t["kind"] == "country"})
    return _CITY_INDEX


def _related_links(slug=None, st=None):
    """(heading, [(href, words)]) that tie a page to its neighbours: country <-> its cities, a city -> its country and
    other cities, a person -> other famous voices of the same kind, a station -> its country, city and genre.
    Google reaches every strong page through these, and visitors find the next thing to play."""
    from .topics import CODE_TO_COUNTRY
    idx = _cities()
    out = []
    if st is not None:
        cslug = (idx["country"].get((st.get("country") or "").strip().lower())
                 or CODE_TO_COUNTRY.get((st.get("countrycode") or "").strip().upper()))
        if cslug:
            out.append((topic_path(cslug), f"{TOPICS[cslug]['label']} radio"))
            code = TOPICS[cslug].get("code", "")
            city = idx["name"].get((code, (st.get("state") or "").strip().lower()))
            if city:
                out.append((topic_path(city), f"{TOPICS[city]['label']} radio"))
        for tag in (st.get("tags") or "").split(","):
            k = slugify(tag.strip(), 60) if tag.strip() else ""
            if k in TOPICS and TOPICS[k]["kind"] != "country" and not TOPICS[k].get("people"):
                out.append((topic_path(k), f"{TOPICS[k]['label']} radio"))
        return ("Explore more radio", out[:5])
    t = TOPICS.get(slug) or {}
    if t.get("kind") == "country":
        out = [(topic_path(k), f"{label} radio") for k, label in idx["code"].get(t.get("code", ""), [])[:24]]
        return (f"Cities in {t['label']}", out)
    if t.get("group") == "Cities":
        code = next((c for c, items in idx["code"].items() if any(k == slug for k, _ in items)), "")
        cslug = CODE_TO_COUNTRY.get(code)
        if cslug:
            out.append((topic_path(cslug), f"All {TOPICS[cslug]['label']} radio"))
        out += [(topic_path(k), f"{label} radio") for k, label in idx["code"].get(code, []) if k != slug][:12]
        return ("More cities nearby", out)
    if t.get("people"):
        kind = t.get("pkind")
        out = [(topic_path(k), TOPICS[k]["label"]) for k in list(_FOUND)
               if k != slug and (TOPICS.get(k) or {}).get("pkind") == kind][:12]
        return ("More famous voices", out)
    return ("", [])


def _page_exists(slug):
    """False for a person whose page would be empty (no audio and no headlines): that page is a 404, so nothing may link to it."""
    if not (TOPICS.get(slug) or {}).get("people") or slug in _FOUND:
        return True
    try:
        return bool(_person_news(slug, wait=False))
    except Exception:
        return False


_KIND_FIRST = ["podcast", "speaker", "business", "politics", "quran", "naat", "bhajan", "gurbani", "gospel", "qawwali", "music"]


def _note_found(slug, shows):
    if shows and slug not in _FOUND:
        pic = next((r["img"] for r in shows if r.get("img")), "")
        if pic:
            _FOUND[slug] = (TOPICS[slug]["label"], pic)


_VOICES_SAVED = {"n": 0}


def _voices_restore():
    """After a restart: the famous-voices list (and each person's shows) comes back from the saved copy outside the server, so it never starts empty."""
    from . import persist
    data = persist.load_json("voices")
    people = data.get("people") if isinstance(data, dict) else None
    n = 0
    for slug, v in (people or {}).items():
        t = TOPICS.get(slug) or {}
        if not t.get("people") or not isinstance(v, dict) or not v.get("s"):
            continue
        try:
            radio.seed_saved("pod:p3:" + slug, v["s"])
        except Exception:
            continue
        _note_found(slug, v["s"])
        n += 1
    for slug, items in ((data or {}).get("news") or {}).items() if isinstance(data, dict) else ():
        t = TOPICS.get(slug) or {}
        if t.get("people") and isinstance(items, list) and items:
            try:
                radio.seed_saved("keep:pn2:" + slug, items)
            except Exception:
                pass
    _VOICES_SAVED["n"] = max(_VOICES_SAVED["n"], n)
    return n


def _voices_save():
    """Keep the list safe outside the server (only when it changed; never replace a good copy with a much smaller one)."""
    from . import persist
    snap = {}
    for k in list(_FOUND):
        shows = radio._peek("pod:p3:" + k)
        if shows:
            snap[k] = {"l": _FOUND[k][0], "p": _FOUND[k][1], "s": shows}
    if not snap or len(snap) < _VOICES_SAVED["n"] * 0.8:
        return "skipped"
    news = {}
    for k, t in TOPICS.items():                        # the headlines too: pages that Google already knows never come back empty after a restart
        if t.get("people"):
            items = [{"t": x["t"], "s": x.get("s", ""), "u": x.get("u", "")} for x in (radio._peek("keep:pn2:" + k) or []) if x.get("t")][:6]
            if items:
                news[k] = items
    result = persist.save_json("voices", {"people": snap, "news": news})
    if result in ("pushed", "unchanged"):
        _VOICES_SAVED["n"] = max(_VOICES_SAVED["n"], len(snap))
    return result


_REFRESH = {"t": 0, "busy": False}


def _spawn_found_refresh():
    """Every worker learns, in the background, about people another worker (or an earlier run) already found: the database copies are read."""
    import threading
    import time
    if time.time() - _REFRESH["t"] < 90 or _REFRESH["busy"]:
        return
    _REFRESH["busy"] = True
    app = current_app._get_current_object()
    if app.config.get("TESTING") or app.config.get("RADIO_DEMO"):
        _REFRESH.update(t=time.time(), busy=False)
        return

    def run():
        try:
            with app.app_context():
                if not _FOUND:
                    _voices_restore()
                for k, t in TOPICS.items():
                    if t.get("people") and t.get("pkind") != "music" and k not in _FOUND:
                        _note_found(k, radio._peek("pod:p3:" + k))
        except Exception:
            pass
        finally:
            _REFRESH.update(t=time.time(), busy=False)
    threading.Thread(target=run, daemon=True, name="voices-refresh").start()


@bp.app_template_global("famous_voices")
def _famous_voices(n=24):
    """People with real podcasts or talks, as a row of covers on the home page (filled in by the background check)."""
    _spawn_found_refresh()
    order = {k: i for i, k in enumerate(TOPICS)}
    def prio(k):
        kind = TOPICS[k].get("pkind")
        return (_KIND_FIRST.index(kind) if kind in _KIND_FIRST else 99, order[k])
    return [(topic_path(k), _FOUND[k][0], _FOUND[k][1]) for k in sorted(_FOUND, key=prio)[:n]]


def _person_text(slug, info, shows, news=()):
    """(paragraphs, newest episodes of the first show, questions) for a person's page, from what really exists: their shows and the newest headlines."""
    from . import podcasts
    full, short = (info["h1"].split(" — ")[0]), info["label"]
    names = [r["name"] for r in shows]
    demo = bool(current_app.config.get("TESTING") or current_app.config.get("RADIO_DEMO"))
    eps = []
    if shows:                                          # the newest episodes only if the show is already in memory: the page never waits for a podcaster's server
        with podcasts._lock:
            hit = podcasts._shows.get(str(shows[0]["id"]))
        eps = (hit[1][1] if hit else (podcasts.show(shows[0]["id"], True)[1] if demo else [])) or []
    eps = [{"name": e["name"], "date": (e.get("date") or "")[:10]} for e in (eps or [])[:8] if e.get("name")]
    n = len(shows)
    paras, faqs = [], []
    if shows:
        paras.append(f"Sur Music lists {n} podcast{'s' if n != 1 else ''} and talk{'s' if n != 1 else ''} by or with {short}: " + ", ".join(names[:5]) + ("." if n <= 5 else f" and {n - 5} more."))
        if eps:
            paras.append(f"The newest episode of {names[0]} is \u201c{eps[0]['name']}\u201d" + (f" ({eps[0]['date']})" if eps[0]["date"] else "") +
                         ". Open the show to play it, or pick an older one; episodes play in your browser, free, with no sign-up.")
            if len(eps) > 1:
                paras.append("Recent episodes: " + "; ".join(f"\u201c{e['name']}\u201d" + (f" ({e['date']})" if e["date"] else "") for e in eps[1:4]) + ".")
        faqs.append((f"Where can I listen to {full} podcasts?", f"On this page. Sur Music lists {n} show{'s' if n != 1 else ''}: " + ", ".join(names[:4]) + ". Press play on any episode."))
        faqs.append((f"Is it free to listen to {short} here?", "Yes. The episodes are free to play in your web browser or in the Sur Music Android app, with no sign-up."))
    if news:
        paras.append(f"This page also follows the latest news about {short}. The newest headline is \u201c{news[0]['t']}\u201d" + (f" ({news[0]['s']})" if news[0].get("s") else "") + ".")
        faqs.append((f"What is the latest news about {full}?", f"The newest headline is \u201c{news[0]['t']}\u201d. The list on this page is refreshed automatically from public news feeds."))
    return paras, eps, faqs


_PEOPLE_THREAD = {"pid": None}


def start_people_check(app):
    """Slowly, in the background, find which famous people really have podcasts or talks (one lookup every 10 seconds, once a week)."""
    if app.config.get("TESTING") or app.config.get("RADIO_DEMO") or _PEOPLE_THREAD["pid"] == os.getpid():
        return None
    _PEOPLE_THREAD["pid"] = os.getpid()
    import threading
    import time

    def save_loop():                                     # keep the famous-voices list safe outside the server, every 10 minutes if it changed
        time.sleep(90)
        while True:
            try:
                with app.app_context():
                    _voices_save()
            except Exception:
                pass
            time.sleep(600)

    def run():
        time.sleep(2)
        with app.app_context():
            try:
                _voices_restore()                        # first: the saved list, so nothing already found is looked up again
            except Exception:
                pass
            todo = []
            for slug in [k for k, t in TOPICS.items() if t.get("people") and t.get("pkind") != "music"]:       # already checked in an earlier run: just remember them
                try:
                    done = radio._peek("pod:p3:" + slug)
                except Exception:
                    done = None
                if done is None:
                    todo.append(slug)
                else:
                    _note_found(slug, done)
            first = lambda k: _KIND_FIRST.index(TOPICS[k].get("pkind")) if TOPICS[k].get("pkind") in _KIND_FIRST else 99
            todo.sort(key=first)                                                # podcasters and speakers first (the sort keeps the list order)
            from . import indexnow
            fresh = []
            for slug in todo:                                                   # the rest, one lookup every 4 seconds (Apple allows about 20 a minute)
                try:
                    if _person_shows(slug) and slug in _FOUND:
                        fresh.append(topic_path(slug))
                except Exception:
                    pass
                if len(fresh) >= 20:                                            # tell Bing, Yahoo, Yandex about the new pages as they appear
                    indexnow.send_pages(app, fresh + ["/voices"])
                    fresh = []
                time.sleep(4)
            indexnow.send_pages(app, fresh + ["/voices"])
    def run_news():                                     # headlines for every person, one lookup every 3 seconds (a different site from Apple's)
        time.sleep(20)
        with app.app_context():
            for slug in sorted((k for k, t in TOPICS.items() if t.get("people")), key=lambda k: (_KIND_FIRST.index(TOPICS[k].get("pkind")) if TOPICS[k].get("pkind") in _KIND_FIRST else 99)):
                try:
                    if not radio._peek("keep:pn2:" + slug):
                        _person_news(slug)
                        time.sleep(3)
                except Exception:
                    time.sleep(3)
    threading.Thread(target=run_news, daemon=True, name="people-news").start()
    threading.Thread(target=save_loop, daemon=True, name="voices-save").start()
    t = threading.Thread(target=run, daemon=True, name="people-check")
    t.start()
    return t


@bp.app_template_global("relax_types")
def _relax_types():
    """The sounds shown as chips on every Relax and sleep page (the same ones as in the app)."""
    return [(topic_path(k), TOPICS[k]["label"]) for k in RELAX_TYPES if k in TOPICS]


@bp.app_template_global("language_az")
def _language_az():
    """Every language page, A to Z by first letter: [(letter, [(href, name)])]."""
    seen, rows = set(), []
    for _, slugs in _LANG_GROUPS:
        for sl in slugs:
            if sl in TOPICS and sl not in seen and not radio.known_empty(sl):
                seen.add(sl)
                rows.append((TOPICS[sl]["label"], topic_path(sl)))
    out = {}
    for name, href in sorted(rows, key=lambda x: x[0].lower()):
        out.setdefault(name[:1].upper(), []).append((href, name))
    return list(out.items())


_FLAG_FIRST = ["pakistan", "india", "saudi-arabia", "uae", "uk", "usa", "canada", "australia", "germany", "france",
               "turkey", "bangladesh", "afghanistan", "egypt", "qatar", "kuwait", "oman", "bahrain", "iraq", "iran",
               "indonesia", "malaysia", "nigeria", "south-africa", "brazil", "mexico", "italy", "spain", "russia",
               "china", "japan", "south-korea", "sri-lanka", "nepal", "morocco", "algeria"]


def _flag(code):
    code = code or ""
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code.upper()) if len(code) == 2 and code.isalpha() else ""


@bp.app_template_global("flag_img")
def _flag_img(code):
    """A small flag picture (Windows has no flag emoji, so a picture is used; the emoji is the fallback)."""
    from markupsafe import Markup, escape
    c = (code or "").lower()
    if len(c) != 2 or not c.isalpha():
        return Markup("")
    return Markup(f'<img class="flagimg" src="https://flagcdn.com/w40/{c}.png" srcset="https://flagcdn.com/w80/{c}.png 2x" '
                  f'width="28" height="21" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" '
                  f'data-emoji="{escape(_flag(c))}">')


@bp.app_template_global("flag_grid")
def _flag_grid():
    """The most used countries as flags: [(href, name, flag)] (side column of the list pages)."""
    rows = [(topic_path(k), TOPICS[k]["label"], TOPICS[k].get("code")) for k in _FLAG_FIRST if k in TOPICS]
    return sorted(rows, key=lambda r: r[1].lower())              # A to Z


@bp.app_template_global("trend_logos")
def _trend_logos(items):
    """A channel logo for each trending row: a different top station of the page the row opens (saved lists only, no network)."""
    from . import radio
    pools, used, out = {}, {}, []
    for r in items:
        href = r.get("href", "")
        slug = href.strip("/").split("/")[-1]
        if href not in pools:
            lst = None
            for key in ("genre:" + slug, "cat:" + slug):
                try:
                    lst = radio._peek(key)
                except Exception:
                    lst = None
                if lst:
                    break
            pools[href] = [s for s in (lst or []) if isinstance(s, dict) and s.get("favicon")][:12]
        pool, n = pools[href], used.get(href, 0)
        used[href] = n + 1
        out.append(pool[n % len(pool)] if pool else None)
    return out


@bp.app_template_global("find_filters")
def _find_filters():
    return _home_filters()


def _home_filters():
    """The three drop-downs on the home page: country, language, category. Each choice is a real page."""
    from .topics import NAV
    nav = {k: slugs for k, _, slugs in NAV}
    az = lambda items: sorted(items, key=lambda x: x[1].lower())          # every list is A to Z
    countries = az([(topic_path(k), t["label"]) for k, t in TOPICS.items() if t["kind"] == "country"])
    languages = az([(topic_path(k), TOPICS[k]["label"]) for k in nav.get("languages", []) if k in TOPICS])
    # The category row (one line of boxes). Only Religious has types inside it; the rest open straight to their channels.
    cats = [("Religious", topic_path("religious")), ("Music", topic_path("music")), ("News", topic_path("news")),
            ("Business", topic_path("business")), ("Daily life", topic_path("daily-life")),
            ("Kids", topic_path("kids")), ("Cooking", topic_path("cooking")),
            ("Science & Tech", topic_path("technology")), ("Relax and sleep", topic_path("relax-sleep")),
            ("Accessibility", "/accessibility")]
    return countries, languages, cats


@bp.route("/")
def home():
    from . import podcasts
    stations, error = _stations_for("bollywood")
    meta = build_meta(page="home", canonical_path="/")
    return render_template("home.html", meta=meta, stations=protect(stations[:60]), error=error, cat="bollywood",
                           popular=_popular(), home_faq=islam_data.HOME_FAQ, market_sections=markets.view(),
                           guides=blog_data.posts_sorted()[:3],
                           pod_cats=sorted(((k, v[0]) for k, v in podcasts.CATEGORIES.items() if not k.startswith("top-")), key=lambda x: x[1].lower()),
                           filters=_home_filters(),
                           trending=_trend_rows(trends.top(6)),
                           ld=[website_ld(), webapp_ld(), organization_ld(), faq_ld(islam_data.HOME_FAQ)])


@bp.route("/<any(bollywood, lollywood, hollywood):cat>")
def category(cat):
    stations, error = _stations_for(cat)
    info = CATEGORY_PAGES[cat]
    meta = build_meta(info["seo_title"], info["description"], page=cat)
    return render_template("category.html", meta=meta, stations=protect(stations), error=error, cat=cat, info=info,
                           ld=[breadcrumb_ld([("Home", "/"), (info["h1"].split(" — ")[0], f"/{cat}")])])


@bp.route("/genre/<slug>")
def genre(slug):
    """Radio by type: Naat, Quran, Qawwali, Pashto, Jazz … (see topics.py)."""
    if slug not in GENRE_PAGES:
        if slug in COUNTRY_PAGES:
            return redirect(topic_path(slug), code=301)
        if slug in TOPIC_ALIASES:                          # a city page that used to be a copy of another page
            return redirect(topic_path(TOPIC_ALIASES[slug]), code=301)
        abort(404)
    return _topic_page(slug)


@bp.route("/country/<slug>")
def country_page(slug):
    """Radio by country: Pakistan, India, UK, Saudi Arabia …"""
    if slug not in COUNTRY_PAGES:
        if slug in GENRE_PAGES:
            return redirect(topic_path(slug), code=301)
        abort(404)
    return _topic_page(slug)


THIN_LIST = 1              # only an empty city or language page is kept out of Google (the owner wants every real page in)
_THIN_GROUPS = ("Cities", "World languages")
REGION_PAGE_MIN = 3        # a region/city gets its own page only when it has at least this many stations (no thin pages)


@bp.route("/country/<slug>/<region_slug>")
def country_region_page(slug, region_slug):
    """Radio of one region or city of a country: /country/paraguay/asuncion."""
    if slug not in COUNTRY_PAGES:
        abort(404)
    return _topic_page(slug, region_slug)


PAGE_SIZE = 100


def _paginate(stations):
    """100 stations per page (?page=2 …) so long lists stay fast; every station is still in the sitemap."""
    pages = max(1, -(-len(stations) // PAGE_SIZE))
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    page = min(max(page, 1), pages)
    return stations[(page - 1) * PAGE_SIZE: page * PAGE_SIZE], page, pages


def _country_neighbours(slug):
    """[(href, label)] of the countries next to this one (only real country pages), for the links on a country page."""
    return [(topic_path(n), COUNTRY_PAGES[n]["label"]) for n in NEIGHBOURS.get(slug, []) if n in COUNTRY_PAGES][:9]


def _state_counts(stations, top=12):
    """[(region, how many stations)] for the regions/cities named in the live list, biggest first."""
    counts = {}
    for st in stations:
        name = (st.get("state") or "").strip()
        if name:
            counts[name] = counts.get(name, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top]


_PLACE_WORDS = set()


def _place_words():
    """Lower-case names of every city and country page: a station tag like "lahore" is a place, not a style of music."""
    if not _PLACE_WORDS:
        _PLACE_WORDS.update(t["label"].lower() for t in TOPICS.values()
                            if t.get("group") == "Cities" or t["kind"] == "country")
    return _PLACE_WORDS


def _country_facts(label, total, stations, regions):
    """One short paragraph made from the live list itself (so it is different on every country page and always true)."""
    if not total:
        return ""
    tags = {}
    for st in stations:
        for t in (st.get("tags") or "").split(","):
            t = t.strip().lower()
            if t and len(t) > 2 and t not in _place_words():
                tags[t] = tags.get(t, 0) + 1
    styles = [t for t, _ in sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))[:4]]
    text = f"Right now Sur Music lists {total} live {label} radio station{'s' if total != 1 else ''} that play in your browser."
    if styles:
        text += " The most common styles are " + ", ".join(styles[:-1]) + (" and " if len(styles) > 1 else "") + styles[-1] + "."
    names = [x["name"] for x in stations[:3] if x.get("name")]
    if names:
        text += " The most played right now " + ("are " + ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else "is " + names[0]) + "."
    places = [r for r, _ in regions[:5]]
    if len(places) >= 2:
        text += " Stations broadcast from " + ", ".join(places[:-1]) + " and " + places[-1] + "."
    return text


def _preparing():
    """A page whose data is not loaded yet: a friendly 'we are working on it' page. Status 503 (not 404/200) so Google keeps the page and comes back."""
    resp = make_response(render_template("errors/preparing.html", meta={"title": "Page is being prepared | Sur Music", "noindex": True}), 503)
    resp.headers["Retry-After"] = "600"
    return resp


def _topic_page(slug, region_slug=None):
    info = base_info = TOPICS[slug]
    if info.get("people"):                         # a person: only podcasts and talks by them; no such audio, no page
        shows = _person_shows(slug, remember=False)         # only what is already saved: a visitor never waits for Apple or for the news feed
        news = _person_news(slug, wait=False)
        shown = {n["t"].lower()[:60] for n in news}
        soon = [x for x in _person_news(slug, wait=False, upcoming=True) if x["t"].lower()[:60] not in shown][:6]
        shows = shows or []
        if not shows and not news:                         # nothing real to show (no audio, no headlines): never an empty page
            if (info.get("pkind") != "music" and radio._peek("pod:p3:" + slug) is None) or not _stored_checked(slug):       # not looked up yet: come back soon (not "gone")
                _check_person_soon(slug)
                resp = _preparing()
                resp.headers["Retry-After"] = "3600"
                return resp
            abort(404)
        stations, error = [], None
    else:
        shows, news, soon = [], [], []
        try:
            stations, error = without_blocked(radio.genre_stations(slug)), None
        except radio.RadioError as exc:
            stations, error = [], str(exc)
    total = len(stations)
    all_stations = stations
    is_country = info["kind"] == "country"
    regions = _state_counts(all_stations) if is_country else []
    region = (request.args.get("region") or "").strip()[:60]
    region_page = ""
    if region_slug:                                                # /country/paraguay/asuncion: a real page of its own
        for name, n in _state_counts(all_stations, top=1000):
            if n >= REGION_PAGE_MIN and slugify(name) == region_slug and region_slug != "item":
                region_page = name
                break
        if not region_page:
            abort(404)
        region = region_page
    if is_country and region and (region_page or region in dict(regions)):    # ?region=Asunción: only that region's stations
        stations = [x for x in stations if (x.get("state") or "").strip() == region]
        total = len(stations)
        if region_page:
            c = base_info["label"]
            info = dict(base_info, label=f"{region_page}, {c}", native="", more="",
                        h1=f"Radio {region_page} — Live {c} Radio Stations",
                        seo_title=f"Radio {region_page}, {c} — Live Stations Online",
                        description=f"Listen to live radio from {region_page}, {c} free: {total} stations playing in your browser, no app and no sign-up.",
                        intro=f"Live radio stations from {region_page} in {c}. Pick a station, press play and keep browsing.")
    else:
        region = ""
    stations, page_no, pages = _paginate(stations)
    own = COUNTRY_ABOUT.get(slug) or GENRE_ABOUT.get(slug) or []
    if region_page:
        own = []
    description = f"Free live {info['label']} radio. {own[0]}" if own else info["description"]   # own text: a description no other page has
    meta = build_meta(info["seo_title"], description, page=None if region_page else f"genre-{slug}",
                      noindex=(not stations and not shows and not news) or page_no > 1 or bool(region and not region_page)
                      or (info.get("group") in _THIN_GROUPS and total < THIN_LIST)        # too few stations: little for Google
)      # an empty page (or page 2, 3, or one region) is not shown in Google
    meta["keywords"] = topic_keywords(info)
    label = info["label"]
    top = [x["name"] for x in all_stations[:3] if x.get("name")]
    popular = [x for x in all_stations[:8] if x.get("name")]
    faqs = [
        (f"Is {label} radio free to listen to?", f"Yes. Every {label} radio station on Sur Music plays free in your web browser."),
        (f"How do I listen to {label} radio online?", f"Open this page, choose a {label} station and press play. It works on a phone, tablet or computer."),
    ]
    if top:
        faqs.append((f"Which are the most popular {label} radio stations?", "Right now: " + ", ".join(top) + "."))
    person_text, person_eps = [], []
    if info.get("people"):                             # a person: text made only from what really exists (their shows and newest episodes)
        person_text, person_eps, faqs = _person_text(slug, info, shows, news)
    crumbs = [("Home", "/"), ("All radio", "/radio-stations")]
    if info["kind"] == "country" and info["group"] in CONTINENTS:
        crumbs.append((CONTINENTS[info["group"]][0], f"/continent/{info['group']}"))
    crumbs.append((base_info["h1"].split(" — ")[0], topic_path(slug)))
    if region_page:
        crumbs.append((region_page, request.path))
    trending = _trend_rows(trends.top(8)) if slug in ("sports", "news", "english-news", "talk", "pop") else []
    ld = [breadcrumb_ld(crumbs), collection_ld(info["h1"], info["description"], request.path if region_page else topic_path(slug), stations if region_page else all_stations)]
    if page_no == 1 and faqs:
        ld.append(faq_items_ld(faqs))
    own_text = (COUNTRY_ABOUT.get(slug) or GENRE_ABOUT.get(slug) or []) if page_no == 1 and not region_page else []
    if (is_country or info.get("group") in _THIN_GROUPS) and page_no == 1 and (region_page or not region) and not own_text:
        facts = _country_facts(label, total, stations if region_page else all_stations, [] if region_page else regions)
        own_text = [facts] if facts else []
    if person_text:
        own_text = person_text
    region_links = [(n, c, f"{topic_path(slug)}/{slugify(n)}" if c >= REGION_PAGE_MIN and slugify(n) != "item"
                     else f"{topic_path(slug)}?region={quote(n)}") for n, c in regions] if len(regions) > 1 else []
    return render_template("category.html", meta=meta, stations=protect(stations), error=error, cat=slug, shows=shows, person_eps=person_eps, news=news, soon=soon,
                           neighbours=_country_neighbours(slug) if is_country else [], regions=region_links, country_href=topic_path(slug),
                           active_region=region,
                           info=info, genre=slug, crumbs=crumbs, ld=ld, trending=trending, faqs=faqs if page_no == 1 else [], popular=popular if page_no == 1 else [],
                           total=total, page_no=page_no, pages=pages, page_base=request.path,
                           own_text=own_text, related=_related_links(slug) if not region_page else ("", []))


def _listed_countries(continent, minimum=3):
    """Countries of one continent that really have stations (all of them if the counts are not known)."""
    counts = radio.country_counts()
    out = []
    for slug, t in countries_in(continent):
        n = counts.get(t.get("code", ""), 0) if counts is not None else None
        if n is None or n >= minimum:
            out.append((slug, t, n))
    return out


def _listed_types(visible_only=False):
    return [(g, [(k, v) for k, v in items if not radio.known_empty(k)]) for g, items in grouped(visible_only)]


_A11Y_FAQ = [
    ("Is there a free radio for blind and visually impaired people?",
     "Yes. Sur Music is free and made to be used by ear: every station is a labelled button, your screen reader says the station name, "
     "and the keyboard alone can play, pause, skip and change the volume. No sign-up is needed."),
    ("Does Sur Music work with TalkBack, VoiceOver, NVDA and JAWS?",
     "Yes. It works with TalkBack on Android, VoiceOver on iPhone, iPad and Mac, and NVDA, JAWS and ChromeVox on computers. "
     "Station changes, errors and volume are announced."),
    ("Which keyboard shortcuts can I use?",
     "K plays or pauses, N is next station, B is previous station, M mutes, Alt with the up or down arrow changes the volume, "
     "and the slash key jumps to search."),
    ("Can I listen to the Quran, news and talk radio without seeing the screen?",
     "Yes. Quran, Naat, news, talk and cricket commentary stations are listed under the Accessibility tab. They are mostly speech, "
     "so they are easy to follow by ear."),
    ("Does the music keep playing when I open another page?",
     "Yes. The player stays on while you browse, and your screen reader reads the new page title."),
    ("Can I listen with the phone screen off?",
     "Yes. The free Sur Music Android app keeps playing with the screen locked and responds to headset and Bluetooth buttons."),
    ("Is there radio in Urdu, Hindi and Arabic for blind listeners?",
     "Yes. Open the Languages tab for Urdu, Hindi, Arabic, Punjabi, Pashto and more than thirty other languages, or use Near me for "
     "stations from your own country."),
    ("How do I report something that is hard to use?",
     "Use the Contact page. Accessibility problems are fixed first."),
]


@bp.route("/accessibility")
def accessibility():
    """How blind and low-vision listeners use Sur Music (screen readers, keyboard)."""
    meta = build_meta("Free Radio for the Blind & Visually Impaired — Screen Reader",
                      "Free online radio for blind and visually impaired listeners: works with TalkBack, VoiceOver, NVDA and JAWS, "
                      "keyboard shortcuts, spoken station names, Quran, news and talk radio from every country. No sign-up.",
                      page="accessibility")
    meta["keywords"] = ("radio for blind people, accessible radio, screen reader radio, talking radio player, "
                        "radio for visually impaired, keyboard radio player, TalkBack radio, VoiceOver radio, NVDA radio, "
                        "blind friendly radio, Quran for blind, audio news for blind, free radio no sign up, "
                        "نابینا افراد کے لیے ریڈیو, दृष्टिबाधित के लिए रेडियो, راديو للمكفوفين")
    page = page_ld("WebPage", "Accessible radio for blind and low-vision listeners", meta["description"])
    page["accessibilityFeature"] = ["ARIA", "structuralNavigation", "readingOrder", "tableOfContents", "alternativeText"]
    page["accessibilityControl"] = ["fullKeyboardControl", "fullMouseControl", "fullTouchControl"]
    page["accessibilityAPI"] = "ARIA"
    page["accessibilityHazard"] = ["noFlashingHazard"]
    page["audience"] = {"@type": "Audience", "audienceType": "Blind and visually impaired people"}
    return render_template("accessibility.html", meta=meta, faqs=_A11Y_FAQ,
                           ld=[page, breadcrumb_ld([("Home", "/"), ("Accessibility", "/accessibility")]),
                               faq_items_ld(_A11Y_FAQ)])


_MY_MUSIC_FAQ = [
    ("Are my songs uploaded to Sur Music?",
     "No. Your songs are played straight from your own device. Nothing is uploaded, so your music stays private."),
    ("Which file types can I play?",
     "MP3, M4A, AAC, WAV, OGG, FLAC and other audio formats your browser supports."),
    ("Do my playlists stay after I close the page?",
     "Playlist names and track names are saved in this browser. The song files stay on your device, so next time pick the same files "
     "and your playlists fill in automatically."),
]


@bp.route("/my-music")
def my_music():
    """A free music player for songs stored on the visitor's own computer or phone (nothing is uploaded)."""
    meta = build_meta("Free Music Player — Play Songs From Your Computer",
                      "Free online music player: play MP3 and other songs from your own computer or phone, build playlists, "
                      "shuffle and repeat. Nothing is uploaded. No sign-up.",
                      page="my-music")
    page = page_ld("WebPage", "Free music player for your own songs", meta["description"])
    return render_template("my_music.html", meta=meta, faqs=_MY_MUSIC_FAQ,
                           ld=[page, breadcrumb_ld([("Home", "/"), ("My music player", "/my-music")]),
                               faq_items_ld(_MY_MUSIC_FAQ)])


LETTERS = "abcdefghijklmnopqrstuvwxyz"

# Pakistani FM stations people search for as "<name> <frequency> <city>" (public frequency lists)
PK_FM = [
    ("FM 100 Pakistan", "100", "Karachi, Lahore, Islamabad, Hyderabad, Multan, Rahim Yar Khan, Gujrat, Jhelum, Abbottabad", "Pop and film music"),
    ("City FM 89", "89", "Karachi, Lahore, Islamabad, Faisalabad", "English and Urdu pop"),
    ("Mast FM 103", "103", "Karachi, Lahore, Faisalabad, Multan", "Pakistani and Indian hits"),
    ("Hot FM 105", "105", "Karachi, Hyderabad, Quetta, Larkana, Nawabshah, Badin", "Urdu music and talk"),
    ("Hum FM 106.2", "106.2", "Karachi, Lahore, Islamabad, Peshawar, Sukkur", "Entertainment"),
    ("Apna Karachi FM 107", "107", "Karachi", "Karachi city radio"),
    ("Radio 1 FM 91", "91", "Karachi, Lahore, Islamabad", "Music and news"),
    ("Power 99 FM", "99", "Islamabad, Abbottabad, Vehari", "Pop music"),
    ("Samaa FM 107.4", "107.4", "Karachi, Lahore, Islamabad, Bahawalpur", "News and music"),
    ("Radio Pakistan (PBC) FM 101", "101", "Karachi, Lahore, Islamabad, Multan, Faisalabad, Quetta, Hyderabad", "National broadcaster"),
    ("Suno FM 89.4", "89.4", "Karachi, Hyderabad", "Urdu music"),
    ("Radio Awaz FM 99", "99", "Karachi, Hyderabad, Jamshoro, Gujrat, Lahore", "Local voices"),
    ("Dil FM 102", "102", "Gujrat, Sahiwal, Kasur, Okara", "Punjabi and Urdu"),
    ("Radio Buraq FM 104", "104", "Peshawar, Sialkot, Mardan", "Pashto and Urdu"),
]


def pk_fm_for(name):
    """The PK_FM row for a station page ("Hum FM 106.2" -> its FM cities), or None."""
    low = f" {(name or '').lower().replace('-', ' ')} ".replace(" one ", " 1 ")
    for row in PK_FM:
        freq = row[1]
        brand = [w for w in row[0].lower().split() if w not in ("fm", freq) and not w.startswith("(")]
        if f" {freq} " in low and brand and all(f" {w} " in low for w in brand[:2]):
            return row
    return None


@bp.route("/api/podcasts")
def api_podcasts():
    """Shows for the moving podcast strip under the header (filled in by site.js; hidden until it has some)."""
    from . import podcasts
    demo = bool(current_app.config.get("TESTING") or current_app.config.get("RADIO_DEMO"))
    rows = podcasts.featured(demo)
    if not demo:
        if rows:
            radio.keep("keep:strip", rows)
        else:                                               # cold start: show the last good strip at once
            try:
                rows = radio._peek("keep:strip") or []
            except Exception:
                rows = []
    resp = jsonify({"items": [{"i": r["id"], "n": r["name"], "a": r["artist"], "m": r["img"]} for r in rows]})
    resp.headers["Cache-Control"] = "public, max-age=600" if rows else "no-store"      # an empty answer (cold start) is never kept
    return resp


def _json_cached(data, seconds=600):
    resp = jsonify(data)
    resp.headers["Cache-Control"] = f"public, max-age={seconds}" if seconds > 0 else "no-store"
    return resp


@bp.route("/api/podcasts/status")
def api_podcast_status():
    """A small health page: how many shows each list has, and the last error, so a problem can be seen at once."""
    from . import podcasts
    out = {"lists": {k: len(v[1]) for k, v in list(podcasts._cat.items())}, "errors": dict(podcasts._errors)}
    def probe(fn):
        try:
            return len(fn())
        except Exception as e:
            return f"{type(e).__name__}: {str(e)[:100]}"
    out["chart_new_address"] = probe(lambda: podcasts._chart_v2("us"))
    out["chart_with_fallback"] = probe(lambda: podcasts._chart("us"))
    out["search_test"] = probe(lambda: podcasts.search("business podcast"))
    resp = jsonify(out)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@bp.route("/api/podcasts/near")
def api_podcast_near():
    """Which chart to show this visitor: the one of his own country (Cloudflare tells us the country; Pakistan if unknown)."""
    from . import podcasts
    cc = (request.headers.get("CF-IPCountry") or request.args.get("cc") or "").strip().lower()[:2]
    if cc in podcasts.NEAR:
        info = {"cc": cc, "name": podcasts.NEAR[cc], "title": f"Top podcasts in {podcasts.NEAR[cc]}", "slug": f"top-{cc}"}
    else:                                                    # country unknown: the world chart, no country is preferred
        info = {"cc": "", "name": "the world", "title": "Top podcasts in the world", "slug": "top-world"}
    resp = jsonify({**info, "faith": "faiths", "faiths": [{"slug": "faiths", "name": "All faiths"}] + [{"slug": k, "name": n} for k, n in podcasts.FAITHS]})
    resp.headers["Cache-Control"] = "private, no-store"
    resp.headers["Vary"] = "CF-IPCountry"
    return resp


@bp.route("/api/podcasts/c/<slug>")
def api_podcast_category(slug):
    """Shows of one podcast category, for the Android app."""
    from . import podcasts
    if not podcasts.valid(slug):
        abort(404)
    demo = bool(current_app.config.get("TESTING") or current_app.config.get("RADIO_DEMO"))
    rows = podcasts.category(slug, demo)
    # an empty list (Apple was slow) must never be remembered by the phone or Cloudflare: the next request asks again
    return _json_cached({"items": [{"i": r["id"], "n": r["name"], "a": r["artist"], "m": r["img"]} for r in rows[:1000]]},
                        600 if rows else 0)


@bp.route("/api/podcasts/<int:sid>/episodes")
def api_podcast_episodes(sid):
    """Newest episodes of one show with their audio links, for the Android app (the audio plays from the podcaster's own server)."""
    from . import podcasts
    demo = bool(current_app.config.get("TESTING") or current_app.config.get("RADIO_DEMO"))
    row, eps = podcasts.show(sid, demo)
    if not row:
        abort(404)
    return _json_cached({"show": {"n": row["name"], "a": row["artist"], "m": row["img"]},
                         "items": [{"id": e["uuid"], "n": e["name"], "u": e["url"], "d": e.get("date", "")} for e in eps[:60]]}, 300)


def _podcast_ld(rows, name):
    return {"@context": "https://schema.org", "@type": "ItemList", "name": name, "numberOfItems": len(rows[:20]),
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": r["name"],
                                 "url": absolute(f"/podcasts/{r['id']}")} for i, r in enumerate(rows[:20])]}


def _podcast_list(slug, q, rows):
    from . import podcasts
    from .seo import faq_items_ld
    desc, intro, faqs = podcasts.PAGE_TEXT.get(slug, podcasts.PAGE_TEXT[""])
    if slug == "":
        title = "Podcasts — Urdu, Islamic, Hindi, Cricket, News"
    else:
        label = podcasts.label(slug)
        title = f"{label} Podcasts — Listen Free" if not label.lower().startswith("top") else f"{label} — Listen Free"
    meta = build_meta(title, desc, page="podcasts" if not slug else f"podcasts-{slug}", noindex=bool(q) or not rows)
    heading = (podcasts.label(slug) if slug else "Podcasts — Urdu, Islamic, Hindi, Cricket & News")
    crumbs = [("Home", "/"), ("Podcasts", "/podcasts")] + ([(podcasts.label(slug), f"/podcasts/c/{slug}")] if slug else [])
    ld = [breadcrumb_ld(crumbs)] + ([_podcast_ld(rows, heading)] if rows and not q else []) + ([faq_items_ld(faqs)] if faqs else [])
    facts = ""
    if rows and not q:                     # a sentence made from the live list itself: different on every category page
        top = [f"{r['name']}" + (f" by {r['artist']}" if r.get("artist") and r["artist"] != r["name"] else "") for r in rows[:3] if r.get("name")]
        facts = f"This page lists {len(rows)} show{'s' if len(rows) != 1 else ''}" + \
            (". At the top right now: " + "; ".join(top) + "." if top else ".")
    return render_template("podcasts.html", meta=meta, rows=rows, q=q, crumbs=crumbs, ld=ld, heading=heading, intro=intro, faqs=faqs, facts=facts,
                           cats=podcasts.CATEGORIES, here=slug)


@bp.route("/podcasts")
def podcasts_page():
    from . import podcasts
    demo = bool(current_app.config.get("TESTING") or current_app.config.get("RADIO_DEMO"))
    q = (request.args.get("q") or "").strip()[:60]
    return _podcast_list("", q, podcasts.search(q, demo) if q else podcasts.featured(demo))


@bp.route("/podcasts/c/<slug>")
def podcast_category(slug):
    from . import podcasts
    if slug in ("ahl-e-bait", "ahl-e-bait@pk", "ahl-e-bait@in"):            # a short-lived page: Shia podcasts now live inside Islamic lectures
        return redirect("/podcasts/c/islamic", code=301)
    if not podcasts.valid(slug):
        abort(404)
    demo = bool(current_app.config.get("TESTING") or current_app.config.get("RADIO_DEMO"))
    return _podcast_list(slug, "", podcasts.category(slug, demo))


def _podcast_facts(row, eps):
    """A paragraph from the show's own details and its newest episodes' notes, so each show page says something of its own."""
    if not eps:
        return "", []
    kind = f"a {row['genre'].lower()} podcast" if row.get("genre") and row["genre"].lower() != "podcasts" else "a podcast"
    text = f"{row['name']} is {kind}" + (f" by {row['artist']}" if row.get("artist") else "") + \
        f". Sur Music lists {len(eps)} of its episode{'s' if len(eps) != 1 else ''}; the newest is “{eps[0]['name']}”" + \
        (f", published {eps[0]['date'].strip()}" if eps[0].get("date") else "") + "."
    if len(eps) > 1:
        text += " Other recent episodes: " + "; ".join(e["name"] for e in eps[1:4] if e.get("name")) + "."
    notes = [(e["name"], e["about"]) for e in eps[:6] if e.get("about") and e["about"] != e.get("name")][:3]
    return text, notes


@bp.route("/podcasts/<int:sid>")
def podcast_page(sid):
    from . import podcasts
    demo = bool(current_app.config.get("TESTING") or current_app.config.get("RADIO_DEMO"))
    row, eps = podcasts.show(sid, demo)
    if not row:
        abort(404)
    facts, notes = _podcast_facts(row, eps)
    strong = bool(eps)                     # every show with episodes goes to Google; one whose feed did not load is empty
    desc = f"Listen to {row['name']} by {row['artist']} free on Sur Music. Press play on any episode."
    if strong:
        desc = f"Listen to {row['name']} by {row['artist']} free: {len(eps)} episodes, newest first. Latest: {eps[0]['name'][:70]}."
    meta = build_meta(f"{row['name'][:44]} — Podcast", desc, page=f"podcast-{sid}", noindex=not strong)
    crumbs = [("Home", "/"), ("Podcasts", "/podcasts"), (row["name"][:50], f"/podcasts/{sid}")]
    if request.args.get("order") == "old":
        eps = list(reversed(eps))
    series = {"@context": "https://schema.org", "@type": "PodcastSeries", "name": row["name"], "url": absolute(f"/podcasts/{sid}")}
    if row.get("img"):
        series["image"] = row["img"]
    if row.get("genre"):
        series["genre"] = row["genre"]
    if facts:
        series["description"] = facts[:300]
    if row.get("feed"):
        series["webFeed"] = row["feed"]
    series["episode"] = [{"@type": "PodcastEpisode", "name": e["name"], **({"description": e["about"]} if e.get("about") else {}),
                          "associatedMedia": {"@type": "MediaObject", "contentUrl": e["url"]}} for e in eps[:5] if e.get("name") and e.get("url")]
    return render_template("podcast.html", meta=meta, show=row, eps=protect(eps), old=request.args.get("order") == "old", sid=sid, crumbs=crumbs, ld=[breadcrumb_ld(crumbs), series],
                           facts=facts, notes=notes)


@bp.route("/pakistan-fm-radio")
def pakistan_fm():
    """Pakistani FM stations by frequency and city: the exact words people type into Google."""
    meta = build_meta("Pakistan FM Radio Live — FM 100, City FM 89, Mast FM 103, Hot FM 105 by City",
                      "Listen live to Pakistani FM radio online: FM 100, City FM 89, Mast FM 103, Hot FM 105, Hum FM, Radio Pakistan by frequency and city. Free, no app.",
                      page="pakistan-fm")
    faqs = [
        ("Which FM channel is best for Pakistani songs online?", "FM 100, City FM 89, Mast FM 103 and Hot FM 105 are among the most listened. Search them here and press play."),
        ("Can I listen to FM 100 Karachi or Lahore online?", "Yes. Search \"FM 100\" on Sur Music and play it free in your browser from any country."),
        ("Do I need an app to listen to Pakistan FM radio?", "No. It plays in your browser. The free Android app adds background play with the screen off."),
    ]
    crumbs = [("Home", "/"), ("Pakistan radio", "/country/pakistan"), ("Pakistan FM by frequency", "/pakistan-fm-radio")]
    return render_template("pakistan_fm.html", meta=meta, rows=PK_FM, faqs=faqs, crumbs=crumbs,
                           ld=[breadcrumb_ld(crumbs), faq_items_ld(faqs)])


@bp.route("/voices")
def voices():
    """Famous voices: every person who really has podcasts, talks or speeches here (filled in by the background check, kept in the database)."""
    people = _famous_voices(2000)
    meta = build_meta("Famous Voices — Podcasts, Talks & Speeches | Sur Music",
                      "Podcasts, talks, lectures and speeches by famous people from every faith, country and field. Free to play in your browser, no sign-up.",
                      page="voices", noindex=not people)
    crumbs = [("Home", "/"), ("Famous voices", "/voices")]
    return render_template("voices.html", meta=meta, people=people, crumbs=crumbs, ld=[breadcrumb_ld(crumbs)])


@bp.route("/top-100")
def top_100():
    """The 100 most-listened stations across every list on the site."""
    stations = without_blocked(radio.known_stations())[:100]
    meta = build_meta("Top 100 Radio Stations — Most Listened Live Radio Online",
                      "The 100 most popular live radio stations on Sur Music: Pakistani, Indian, Arabic, English, Naat, Quran, news and music. Free, no sign-up.",
                      page="top-100", noindex=not stations)
    crumbs = [("Home", "/"), ("Top 100 radio stations", "/top-100")]
    return render_template("directory.html", meta=meta, stations=protect(stations), crumbs=crumbs, letters=LETTERS, letter=None,
                           h1="Top 100 Radio Stations — Most Listened Live Online",
                           lead="The 100 most popular live radio stations on Sur Music right now, ranked by how many people listen. Press play on any station; it works free in your browser.",
                           ld=[breadcrumb_ld(crumbs), collection_ld("Top 100 radio stations", "Most listened live radio stations", "/top-100", stations)])


@bp.route("/stations/<letter>")
def stations_az(letter):
    """A–Z station directory: one page per first letter (0 = numbers), 100 stations per page, most listened first.
    Comes from the world station directory file (directory.py), so it is full right after a restart."""
    letter = letter.lower()
    if letter != "0" and (len(letter) != 1 or letter not in LETTERS):
        abort(404)
    per = 100                                # about 170 KB a page: lighter on visitors and on bandwidth
    try:
        pg = max(1, int(request.args.get("page", 1)))
    except ValueError:
        pg = 1

    def first(st):
        c = (st.get("name") or "?").strip()[:1].lower()
        return c if c in LETTERS else "0"
    from . import directory
    try:
        stations, total = directory.by_letter(letter, limit=per, offset=(pg - 1) * per)
    except Exception:                       # directory file not readable: the lists already in memory
        stations, total = [], 0
    if pg == 1:
        # stations from the site's own lists that the world directory may not have (e.g. HLS news channels)
        have = {x.get("uuid") for x in stations}
        extra = [x for x in radio.known_stations() if first(x) == letter and x.get("uuid") not in have]
        if not total:
            stations, total = extra, len(extra)
        else:
            stations = stations + extra[:50]
    stations = without_blocked(stations)
    pages = max(1, (total + per - 1) // per)
    if pg > pages:
        abort(404)
    shown = "numbers" if letter == "0" else letter.upper()
    meta = build_meta(f"Radio Stations Starting with {shown} — A–Z Radio Directory",
                      f"All live radio stations whose name starts with {shown}: free A–Z radio directory with Pakistani, Indian, Arabic and world stations.",
                      noindex=not stations or pg > 1)
    crumbs = [("Home", "/"), ("Top 100", "/top-100"), (f"Stations {shown}", f"/stations/{letter}")]
    return render_template("directory.html", meta=meta, stations=protect(stations), crumbs=crumbs, letters=LETTERS, letter=letter,
                           h1=f"Radio Stations Starting with {shown}",
                           lead=f"{total} live radio stations from A to Z that start with {shown}. Choose one and press play, free in your browser.",
                           page_no=pg, pages=pages,
                           ld=[breadcrumb_ld(crumbs)])


@bp.route("/radio-stations")
def all_topics():
    """One page that links to every type, continent and country — helps visitors and Google find them all."""
    meta = build_meta("All Radio Stations — World Radio by Country, Naat, Quran, News & Music",
                      "Live radio from every continent: Europe, America, Africa, Asia, the Middle East and Oceania, "
                      "plus Naat, Quran, qawwali, news, pop, rock, jazz and more — free in your browser.",
                      page="radio-stations")
    world = [(c, CONTINENTS[c][0], _listed_countries(c)) for c in CONTINENTS]
    return render_template("topics.html", meta=meta, groups=_listed_types(True), world=world, topic_path=topic_path,
                           ld=[breadcrumb_ld([("Home", "/"), ("All radio", "/radio-stations")])])


@bp.route("/continent/<slug>")
def continent(slug):
    """Radio from one continent: a list of its countries."""
    if slug not in CONTINENTS:
        abort(404)
    name, adjective = CONTINENTS[slug]
    items = _listed_countries(slug)
    meta = build_meta(f"{name} Radio Live — {adjective} Stations by Country",
                      f"Listen to live {adjective} radio free: choose a country in {name} and play its music, news "
                      "and talk stations in your browser.", page=f"continent-{slug}", noindex=not items)
    crumbs = [("Home", "/"), ("All radio", "/radio-stations"), (name, f"/continent/{slug}")]
    return render_template("continent.html", meta=meta, name=name, adjective=adjective, items=items,
                           topic_path=topic_path, crumbs=crumbs, ld=[breadcrumb_ld(crumbs)])


_og_slot = threading.BoundedSemaphore(1)


@bp.route("/og/station/<uuid>.png")
def station_card(uuid):
    """Share picture of one station (shown next to the link in WhatsApp, Facebook, …)."""
    from . import ogcard
    if not ogcard.UUID_RE.match(uuid):
        abort(404)
    st, _key = radio.station_by_uuid(uuid)
    if not st or is_blocked(st):
        abort(404)
    # a small server draws one picture at a time; a crawler asking for hundreds must not starve the real pages
    name, place = (st.get("name") or "Radio").strip()[:90], (st.get("country") or "").strip()[:40]
    if ogcard.is_ready(name, place):
        png = ogcard.render(name, place)
    elif not _og_slot.acquire(blocking=False):
        return Response("Busy, try again shortly", status=503, headers={"Retry-After": "60", "Cache-Control": "no-store"})
    else:
        try:
            png = ogcard.render(name, place)
        finally:
            _og_slot.release()
    return Response(png, mimetype="image/png", headers={"Cache-Control": "public, max-age=86400"})


def _station_facts(st, similar):
    """A short paragraph made only from what the directory really knows about this station (so every page differs)."""
    from urllib.parse import urlsplit
    out = []
    where = ", ".join(x for x in [st.get("state"), st.get("country")] if x)
    lang = st.get("language")
    if where or lang:
        out.append(f"{st['name']} broadcasts" + (f" from {where}" if where else "") + (f" in {lang}" if lang else "") + ".")
    if st.get("codec") or st.get("bitrate"):
        out.append("The live stream is " + " ".join(x for x in [f"{st['bitrate']} kbps" if st.get("bitrate") else "", st.get("codec") or ""] if x) + ".")
    if st.get("votes") or st.get("clicks"):
        out.append("Worldwide it has " + " and ".join(x for x in [f"{st['votes']:,} listener votes" if st.get("votes") else "",
                                                                  f"{st['clicks']:,} recent plays" if st.get("clicks") else ""] if x) + ".")
    host = urlsplit(st.get("homepage") or "").netloc.replace("www.", "")
    if host:
        out.append(f"Its own website is {host}.")
    names = [x["name"] for x in similar[:3] if x.get("name")]
    if names:
        out.append("Listeners of " + st["name"] + " also play " + (", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]) + ".")
    return " ".join(out)


def _station_description(st):
    """The Google snippet, made from this station's own details (place, language, styles, stream, website)."""
    from urllib.parse import urlsplit
    where = ", ".join(x for x in [st.get("state"), st.get("country")] if x)
    styles = ", ".join([t.strip() for t in (st.get("tags") or "").split(",") if t.strip()][:3])
    text = f"Listen to {st['name']} live online free."
    if where or st.get("language") or styles:
        text += " Broadcasting" + (f" from {where}" if where else "") + (f" in {st['language']}" if st.get("language") else "") + \
            (f": {styles}" if styles else "") + "."
    host = urlsplit(st.get("homepage") or "").netloc.replace("www.", "")
    extra = [f"{st['bitrate']} kbps stream" if st.get("bitrate") else "", f"official site {host}" if host else ""]
    if any(extra):
        text += " " + ", ".join(x for x in extra if x).capitalize() + "."
    return text + " Press play, no download."


def strong_station(st):
    """Every playing station goes into Google (the owner's choice): each page carries its own facts paragraph."""
    return bool(st.get("uuid") and st.get("url"))


@bp.route("/station/<uuid>")
@bp.route("/station/<uuid>/<slug>")
def station_page(uuid, slug=None):
    """Each station's own page: play button, details, similar stations and ads."""
    st, key = radio.station_by_uuid(uuid)
    if not st:
        from .topics import CODE_TO_COUNTRY
        gone = CODE_TO_COUNTRY.get(radio.gone_station_country(uuid))
        if gone:                                      # the station stopped playing: keep its Google visitors
            return redirect(topic_path(gone), code=301)
        abort(404)
    if is_blocked(st):
        abort(410)
    want = station_path(st)
    if request.path != want:
        return redirect(want, code=301)
    similar = []
    try:
        if key in CATEGORY_PAGES:
            similar = radio.category_stations(key)
        elif key in TOPICS:
            similar = radio.genre_stations(key)
    except radio.RadioError:
        similar = []
    similar = [s for s in without_blocked(similar) if s["uuid"] != st["uuid"]][:12]
    place = st.get("country") or "around the world"
    tags = st.get("tags") or "music"
    title = f"{st['name']} Live — Listen Online Free" if not st.get("country") else \
        f"{st['name']} Live — {st['country']} Radio Online Free"
    desc = _station_description(st)
    meta = build_meta(title, desc, canonical_path=want)
    if not strong_station(st):
        meta["robots"] = "noindex, follow"               # not in Google, but share previews and links still work
    meta["image"] = absolute(f"/og/station/{st['uuid']}.png")
    meta["og_type"] = "music.radio_station"
    meta["keywords"] = ", ".join(x for x in [st["name"], f"{st['name']} live", f"{st['name']} online", f"{st.get('country') or ''} radio".strip(), tags] if x)
    back = (CATEGORY_PAGES.get(key) or TOPICS.get(key) or {}).get("h1", "All radio").split(" — ")[0]
    back_href = f"/{key}" if key in CATEGORY_PAGES else (topic_path(key) if key in TOPICS else "/radio-stations")
    crumbs = [("Home", "/")]
    if key in TOPICS:
        crumbs.append(("All radio", "/radio-stations"))
        if TOPICS[key]["kind"] == "country" and TOPICS[key]["group"] in CONTINENTS:
            crumbs.append((CONTINENTS[TOPICS[key]["group"]][0], f"/continent/{TOPICS[key]['group']}"))
    if back_href != "/radio-stations" or key not in TOPICS:
        crumbs.append((back, back_href))
    crumbs.append((st["name"], want))
    faqs = [
        (f"How can I listen to {st['name']} live?", f"Press the play button on this page. {st['name']} plays straight in your browser on Sur Music — no app, no download and no sign-up."),
        (f"Is {st['name']} free to listen to?", f"Yes. Listening to {st['name']} on Sur Music is free. The stream comes directly from the station's own server."),
        (f"What does {st['name']} play?", f"{st['name']} is a radio station {('from ' + st['country'] + ' ') if st.get('country') else ''}playing {st.get('tags') or 'music and programmes'}."),
        (f"What can I do if {st['name']} stops playing?", "Stations sometimes go offline or change their address. Wait a minute and press play again, or pick another station from the list of similar stations below."),
    ]
    fm = pk_fm_for(st["name"])
    if fm:                                            # real frequency and cities: what people search for
        faqs.insert(0, (f"Where can I hear {st['name']} on FM?", f"On FM {fm[1]} in {fm[2]}. Anywhere else, listen live on this page."))
        meta["description"] = plain_text(f"Listen to {st['name']} live online free. On FM {fm[1]} in {fm[2]}.", 160)
    owner_fix = radio.STATION_FIXES.get(st["uuid"]) or {}
    if owner_fix.get("about"):                        # the station's own words: what its listeners search for
        faqs.insert(0, (f"What is {st['name']}?", owner_fix["about"]))
        meta["description"] = plain_text(f"Listen to {st['name']} live online free. {owner_fix['about']}", 160)
        meta["keywords"] += ", " + owner_fix.get("also", "")
    ld = [breadcrumb_ld(crumbs), station_ld(st, want), faq_items_ld(faqs)]
    page_url = absolute(want)
    share_text = f"Listen to {st['name']} live on Sur Music: {page_url}"
    share = [
        ("WhatsApp", "https://wa.me/?" + urlencode({"text": share_text})),
        ("Facebook", "https://www.facebook.com/sharer/sharer.php?" + urlencode({"u": page_url})),
        ("X", "https://twitter.com/intent/tweet?" + urlencode({"text": f"Listen to {st['name']} live", "url": page_url})),
        ("Telegram", "https://t.me/share/url?" + urlencode({"url": page_url, "text": f"Listen to {st['name']} live"})),
        ("Email", "mailto:?" + urlencode({"subject": f"{st['name']} live radio", "body": share_text}, quote_via=quote)),
    ]
    embed_code = (f'<iframe src="{absolute("/embed/station/" + st["uuid"])}" title="{html_escape(st["name"])} live radio player" '
                  f'width="100%" height="120" style="border:0;max-width:480px" loading="lazy"></iframe>'
                  f'<p style="font:13px sans-serif">Listen to <a href="{page_url}">{html_escape(st["name"])} live</a> on Sur Music</p>')
    details = [(label, value) for label, value in [
        ("Country", st.get("country")),
        ("City / region", st.get("state")),
        ("Language", st.get("language")),
        ("Genres", st.get("tags")),
        ("Stream quality", " ".join(x for x in [f"{st['bitrate']} kbps" if st.get("bitrate") else "", st.get("codec") or ""] if x)),
        ("Listeners", f"{st['clicks']:,} recent plays worldwide" if st.get("clicks") else ""),
        ("Worldwide votes", f"{st['votes']:,}" if st.get("votes") else ""),
    ] if value]
    likes, dislikes = like_counts(st["uuid"])
    return render_template("station.html", meta=meta, st=protect([st])[0], similar=protect(similar), cat=key or "", faqs=faqs,
                           facts=_station_facts(st, similar), related=_related_links(st=st),
                           likes=likes, dislikes=dislikes,
                           back=back, back_href=back_href, crumbs=crumbs, ld=ld, share=share, embed_code=embed_code,
                           details=details)


@bp.route("/embed/station/<uuid>")
def station_embed(uuid):
    """A small player other websites can put on their pages (like the "add this radio to your website" widgets
    of the big directories). It always links back to the station's page on Sur Music."""
    st, _key = radio.station_by_uuid(uuid)
    if not st or is_blocked(st):
        abort(404)
    page_url = absolute(station_path(st))
    playable = not gate_active()          # when sign-in is required the widget only links to the station page
    resp = make_response(render_template("embed_station.html", st=st, page_url=page_url, playable=playable))
    nonce = csp_nonce()
    resp.headers["Content-Security-Policy"] = (
        "default-src 'none'; " f"script-src 'nonce-{nonce}'; style-src 'unsafe-inline'; img-src https: data:; "
        "media-src https: blob:; base-uri 'none'; form-action 'none'; frame-ancestors *")
    resp.headers["X-Frame-Options"] = "ALLOWALL"
    resp.headers["X-Robots-Tag"] = "noindex, follow"
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@bp.app_template_global("offers_for")
def _offers_for(place, limit=3):
    return offers_for(place, limit)


@bp.route("/deals")
def deals():
    items = affiliate_offers(True) if get_settings().get("affiliate_enabled") == "1" else []
    meta = build_meta("Deals & recommendations — headphones, speakers and more",
                      "Hand-picked headphones, speakers and gadgets for better listening. Affiliate links.", page="deals")
    return render_template("deals.html", meta=meta, items=items,
                           ld=[page_ld("CollectionPage", "Deals & recommendations", meta["description"]),
                               breadcrumb_ld([("Home", "/"), ("Deals", "/deals")])])


@bp.route("/go/<oid>")
def go(oid):
    """Partner offer click: count it (Admin → Partner offers) and send the visitor to the stored link only."""
    o = next((x for x in affiliate_offers(True) if x.get("id") == oid), None)
    if not o or get_settings().get("affiliate_enabled") != "1":
        abort(404)
    if not rate_limited("go", 60, 600):
        from . import lowdb
        uid = session.get("uid") if lowdb.enabled() else (current_user() or {}).get("id")
        analytics.record("affiliate_click", uid, detail=f"{o['id']} · {o.get('store', '')} · {o.get('title', '')}")
    resp = redirect(o["url"], code=302)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    resp.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
    return resp


@bp.route("/search")
def search():
    q = " ".join((request.args.get("q") or "").split())[:60]
    stations, error = [], None
    if q:
        if rate_limited("search", 60, 300):
            error = "Too many searches. Please wait a moment."
        else:
            try:
                stations = without_blocked(radio.search_stations(q))
            except radio.RadioError as exc:
                error = str(exc)
    meta = build_meta(f"Search: {q}" if q else "Search radio stations", "Search live radio stations by name, "
                      "singer, city or genre.", page="search", noindex=bool(q))
    return render_template("search.html", meta=meta, q=q, stations=protect(stations), error=error)


@bp.route("/favorites")
def favorites():
    stations = []
    u = current_user()
    if u:
        stations = without_blocked([json.loads(r["station_json"]) for r in get_db().all(
            "SELECT station_json FROM favorites WHERE user_id = ? ORDER BY created_at DESC", (u["id"],))])
    meta = build_meta("My favourite stations", "Your saved radio stations.", page="favorites", noindex=True)
    return render_template("favorites.html", meta=meta, stations=stations)


@bp.route("/download")
def download_page():
    apps = {r["platform"]: r for r in get_db().all("SELECT * FROM apps")}
    meta = build_meta("Sur Music Apps — Android App & Chrome Extension",
                      "Sur Music for Android (free with ads; Pro without ads: free trial, then US$5 per year; download from this website) and the Chrome extension (7-day free "
                      "trial, then US$1/month), and how to install Sur Music on iPhone and iPad: 15 player themes, equalizer, voice commands, sleep timer, live news radio (HLS, AAC, MP3), background play, lock-screen controls and favourites.", page="download")
    return render_template("download.html", meta=meta, apps=apps, apk=apk_file(),
                           ld=[breadcrumb_ld([("Home", "/"), ("Download", "/download")]), android_app_ld()])


APK_NAME = "SurMusic.apk"
APK_DIR = os.path.join(os.path.dirname(__file__), "static", "downloads")


def apk_file():
    """The Android app file shipped with the website (app/static/downloads/SurMusic.apk), or None."""
    return os.path.isfile(os.path.join(APK_DIR, APK_NAME))


@bp.route("/download/<any(android, chrome):platform>")
def download_file(platform):
    if platform == "android" and apk_file():
        # The app itself is not secret: it only works after signing in with a paid account (one phone per account).
        u = current_user()
        analytics.record("download", u["id"] if u else None, detail="android (apk)")
        return send_from_directory(APK_DIR, APK_NAME, as_attachment=True, download_name=APK_NAME,
                                   mimetype="application/vnd.android.package-archive", max_age=300)
    app_row = get_db().one("SELECT * FROM apps WHERE platform = ?", (platform,))
    if not app_row:
        abort(404)
    # Other apps are sold through the Chrome Web Store: no free file download from the website.
    if valid_url(app_row["external_url"], https_only=True):
        u = current_user()
        analytics.record("download", u["id"] if u else None, detail=f"{platform} (store link)")
        return redirect(app_row["external_url"], code=302)
    abort(404)


@bp.route("/donate")
def donate():
    methods = {m: donation_method(m) for m in ("jazzcash", "nayapay", "wise")}
    meta = build_meta("Support Sur Music — Keep Free Radio Free", "Support Sur Music and Mousa International "
                      "Software House with JazzCash, NayaPay or an international transfer.", page="donate")
    return render_template("donate.html", meta=meta, methods=methods,
                           ld=[page_ld("WebPage", "Support Sur Music", meta["description"])])


@bp.route("/for-stations")
def for_stations():
    """For radio station owners: put the free Sur Music player (with a link back) on their own website."""
    meta = build_meta("Free Radio Player for Your Station's Website",
                      "Radio stations: add a free live player of your station to your own website in one minute. "
                      "No account, no fee. Works on phones and with screen readers.", page="for-stations")
    site = current_app.config["SITE_URL"]
    badge_code = (f'<a href="{site}/" title="Listen live on Sur Music Radio" '
                  f'style="display:inline-block;padding:8px 14px;border-radius:999px;background:#e11d48;color:#fff;'
                  f'font:600 14px sans-serif;text-decoration:none">&#9654; Listen on Sur Music Radio</a>')
    return render_template("for_stations.html", meta=meta, badge_code=badge_code,
                           ld=[breadcrumb_ld([("Home", "/"), ("For radio stations", "/for-stations")])])


@bp.route("/about")
def about():
    meta = build_meta("About Sur Music — Free Online Radio by MISH", get_settings()["about_md"], page="about")
    return render_template("about.html", meta=meta, ld=[organization_ld()])


@bp.route("/contact", methods=["GET", "POST"])
def contact():
    s = get_settings()
    u = current_user()
    removal = request.args.get("topic") == "removal"
    form = {"name": (u["display_name"] if u else ""), "email": (u["email"] if u else "")}
    station = " ".join((request.args.get("station") or "").split())[:100]
    if removal:
        form["subject"] = ("Station removal request: " + station) if station else "Station removal request"
    elif request.args.get("topic") == "update":
        form["subject"] = ("Station details update: " + station) if station else "Station details update"
    errors = {}
    if request.method == "POST":
        form = {k: (request.form.get(k) or "").strip() for k in ("name", "email", "subject", "message")}
        if not 2 <= len(form["name"]) <= 100:
            errors["name"] = "Please enter your name (2–100 characters)."
        if not valid_email(form["email"]):
            errors["email"] = "Please enter a valid email address."
        if not 3 <= len(form["subject"]) <= 150:
            errors["subject"] = "Please enter a subject (3–150 characters)."
        if not 10 <= len(form["message"]) <= 5000:
            errors["message"] = "Please write a message (10–5000 characters)."
        if request.form.get("website"):
            errors["form"] = "Submission rejected."
        if not errors and rate_limited("contact", 5, 3600):
            errors["form"] = "Too many messages from your connection. Please try again in an hour."
        if not errors:
            status = send_mail(s.get("contact_email"), f"[Sur Music contact] {form['subject']}",
                               f"From: {form['name']} <{form['email']}>\n\n{form['message']}", reply_to=form["email"])
            db = get_db()
            db.insert("messages", {"name": form["name"], "email": form["email"], "subject": form["subject"],
                                   "body": form["message"], "email_status": status, "is_read": 0,
                                   "ip_hash": ip_hash(), "created_at": utcnow()})
            db.commit()
            u = current_user()
            analytics.record("contact", u["id"] if u else None, detail=form["subject"])
            if status == "sent":
                flash("Thank you — your message was sent. We will reply by email.", "success")
            else:
                flash("Thank you — your message was received. Replies may take a little longer while email "
                      "notifications are being set up.", "success")
            return redirect(url_for("public.contact"))
    meta = build_meta("Contact Sur Music — Support, Feedback and Ads", "Questions, feedback, station removal "
                      "requests or advertising enquiries for Sur Music by Mousa International Software House.",
                      page="contact")
    return render_template("contact.html", meta=meta, form=form, errors=errors, removal=removal,
                           ld=[page_ld("ContactPage", "Contact Sur Music", meta["description"])]), (400 if errors else 200)


def _approved_reviews(limit=40):
    try:
        return get_db().all("SELECT name, rating, body, created_at FROM reviews WHERE status = 'approved' "
                            "ORDER BY created_at DESC LIMIT ?", (limit,))
    except Exception:
        return []


@bp.route("/reviews", methods=["GET", "POST"])
def reviews():
    """Listeners' reviews of Sur Music. New reviews wait for the owner's approval before they are shown."""
    form, errors = {"name": "", "rating": "5", "body": ""}, {}
    if request.method == "POST":
        form = {k: " ".join((request.form.get(k) or "").split()) for k in ("name", "rating")}
        form["body"] = (request.form.get("body") or "").strip()
        if not 2 <= len(form["name"]) <= 40:
            errors["name"] = "Please enter a first name or nickname (2–40 characters)."
        if form["rating"] not in ("1", "2", "3", "4", "5"):
            errors["rating"] = "Please choose 1 to 5 stars."
        if not 10 <= len(form["body"]) <= 600:
            errors["body"] = "Please write 10–600 characters."
        if re.search(r"https?://|www\.|@\w+\.\w+", form["body"] + " " + form["name"], re.I):
            errors["body"] = "Please do not put links or email addresses in a review."
        if request.form.get("website"):
            errors["form"] = "Submission rejected."
        if not errors and rate_limited("review", 3, 3600):
            errors["form"] = "Too many reviews from your connection. Please try again later."
        if not errors:
            db = get_db()
            db.insert("reviews", {"name": form["name"], "rating": int(form["rating"]), "body": form["body"],
                                  "status": "pending", "ip_hash": ip_hash(), "created_at": utcnow()})
            db.commit()
            flash("Thank you! Your review was received and will appear after a quick check.", "success")
            return redirect(url_for("public.reviews"))
    items = _approved_reviews()
    meta = build_meta("Sur Music Reviews — What Listeners Say About Our Radio",
                      "Read what listeners say about Sur Music, the free online radio and music player, and write your own "
                      "review. Reviews are checked by us before they appear.", page="reviews")
    ld = [page_ld("CollectionPage", "Sur Music listener reviews", meta["description"]),
          breadcrumb_ld([("Home", "/"), ("Reviews", "/reviews")])]
    if len(items) >= 5:          # star rating goes to Google only once there are enough real, approved reviews
        app_ld = webapp_ld()
        app_ld["aggregateRating"] = {"@type": "AggregateRating",
                                     "ratingValue": round(sum(r["rating"] for r in items) / len(items), 1),
                                     "reviewCount": len(items), "bestRating": 5, "worstRating": 1}
        ld.append(app_ld)
    return render_template("reviews.html", meta=meta, items=items, form=form, errors=errors, ld=ld), (400 if errors else 200)


def _policy(key, page, title, description, extra_ld=None):
    meta = build_meta(title, description, page=page)
    ld = [breadcrumb_ld([("Home", "/"), (title, request.path)])] + ([extra_ld] if extra_ld else [])
    return render_template("policy.html", meta=meta, title=title, body=get_settings()[key], ld=ld)


@bp.route("/faq")
def faq():
    return _policy("faq_md", "faq", "Frequently Asked Questions", "Answers about Sur Music: how to listen to live radio free, accounts, "
                   "the Android app, the Chrome extension, donations and removal requests.", faq_ld(get_settings()["faq_md"]))


@bp.route("/privacy")
def privacy():
    return _policy("privacy_md", "privacy", "Privacy Policy", "How Sur Music protects your data: what we collect, how long we keep it, your choices, cookies, ads and how to contact us.")


@bp.route("/terms")
def terms():
    return _policy("terms_md", "terms", "Terms of Use — Free Online Radio, Accounts and Apps", "The terms for using Sur Music: free listening, accounts, acceptable use, third-party radio streams, apps and donations.")


@bp.route("/disclaimer")
def disclaimer():
    return _policy("disclaimer_md", "disclaimer", "Disclaimer — Live Radio Streams and Station Content", "Sur Music plays public live radio streams from stations around the "
                   "world. All music and station names belong to their owners.")


@bp.route("/donation-disclaimer")
def donation_disclaimer():
    return _policy("donation_disclaimer_md", "donation-disclaimer", "Donation Disclaimer",
                   "How donations to Sur Music work: voluntary, not refundable, not a purchase, and how to ask us about a payment.")


@bp.route("/cookies")
def cookies():
    return _policy("cookies_md", "cookies", "Cookie Policy", "The cookies and local browser storage Sur Music uses to keep you signed in, remember settings and show ads.")


# ---------------------------------------------------------------- JSON API (used by player.js)

@bp.route("/api/stations/<any(bollywood, lollywood, hollywood):cat>")
def api_stations(cat):
    stations, error = _stations_for(cat)
    resp = jsonify({"stations": protect(without_blocked(stations)), "error": error})
    resp.headers["Cache-Control"] = "private, max-age=300"
    return resp


@bp.route("/api/search")
def api_search():
    q = " ".join((request.args.get("q") or "").split())[:60]
    if rate_limited("search", 60, 300):
        return jsonify({"stations": [], "error": "Too many searches. Please wait a moment."}), 429
    try:
        return jsonify({"stations": protect(without_blocked(radio.search_stations(q))), "error": None})
    except radio.RadioError as exc:
        return jsonify({"stations": [], "error": str(exc)}), 503


@bp.route("/api/me")
def api_me():
    u = current_user()
    return jsonify({"user": {"name": u["display_name"] or u["email"].split("@")[0]} if u else None,
                    "favorites": _user_favorite_ids(), "gate": gate_active()})


@bp.route("/api/welcome")
def api_welcome():
    """The visitor's country for the waving-flag welcome bar (empty when it is not known)."""
    from . import geo
    code = (visitor_country() or "").lower()
    flag_file = os.path.join(current_app.static_folder, "flags", code + ".svg")
    out = {}
    if len(code) == 2 and code.isalpha() and os.path.exists(flag_file):
        out = {"code": code, "name": geo.country_name(code), "flag": "/static/flags/" + code + ".svg"}
    resp = jsonify(out)
    resp.headers["Cache-Control"] = "private, max-age=300"
    resp.headers["Vary"] = "Accept-Language, CF-IPCountry"
    return resp


_WX_ICONS = (("thunder", "⛈️"), ("snow", "❄️"), ("rain", "🌧️"), ("drizzle", "🌦️"), ("shower", "🌦️"), ("fog", "🌫️"), ("overcast", "☁️"), ("cloud", "⛅"))


@bp.route("/api/app/weather")
def api_app_weather():
    """Weather for the Android app: every listed city that has data, with its 7-day forecast."""
    _weather_start()
    out = []
    for name, country, _key, _la, _lo in weather.CITIES:
        d = _weather_data(slugify(name, 60))
        if d:
            out.append({"name": name, "country": country, "temp": d["temp"], "text": d["text"],
                        "days": [{k: v for k, v in day.items() if isinstance(v, (str, int, float)) or v is None} for day in d["days"][:7]]})
    return _json_cached({"cities": out}, 600 if out else 0)


@bp.route("/api/app/news")
def api_app_news():
    """Today's headlines for the Android app (the same ones as the /today page)."""
    try:
        today_news.start(current_app._get_current_object(), radio.keep, radio._peek)
    except Exception:
        pass
    data = today_news.get()
    if not data["sections"]:
        try:
            today_news.load_saved(radio._peek("keep:today"))
        except Exception:
            pass
        data = today_news.get()
    ready = len(data["sections"]) >= 3
    return _json_cached({"sections": [{"name": k, "items": [{"t": n.get("t", ""), "s": n.get("s", "")} for n in v[:12]]}
                                      for k, v in data["sections"].items()] if ready else []}, 600 if ready else 0)


@bp.route("/api/app/voices")
def api_app_voices():
    """Famous voices for the Android app: only people who really have podcasts or talks."""
    people = _famous_voices(2000)
    return _json_cached({"items": [{"slug": path.rsplit("/", 1)[-1], "n": label, "m": cover or ""} for path, label, cover in people]},
                        600 if people else 0)


@bp.route("/api/app/voices/<slug>")
def api_app_voice_shows(slug):
    """The shows of one famous voice, in the same shape as /api/podcasts."""
    if slug not in _FOUND:
        abort(404)
    rows = _person_shows(slug, remember=False) or []
    return _json_cached({"items": [{"i": r["id"], "n": r["name"], "a": r["artist"], "m": r["img"]} for r in rows]}, 600 if rows else 0)


@bp.route("/api/weather-chip")
def api_weather_chip():
    """The small weather gadget in the header: the visitor's own city if it is in the list, else the first listed city of the visitor's country."""
    code = (visitor_country() or "").upper()
    city = ""
    try:
        city = (analytics._location()[1] or "").strip().lower()
    except Exception:
        city = ""
    pick = next((c for c in weather.CITIES if city and c[0].lower() == city), None)
    own = None
    if not pick and city and code:
        own = weather.place(code, city)                       # the visitor's own town: looked up in the background the first time
    if not pick and not own and code:
        pick = next((c for c in weather.CITIES if (TOPICS.get(c[2]) or {}).get("code") == code), None)
    out = {}
    d = own or (_weather_data(slugify(pick[0], 60)) if pick else None)
    name = own["name"] if own else (pick[0] if pick else "")
    if d:
        low = d["text"].lower()
        out = {"href": "/weather" if own else "/weather/" + slugify(pick[0], 60), "name": name, "temp": d["temp"], "text": d["text"],
               "icon": next((i for k, i in _WX_ICONS if k in low), "☀️"), "own": bool(own), "more": bool(city and code and not own and not (pick and pick[0].lower() == city))}
    _weather_start()
    resp = jsonify(out)
    resp.headers["Cache-Control"] = "private, no-store"            # differs for every visitor: never shared by a cache
    resp.headers["Vary"] = "Accept-Language, CF-IPCountry"
    return resp


@bp.route("/api/headlines")
def api_headlines():
    """Headlines for the news strip: the visitor's own country (English edition), refreshed by itself."""
    from . import headlines
    if current_app.config.get("TESTING") or current_app.config.get("RADIO_DEMO"):
        items = []
    else:
        cc = visitor_country()
        items = headlines.get(cc)
        key = "keep:news:" + (cc if re.fullmatch(r"[A-Z]{2}", cc or "") else "US")
        if items:
            radio.keep(key, items)
        else:
            try:
                items = radio._peek(key) or []
            except Exception:
                items = []
    resp = jsonify({"items": items})
    resp.headers["Cache-Control"] = "private, max-age=120" if items else "no-store"
    resp.headers["Vary"] = "Accept-Language, CF-IPCountry"
    return resp


@bp.route("/api/stream", methods=["POST"])
def api_stream():
    """Give the playable URL for a station token — only to signed-in members when sign-in is required."""
    if gate_active() and not current_user():
        return jsonify({"error": "login_required"}), 401
    st = _unlock(_json_body().get("station"))
    if not st:
        abort(400)
    if is_blocked(st):
        return jsonify({"error": "removed"}), 410
    return jsonify({"url": st["url"]})


@bp.route("/api/nowplaying", methods=["POST"])
def api_nowplaying():
    """The song that is on air right now (from the stream's own title information), or an empty string."""
    if gate_active() and not current_user():
        return jsonify({"title": ""})
    if rate_limited("nowplaying", 60, 600):
        return jsonify({"title": ""}), 429
    st = _unlock(_json_body().get("station"))
    if not st or is_blocked(st):
        return jsonify({"title": ""})
    return jsonify({"title": radio.now_playing(st["url"])})


APP_LICENSE_IDLE_DAYS = 7          # a second phone may take over a subscription after 7 days of silence


@bp.route("/api/app/license", methods=["POST"])
def api_app_license():
    """The Android app asks: may this phone use this Play subscription? One subscription, one phone.

    Only hashes are stored. The app has already checked with Google Play that the subscription is real."""
    import hashlib
    import re as _re
    data = _json_body()
    token, install = data.get("token"), data.get("install")
    if not (isinstance(token, str) and 20 <= len(token) <= 4000 and isinstance(install, str)
            and _re.fullmatch(r"[A-Za-z0-9-]{16,80}", install)):
        return jsonify({"ok": False, "reason": "bad_request"}), 400
    if rate_limited("applicense", 60, 3600):
        return jsonify({"ok": False, "reason": "slow_down"}), 429
    th = hashlib.sha256(token.encode()).hexdigest()
    ih = hashlib.sha256(install.encode()).hexdigest()
    db = get_db()
    now = datetime.now(timezone.utc)
    stamp = now.replace(microsecond=0).isoformat()
    row = db.one("SELECT install_hash, last_seen FROM app_licenses WHERE token_hash = ?", (th,))
    if row is None:
        db.execute("INSERT INTO app_licenses (token_hash, install_hash, first_seen, last_seen) VALUES (?, ?, ?, ?)",
                   (th, ih, stamp, stamp))
    elif row["install_hash"] == ih:
        db.execute("UPDATE app_licenses SET last_seen = ? WHERE token_hash = ?", (stamp, th))
    else:
        try:
            idle = now - datetime.fromisoformat(row["last_seen"])
        except ValueError:
            idle = timedelta(days=999)
        if idle < timedelta(days=APP_LICENSE_IDLE_DAYS):
            return jsonify({"ok": False, "reason": "other_device"}), 403
        db.execute("UPDATE app_licenses SET install_hash = ?, last_seen = ? WHERE token_hash = ?", (ih, stamp, th))
    db.commit()
    return jsonify({"ok": True})


@bp.route("/api/track", methods=["POST"])
def api_track():
    """Page-view beacon from site.js (gives the time zone for approximate location)."""
    data = _json_body()
    path = data.get("path") if isinstance(data.get("path"), str) else ""
    if not path.startswith("/") or path.startswith(("/admin", "/api")) or len(path) > 200:
        return jsonify({"ok": True})
    if rate_limited("track", 300, 600):
        return jsonify({"ok": True})
    analytics.remember_timezone(data.get("tz"))
    from . import lowdb
    if lowdb.enabled():
        uid = session.get("uid")
    else:
        u = current_user()
        uid = u["id"] if u else None
    ref = data.get("ref") if isinstance(data.get("ref"), str) else ""
    analytics.record("page_view", uid, path.split("?")[0], referrer=analytics.referrer_domain(ref))
    return jsonify({"ok": True})


@bp.route("/api/heartbeat", methods=["POST"])
def api_heartbeat():
    """While a station is playing the player calls this every minute (powers Admin → Live now)."""
    data = _json_body()
    from . import lowdb
    if lowdb.enabled():
        uid = session.get("uid")            # signed session cookie; no database look-up while listening
    else:
        u = current_user()
        uid = u["id"] if u else None
    if rate_limited("heartbeat", 60, 600):
        return jsonify({"ok": True})
    if data.get("stop"):
        analytics.stop_listening(uid)
        return jsonify({"ok": True})
    name = data.get("station_name") if isinstance(data.get("station_name"), str) else ""
    cat = data.get("category") if data.get("category") in CATEGORY_PAGES else ""
    if name:
        analytics.heartbeat(uid, " ".join(name.split())[:120], cat)
    return jsonify({"ok": True})


@bp.route("/api/play", methods=["POST"])
def api_play():
    data = _json_body()
    if gate_active() and not current_user():
        return jsonify({"error": "login_required"}), 401
    st = _unlock(data.get("station"))
    if not st:
        abort(400)
    if is_blocked(st):
        return jsonify({"error": "removed"}), 410
    if rate_limited("play", 120, 3600):
        return jsonify({"ok": True})
    cat = data.get("category") if data.get("category") in CATEGORY_PAGES else ""
    from . import lowdb
    if lowdb.enabled():
        # no database wake-up: queue the play (and a member's history) for the next batch write
        uid = session.get("uid")
        lowdb.defer("INSERT INTO plays (station_uuid, station_name, category, created_at) VALUES (?, ?, ?, ?)",
                    (st["uuid"], st["name"], cat, utcnow()))
        analytics.record("play", uid, detail=st["name"])
        if uid:
            lowdb.defer("DELETE FROM history WHERE user_id = ? AND station_uuid = ?", (uid, st["uuid"]))
            lowdb.defer("INSERT INTO history (user_id, station_uuid, station_json, played_at) VALUES (?, ?, ?, ?)",
                        (uid, st["uuid"], json.dumps(st), utcnow()))
        return jsonify({"ok": True})
    db = get_db()
    db.insert("plays", {"station_uuid": st["uuid"], "station_name": st["name"], "category": cat,
                        "created_at": utcnow()})
    u = current_user()
    analytics.record("play", u["id"] if u else None, detail=st["name"])
    if u:
        db.execute("DELETE FROM history WHERE user_id = ? AND station_uuid = ?", (u["id"], st["uuid"]))
        db.insert("history", {"user_id": u["id"], "station_uuid": st["uuid"], "station_json": json.dumps(st),
                              "played_at": utcnow()})
        old = db.all("SELECT id FROM history WHERE user_id = ? ORDER BY played_at DESC LIMIT 1000 OFFSET 50",
                     (u["id"],))
        for r in old:
            db.execute("DELETE FROM history WHERE id = ?", (r["id"],))
    db.commit()
    return jsonify({"ok": True})


def like_counts(uuid):
    """(likes, dislikes) of one station from listeners on Sur Music (cached, so pages do not wake the database)."""
    from . import lowdb
    key = "likes:" + uuid
    if lowdb.enabled():
        hit, value = lowdb.cache_get(key)
        if hit:
            return tuple(value)
    row = get_db().one("SELECT SUM(CASE WHEN value = 1 THEN 1 ELSE 0 END) AS up, "
                       "SUM(CASE WHEN value = -1 THEN 1 ELSE 0 END) AS down FROM station_likes WHERE station_uuid = ?", (uuid,))
    out = (int((row or {}).get("up") or 0), int((row or {}).get("down") or 0)) if row else (0, 0)
    if lowdb.enabled():
        lowdb.cache_set(key, list(out), 600)
    return out


@bp.route("/api/like", methods=["POST"])
def api_like():
    """Like (1), dislike (-1) or clear (0) a station — one vote per visitor, like myTuner's thumbs."""
    data = _json_body()
    uuid = data.get("uuid") if isinstance(data.get("uuid"), str) else ""
    value = data.get("value")
    if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", uuid) or value not in (1, -1, 0):
        abort(400)
    st, _key = radio.station_by_uuid(uuid)
    if not st or is_blocked(st):
        abort(404)
    if rate_limited("like", 60, 3600):
        return jsonify({"error": "rate_limited"}), 429
    db, who = get_db(), ip_hash()
    db.execute("DELETE FROM station_likes WHERE station_uuid = ? AND ip_hash = ?", (uuid, who))
    if value:
        db.execute("INSERT INTO station_likes (station_uuid, ip_hash, value, created_at) VALUES (?, ?, ?, ?)",
                   (uuid, who, value, utcnow()))
    db.commit()
    from . import lowdb
    row = db.one("SELECT SUM(CASE WHEN value = 1 THEN 1 ELSE 0 END) AS up, "
                 "SUM(CASE WHEN value = -1 THEN 1 ELSE 0 END) AS down FROM station_likes WHERE station_uuid = ?", (uuid,))
    up, down = int((row or {}).get("up") or 0), int((row or {}).get("down") or 0)
    if lowdb.enabled():
        lowdb.cache_set("likes:" + uuid, [up, down], 600)
    return jsonify({"ok": True, "likes": up, "dislikes": down, "value": value})


@bp.route("/api/favorites", methods=["GET", "POST"])
def api_favorites():
    u = current_user()
    if not u:
        abort(401)
    db = get_db()
    if request.method == "POST":
        st = _unlock(_json_body().get("station"))
        if not st:
            abort(400)
        if is_blocked(st):
            return jsonify({"error": "removed"}), 410
        if db.scalar("SELECT COUNT(*) FROM favorites WHERE user_id = ?", (u["id"],)) >= 500:
            return jsonify({"error": "You can save up to 500 favourites."}), 400
        if not db.one("SELECT id FROM favorites WHERE user_id = ? AND station_uuid = ?", (u["id"], st["uuid"])):
            db.insert("favorites", {"user_id": u["id"], "station_uuid": st["uuid"], "station_json": json.dumps(st),
                                    "created_at": utcnow()})
            db.commit()
            analytics.record("favorite", u["id"], detail=st["name"])
    rows = db.all("SELECT station_json FROM favorites WHERE user_id = ? ORDER BY created_at DESC", (u["id"],))
    return jsonify({"favorites": without_blocked([json.loads(r["station_json"]) for r in rows])})


@bp.route("/api/favorites/<path:uuid>", methods=["DELETE"])
def api_favorite_delete(uuid):
    u = current_user()
    if not u:
        abort(401)
    db = get_db()
    db.execute("DELETE FROM favorites WHERE user_id = ? AND station_uuid = ?", (u["id"], uuid[:64]))
    db.commit()
    return jsonify({"ok": True})


@bp.route("/api/favorites/import", methods=["POST"])
def api_favorites_import():
    """Move favourites saved in the browser into the account after sign-in."""
    u = current_user()
    if not u:
        abort(401)
    items = _json_body().get("stations")
    if not isinstance(items, list):
        abort(400)
    db = get_db()
    have = {r["station_uuid"] for r in db.all("SELECT station_uuid FROM favorites WHERE user_id = ?", (u["id"],))}
    added = 0
    for raw in items[:200]:
        st = _unlock(raw)
        if st and not is_blocked(st) and st["uuid"] not in have and len(have) < 500:
            db.insert("favorites", {"user_id": u["id"], "station_uuid": st["uuid"], "station_json": json.dumps(st),
                                    "created_at": utcnow()})
            have.add(st["uuid"])
            added += 1
    db.commit()
    return jsonify({"added": added})


# ---------------------------------------------------------------- infrastructure

@bp.route("/media/<name>")
def media(name):
    path = media_path(name)
    if path:
        resp = send_file(path, max_age=60 * 60 * 24 * 30)
    else:
        found = media_bytes(name)
        if not found:
            abort(404)
        resp = current_app.response_class(found[0], mimetype=found[1])
        resp.headers["Cache-Control"] = "public, max-age=2592000"
    resp.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
    return resp


@bp.route("/<key>.txt")
def indexnow_key(key):
    """IndexNow ownership proof: the file name and the text inside are the same key."""
    from . import indexnow
    if len(key) == 32 and key == indexnow.key_for(current_app.config["SECRET_KEY"]):
        return key, 200, {"Content-Type": "text/plain; charset=utf-8"}
    abort(404)


ADMOB_PUBLISHER_LINE = "google.com, pub-1108836433307648, DIRECT, f08c47fec0942fa0"


@bp.route("/ads.txt")
def ads_txt():
    return _ads_txt_response([])


@bp.route("/app-ads.txt")                # the same lines plus the AdMob publisher of the Android app
def app_ads_txt():
    return _ads_txt_response([ADMOB_PUBLISHER_LINE])


def _ads_txt_response(more_lines):
    s = get_settings()
    lines = []
    client = s.get("adsense_client", "")
    if ADSENSE_CLIENT_RE.match(client):
        # Google's standard ads.txt line for AdSense publishers
        lines.append(f"google.com, {client.replace('ca-', '', 1)}, DIRECT, f08c47fec0942fa0")
    for line in (s.get("ads_txt_extra") or "").splitlines():
        line = line.strip()
        if line and len(line) < 300 and all(32 <= ord(c) < 127 for c in line):
            lines.append(line)
    lines += [m for m in more_lines if m not in lines]
    if not lines:
        lines.append("# No advertising partners configured yet.")
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


@bp.route("/robots.txt")
def robots():
    site = current_app.config["SITE_URL"]
    rules = ("Disallow: /admin\nDisallow: /account\nDisallow: /api/\nDisallow: /login\nDisallow: /signup\n"
             "Disallow: /forgot\nDisallow: /reset/\nDisallow: /search\nDisallow: /contact?*station=\nAllow: /\n")
    # Search and AI-answer crawlers are named on purpose (a named group must repeat the rules).
    bots = ["Googlebot", "Bingbot", "OAI-SearchBot", "ChatGPT-User", "GPTBot", "ClaudeBot", "Claude-SearchBot",
            "Claude-User", "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot", "Applebot-Extended",
            "DuckDuckBot", "YandexBot", "Amazonbot"]
    body = "".join(f"User-agent: {b}\n" for b in ("SemrushBot", "AhrefsBot", "MJ12bot", "DotBot", "BLEXBot", "DataForSeoBot")) + "Disallow: /\n\n"
    body += "User-agent: *\n" + rules + "\n"
    for b in bots:
        body += f"User-agent: {b}\n" + rules + "\n"
    body += f"Sitemap: {site}/sitemap.xml\n"
    from . import directory
    for n in directory.chunks():
        body += f"Sitemap: {site}/sitemap-stations-{n}.xml\n"
    return Response(body, mimetype="text/plain")


@bp.route("/live-news")
def live_news_page():
    meta = build_meta("Live News Radio — World, Pakistan, India & US News Online",
                      "Listen free to live news radio and see today's headlines: breaking news, politics, business, sports "
                      "and Bollywood, in Urdu, Hindi and English.",
                      canonical_path="/live-news")
    crumbs = [("Home", "/"), ("Live news", "/live-news")]
    topics = [("US news", "/country/usa"), ("Europe news", "/continent/europe"),
              ("Middle East news", "/continent/middle-east"), ("UK news", "/country/uk"), ("Germany", "/country/germany"),
              ("France", "/country/france"), ("Italy", "/country/italy"), ("Spain", "/country/spain"),
              ("Ukraine", "/country/ukraine"), ("Russia", "/country/russia"), ("Israel", "/country/israel"),
              ("Iran", "/country/iran"), ("Saudi Arabia", "/country/saudi-arabia"), ("UAE", "/country/uae"),
              ("Turkey", "/country/turkey"), ("Pakistan", "/country/pakistan"), ("India", "/country/india"),
              ("Canada", "/country/canada"), ("Australia", "/country/australia")]
    return render_template("live_news.html", meta=meta, topics=topics, faq=islam_data.LIVE_NEWS_FAQ,
                           trending=_trend_rows(trends.top(8)), ld=[breadcrumb_ld(crumbs), faq_ld(islam_data.LIVE_NEWS_FAQ)])


from .headlines import _SKIP as _ADULT_TOPIC  # noqa: E402  (one list of adult words for every headline and topic)
_TREND_PAGES = {}               # slug -> {term, kind, href, news, ts}: the pages of what people search right now (kept small, refreshed by the background thread)


def _trend_slug(term):
    return slugify(term, 60)


def _trend_save(term, kind, href, news):
    """Remember one trending topic's page (only real, family-safe headlines); the newest 150 topics stay."""
    slug = _trend_slug(term)
    news = [n for n in (news or []) if n.get("t") and not _ADULT_TOPIC.search(n["t"])]
    if len(news) < 2 or _ADULT_TOPIC.search(term):
        return None
    _TREND_PAGES[slug] = {"term": term, "kind": kind, "href": href, "news": [{"t": n["t"], "s": n.get("s", "")} for n in news[:8]], "ts": time.time()}
    if len(_TREND_PAGES) > 150:
        for old in sorted(_TREND_PAGES, key=lambda k: _TREND_PAGES[k]["ts"])[:len(_TREND_PAGES) - 150]:
            _TREND_PAGES.pop(old, None)
    radio.keep("keep:tr:" + slug, _TREND_PAGES[slug])
    radio.keep("keep:tr:index", [[k, v["term"]] for k, v in _TREND_PAGES.items()])
    return slug


def _trend_page_data(slug):
    """What a visitor sees: the saved copy in memory, else the database copy; never the network."""
    hit = _TREND_PAGES.get(slug)
    if hit:
        return hit
    try:
        data = radio._peek("keep:tr:" + slug)
    except Exception:
        data = None
    if isinstance(data, dict) and data.get("news") and slug == _trend_slug(data.get("term", "")):
        _TREND_PAGES[slug] = data
        return data
    return None


def _trend_known():
    """[(slug, term)] of the saved trending pages, newest first (after a restart: from the database copy of the list)."""
    if not _TREND_PAGES:
        try:
            for slug, term in (radio._peek("keep:tr:index") or [])[:150]:
                _trend_page_data(slug)
        except Exception:
            pass
    return [(k, v["term"]) for k, v in sorted(_TREND_PAGES.items(), key=lambda kv: -kv[1]["ts"])]


_TREND_THREAD = {"pid": None}


def start_trend_pages(app):
    """Every 30 minutes, for each trending topic (all countries), read the newest public headlines and keep them as a page of its own.
    Started once per process: at start-up, and again by the first visitor of a worker (a thread made before the server forks its workers does not follow them)."""
    if app.config.get("TESTING") or app.config.get("RADIO_DEMO") or _TREND_THREAD["pid"] == os.getpid():
        return None
    _TREND_THREAD["pid"] = os.getpid()
    import time as _t
    from . import headlines, indexnow

    def run():
        _t.sleep(60)
        while True:
            fresh = []
            try:
                with app.app_context():
                    seen = set()
                    for c in trends.by_country():
                        for r in c["rows"]:
                            if r["term"].lower() in seen or len(seen) >= 80:
                                continue
                            seen.add(r["term"].lower())
                            if _ADULT_TOPIC.search(r["term"]):
                                continue
                            slug = _trend_slug(r["term"])
                            old = _TREND_PAGES.get(slug)
                            if old and _t.time() - old["ts"] < 1500:
                                continue
                            items = headlines.person_news(r["term"], exact=False)       # a match or a topic is never one exact phrase in a headline
                            if items is not None and _trend_save(r["term"], r["kind"], r["href"], items) and not old:
                                fresh.append("/trending/" + slug)
                            _t.sleep(3)
                    if fresh:
                        indexnow.send_pages(app, fresh[:50] + ["/trending"])
            except Exception:
                pass
            _t.sleep(1800 if _TREND_PAGES else 120)         # nothing yet (the trending list was not ready): look again soon
    t = threading.Thread(target=run, daemon=True, name="trend-pages")
    t.start()
    return t


def _trend_rows(rows):
    """The trending terms for a strip: a topic that has a page of its own opens it (and says so); the others keep their radio link."""
    try:
        start_trend_pages(current_app._get_current_object())
    except Exception:
        pass
    out = []
    for r in rows or []:
        slug = _trend_slug(r["term"])
        page = _trend_page_data(slug)
        out.append(dict(r, href="/trending/" + slug, action="Latest news") if page else r)
    return out


@bp.route("/trending/<slug>")
def trending_topic(slug):
    data = _trend_page_data(slug)
    if not data:
        abort(404)
    term, news = data["term"], data["news"]
    others = [(k, v) for k, v in _trend_known() if k != slug][:12]
    title = f"{term}: Latest News and Updates"
    meta = build_meta(title, f"What is happening with {term} right now: {news[0]['t']}. Updated automatically from public news feeds, with live radio to follow it.",
                      canonical_path=f"/trending/{slug}")
    faqs = [(f"What is the latest news about {term}?", f"The newest headline is \u201c{news[0]['t']}\u201d" + (f" ({news[0]['s']})" if news[0].get("s") else "") + ". This page refreshes by itself about every 30 minutes."),
            (f"Why is {term} trending?", f"{term} is one of the things many people are searching for right now. The headlines on this page show what is being reported about it today.")]
    crumbs = [("Home", "/"), ("Trending now", "/trending"), (term, f"/trending/{slug}")]
    return render_template("trend_topic.html", meta=meta, term=term, news=news, kind=data["kind"], href=data["href"], others=others, faqs=faqs,
                           updated=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(data["ts"])), ld=[breadcrumb_ld(crumbs), faq_items_ld(faqs)])


def _weather_start():
    try:
        weather.start(current_app._get_current_object(), radio.keep, radio._peek)
    except Exception:
        pass


def _weather_data(slug):
    """The saved weather of a city (memory, else the database copy); never the network."""
    hit = weather.get(slug)
    if not hit:
        try:
            weather.load_saved(radio._peek("keep:weather"))
        except Exception:
            pass
        hit = weather.get(slug)
    return hit


_JOBS = {"pid": None}


def _digest_collect():
    """(the newest trending topics with their first headline, the top world headlines) for the weekly message."""
    trending = [{"term": v["term"], "t": v["news"][0]["t"]} for v in sorted(_TREND_PAGES.values(), key=lambda v: -v["ts"])[:8]]
    world = (today_news.get()["sections"].get("World") or [])[:6]
    return trending, world


@bp.before_app_request
def _start_background_jobs():
    """The first request of every web process starts the automatic jobs (trending pages, weather, today's news, the weekly message):
    a thread made before the server forks its workers does not follow them."""
    if _JOBS["pid"] == os.getpid():
        return
    _JOBS["pid"] = os.getpid()
    try:
        app = current_app._get_current_object()
        start_trend_pages(app)
        start_people_check(app)
        weather.start(app, radio.keep, radio._peek)
        today_news.start(app, radio.keep, radio._peek)
        digest.start(app, _digest_collect)
    except Exception:
        pass


@bp.route("/unsubscribe/<token>", methods=["GET", "POST"])
def unsubscribe(token):
    db = get_db()
    done = False
    valid = digest.token_exists(db, token)
    if request.method == "POST" and valid:
        done = digest.stop_by_token(db, token)
        valid = False
    return render_template("unsubscribe.html", meta={"title": "Weekly message | Sur Music", "noindex": True}, done=done, valid=valid)


@bp.route("/today")
def todays_news():
    try:
        today_news.start(current_app._get_current_object(), radio.keep, radio._peek)
    except Exception:
        pass
    data = today_news.get()
    if not data["sections"]:
        try:
            today_news.load_saved(radio._peek("keep:today"))
        except Exception:
            pass
        data = today_news.get()
    ready = len(data["sections"]) >= 3
    first = next(iter(data["sections"].values()))[0]["t"] if ready else ""
    meta = build_meta("Today's News Headlines: World, Pakistan, India, Sports",
                      f"Today's top headlines from the world, Pakistan, India, the USA, the UK, business, technology and sport, refreshed automatically. Latest: {first}." if ready
                      else "Today's top headlines from the world, Pakistan, India, the USA, the UK, business, technology and sport, refreshed automatically.",
                      canonical_path="/today", noindex=not ready)
    crumbs = [("Home", "/"), ("Today's news", "/today")]
    return render_template("today.html", meta=meta, sections=data["sections"] if ready else {},
                           updated=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(data["t"])), ld=[breadcrumb_ld(crumbs)])


@bp.route("/weather")
def weather_index():
    _weather_start()
    groups, any_data = {}, False
    for name, country, key, _la, _lo in weather.CITIES:
        slug = slugify(name, 60)
        d = _weather_data(slug)
        any_data = any_data or bool(d)
        groups.setdefault(country, []).append({"slug": slug, "name": name, "temp": d["temp"] if d else None, "text": d["text"] if d else ""})
    meta = build_meta("Weather Today in Pakistan, India, UAE, UK, USA and More",
                      "Today's temperature and a 7-day forecast for Lahore, Karachi, Islamabad, Delhi, Mumbai, Dubai, Riyadh, London, New York and 60+ cities. Updated every 30 minutes, with live radio.",
                      canonical_path="/weather", noindex=not any_data)
    crumbs = [("Home", "/"), ("Weather", "/weather")]
    return render_template("weather_index.html", meta=meta, groups=groups, ld=[breadcrumb_ld(crumbs)])


@bp.route("/weather/<slug>")
def weather_city(slug):
    if not weather.valid_slug(slug):
        abort(404)
    _weather_start()
    city, country, key, _la, _lo = weather.BY_SLUG[slug]
    d = _weather_data(slug)
    if not d:
        resp = _preparing()
        resp.headers["Retry-After"] = "600"
        return resp
    today = d["days"][0]
    meta = build_meta(f"{city} Weather Today: Temperature & 7-Day Forecast",
                      f"{city}, {country} weather now: {d['temp']}°C and {d['text'].lower()}. Today {today['lo']}° to {today['hi']}°C. 7-day forecast, updated every 30 minutes, with live radio.",
                      canonical_path=f"/weather/{slug}")
    faqs = [(f"What is the weather in {city} today?", f"Right now it is {d['temp']}°C ({weather.f_from_c(d['temp'])}°F) in {city} with {d['text'].lower()}. Today's low is {today['lo']}°C and the high is {today['hi']}°C."),
            (f"Will it rain in {city} today?", f"The chance of rain today is {today['rain']}%." if today.get("rain") is not None else f"Check the 7-day forecast above for rain in {city}."),
            (f"How often is the {city} weather updated?", "This page is refreshed automatically about every 30 minutes.")]
    near = [x for x in weather.CITIES if x[1] == country and x[0] != city][:8]
    crumbs = [("Home", "/"), ("Weather", "/weather"), (city, f"/weather/{slug}")]
    radio_href = topic_path(key) if key in TOPICS else "/genre/news"
    return render_template("weather_city.html", meta=meta, city=city, country=country, d=d, faqs=faqs, near=[(slugify(x[0], 60), x[0]) for x in near],
                           radio_href=radio_href, f=weather.f_from_c, updated=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(d["t"])),
                           ld=[breadcrumb_ld(crumbs), faq_items_ld(faqs)])


@bp.route("/trending")
def trending_page():
    countries = trends.by_country()
    try:
        start_trend_pages(current_app._get_current_object())
    except Exception:
        pass
    for c in countries:                                    # a topic with a page of its own opens it; the radio link stays beside it
        for r in c["rows"]:
            r["page"] = "/trending/" + _trend_slug(r["term"]) if _trend_page_data(_trend_slug(r["term"])) else ""
    meta = build_meta("Trending Now: News, Elections, Cricket, Weather, Songs",
                      "What people in Pakistan, India, the UAE, Europe, the USA and more are searching for right now: "
                      "news, elections, war, weather, cricket, gold, songs and movies. Updated every 30 minutes.",
                      canonical_path="/trending", noindex=not countries)
    crumbs = [("Home", "/"), ("Trending now", "/trending")]
    return render_template("trending.html", meta=meta, countries=countries, updated=trends.updated_text(),
                           ld=[breadcrumb_ld(crumbs)])


@bp.route("/markets")
def markets_page():
    meta = build_meta("Gold Rate Today (Per Tola), Dollar Rate and Bitcoin Price",
                      "Gold rate today per tola and gram, silver rate, USD to PKR dollar rate, euro, pound, dirham and "
                      "riyal rates, and Bitcoin price, updated automatically. Plus live news radio.",
                      canonical_path="/markets")
    crumbs = [("Home", "/"), ("Markets", "/markets")]
    return render_template("markets.html", meta=meta, sections=markets.view(), faq=islam_data.MARKETS_FAQ,
                           year=datetime.now(timezone.utc).year,
                           ld=[breadcrumb_ld(crumbs), faq_ld(islam_data.MARKETS_FAQ)])


@bp.route("/api/markets")
def api_markets():
    resp = jsonify(markets.api_payload())
    resp.headers["Cache-Control"] = "public, max-age=30"
    return resp


@bp.route("/islam")
def islam_page():
    meta = build_meta("Islamic Radio Live: Quran, Naat, Qawwali and Famous Qaris",
                      "Listen free to live Quran recitation, Naat Sharif, hamd and qawwali. Famous qaris, naat khwans "
                      "and qawwali artists, Islamic radio by country, and answers to common questions.",
                      canonical_path="/islam")
    crumbs = [("Home", "/"), ("Islam", "/islam")]
    return render_template("islam.html", meta=meta, qaris=islam_data.QARIS, naats=islam_data.NAAT_KHWANS,
                           qawwals=islam_data.QAWWALS, titles=islam_data.TITLES, countries=islam_data.COUNTRIES,
                           faq=islam_data.ISLAM_FAQ, ld=[breadcrumb_ld(crumbs), faq_ld(islam_data.ISLAM_FAQ)])


@bp.route("/blog")
def blog_index():
    meta = build_meta("Radio Guides and Articles — Quran, Naat, Qawwali, Help",
                      "Practical guides from Sur Music: how to listen to Quran radio, find your home country's "
                      "stations from abroad, use radio with a screen reader, and fix stopping streams.",
                      canonical_path="/blog")
    crumbs = [("Home", "/"), ("Guides", "/blog")]
    return render_template("blog.html", meta=meta, posts=blog_data.posts_sorted(), crumbs=crumbs,
                           ld=[breadcrumb_ld(crumbs)])


@bp.route("/blog/<slug>")
def blog_post(slug):
    post = blog_data.BY_SLUG.get(slug)
    if not post:
        abort(404)
    meta = build_meta(post["title"], post["description"], canonical_path=f"/blog/{slug}")
    crumbs = [("Home", "/"), ("Guides", "/blog"), (post["title"], f"/blog/{slug}")]
    return render_template("blog_post.html", meta=meta, post=post, related=blog_data.related(slug), crumbs=crumbs,
                           author=blog_data.AUTHOR,
                           ld=[breadcrumb_ld(crumbs), article_ld(post, blog_data.AUTHOR)])


@bp.route("/llms.txt")
def llms_txt():
    """A plain-text summary of the site for AI assistants and answer engines (llms.txt)."""
    site = current_app.config["SITE_URL"]
    s = get_settings()
    types = [(k, v) for k, v in GENRE_PAGES.items() if not radio.known_empty(k) and _page_exists(k)][:40]
    big = ["pakistan", "india", "usa", "uk", "uae", "saudi-arabia", "canada", "australia", "germany", "france", "turkey",
           "bangladesh", "afghanistan", "qatar", "oman"]
    body = (f"# {s['site_full_name']}\n\n"
            "> Free online radio in the browser: thousands of live stations from more than 200 countries, including "
            "Quran, Naat, Qawwali, Ghazal, news, Bollywood, Lollywood and English hits. Works on any phone or "
            "computer, with screen readers. An Android app (free with ads, Pro without ads) is also available.\n\n"
            f"Made by {s['owner_name']}. Website: {site}\n\n"
            "## Facts for answers\n"
            "- Listening on the website is free. Stations are public internet radio streams; Sur Music does not own them.\n"
            "- Each station has its own page with details and a play button: /station/<id>/<name>.\n"
            "- Station lists update through the day.\n"
            "- Android app: free with ads; Sur Music Pro (no ads, all themes) is US$5 per year after a free trial.\n\n"
            "## Main pages\n"
            f"- [All radio stations by country and type]({site}/radio-stations)\n"
            f"- [Islam: Quran, Naat and Qawwali]({site}/islam)\n"
            f"- [Live news radio: world, Pakistan, India, US news and sports]({site}/live-news)\n"
            f"- [Trending searches now]({site}/trending)\n"
            f"- [Gold, Bitcoin and dollar rates]({site}/markets)\n"
            f"- [Guides and articles]({site}/blog)\n"
            f"- [Android app and Chrome extension]({site}/download)\n"
            f"- [Top 100 most listened stations]({site}/top-100)\n"
            f"- [Pakistan FM radio by frequency and city]({site}/pakistan-fm-radio)\n"
            f"- [Free podcasts: Urdu, Islamic scholars, Hindi, cricket, news]({site}/podcasts)\n"
            f"- [A-Z station directory]({site}/stations/a)\n"
            f"- [Accessibility: radio for blind and low-vision listeners (TalkBack, VoiceOver, NVDA, JAWS)]({site}/accessibility)\n"
            f"- [About]({site}/about)\n"
            f"- [Sitemap]({site}/sitemap.xml)\n\n"
            "## Radio by type\n")
    for k, v in types:
        body += f"- [{v['label']} radio]({site}{topic_path(k)})\n"
    body += "\n## Radio by country\n"
    for k in big:
        if k in COUNTRY_PAGES:
            body += f"- [{COUNTRY_PAGES[k]['label']} radio]({site}{topic_path(k)})\n"
    from .topics import PROVINCE_SLUGS
    body += "\n## Radio by province and state\n"
    for k in PROVINCE_SLUGS:
        body += f"- [{TOPICS[k]['label']} radio]({site}{topic_path(k)})\n"
    try:
        popular = [x for x in without_blocked(radio.known_stations()) if x.get("name")]
    except Exception:              # the list is a bonus; never break the file
        popular = []
    popular.sort(key=lambda x: -(x.get("clicks") or 0))
    if popular:
        body += "\n## Popular stations (listen live free)\n"
        seen = set()
        for st in popular:
            if st["uuid"] in seen:
                continue
            seen.add(st["uuid"])
            body += f"- [{st['name']} live]({site}{station_path(st)})" + (f" - {st['country']}" if st.get("country") else "") + "\n"
            if len(seen) >= 40:
                break
    return Response(body, mimetype="text/plain; charset=utf-8")


@bp.route("/sitemap.xml")
def sitemap():
    from . import lowdb
    if lowdb.enabled():
        hit, xml = lowdb.cache_get("sitemap")
        if hit:
            return Response(xml, mimetype="application/xml")
    site = current_app.config["SITE_URL"]
    pages = ["/", "/bollywood", "/lollywood", "/hollywood", "/download", "/donate", "/about", "/contact", "/faq",
             "/privacy", "/terms", "/disclaimer", "/donation-disclaimer", "/cookies"]
    pages += ["/for-stations", "/radio-stations", "/top-100", "/pakistan-fm-radio", "/podcasts", "/accessibility", "/my-music", "/reviews", "/islam", "/markets", "/live-news", "/blog"] + (["/voices"] if _FOUND else []) + (["/trending"] if trends.by_country() else []) + [f"/trending/{k}" for k, _ in _trend_known()] + (["/weather"] + [f"/weather/{k}" for k in weather.saved_copy()] if weather.saved_copy() else []) + (["/today"] if len(today_news.get()["sections"]) >= 3 else []) + [f"/blog/{p['slug']}" for p in blog_data.POSTS] + [f"/continent/{c}" for c in CONTINENTS]
    pages += [topic_path(k) for _, items in _listed_types() for k, _ in items]
    pages += [topic_path(k) for c in CONTINENTS for k, _, _ in _listed_countries(c)] + ["/deals"]
    from . import podcasts as _pod
    pages += [f"/podcasts/c/{k}" for k in _pod.CATEGORIES]
    seen, thin = set(), set()
    keys = {"cat:" + c for c in radio.CATEGORIES} | {"genre:" + g for g in radio.LISTED_GENRES}
    db = get_db()
    for key_row in db.all("SELECT cache_key FROM station_cache"):             # one list at a time: low memory
        if key_row["cache_key"] not in keys:
            continue
        row = db.one("SELECT body FROM station_cache WHERE cache_key = ?", (key_row["cache_key"],))
        try:
            stations = json.loads(row["body"]) or []
        except (ValueError, TypeError):
            continue
        gslug = key_row["cache_key"][6:] if key_row["cache_key"].startswith("genre:") else ""
        if (TOPICS.get(gslug) or {}).get("group") in _THIN_GROUPS and len(without_blocked(stations)) < THIN_LIST:
            thin.add(topic_path(gslug))
        if gslug in COUNTRY_PAGES:                                    # a page for each region/city with enough stations
            pages += [f"{topic_path(gslug)}/{slugify(n)}" for n, c in _state_counts(without_blocked(stations), top=1000)
                      if c >= REGION_PAGE_MIN and slugify(n) != "item"]
        for st in without_blocked(stations):
            if isinstance(st, dict) and st.get("uuid") and st["uuid"] not in seen and len(seen) < 45000 \
                    and strong_station(st):
                seen.add(st["uuid"])
                pages.append(station_path(st))
    pages = [p for p in pages if p not in thin]
    for k, t in TOPICS.items():                                   # a person's page counts only when it has real content (a podcast or talk, or real headlines)
        if t.get("people"):
            try:
                if _person_shows(k, remember=False) or _person_news(k, wait=False):   # a podcast or real headlines
                    pages.append(topic_path(k))
            except Exception:
                pass
    from . import podcasts as _pods
    for _t, rows in list(_pods._cat.values()):                    # every podcast show page the site lists
        for r in rows or []:
            if r.get("id") and len(pages) < 45000:
                pages.append(f"/podcasts/{r['id']}")
    from . import directory as _dir
    known_first = {(x.get("name") or "?").strip()[:1].lower() for x in radio.known_stations()}
    for c in "0" + LETTERS:                                       # an A–Z page only when it has stations (an empty one is noindex)
        if _dir.by_letter(c, limit=1)[1] or (c in known_first if c != "0" else any(
                k not in LETTERS for k in known_first)):
            pages.append(f"/stations/{c}")
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    post_dates = {f"/blog/{bp['slug']}": bp.get("date") for bp in blog_data.POSTS}    # real publish dates only
    pages = list(dict.fromkeys(pages))                            # each page once (a repeated link confuses search engines)
    for p in pages:
        day = post_dates.get(p)
        parts.append(f"<url><loc>{escape(site + p)}</loc>" + (f"<lastmod>{escape(day)}</lastmod>" if day else "") + "</url>")
    parts.append("</urlset>")
    xml = "\n".join(parts)
    if lowdb.enabled():
        lowdb.cache_set("sitemap", xml, 3600)
    return Response(xml, mimetype="application/xml")


@bp.route("/sitemap-stations-<int:n>.xml")
def sitemap_stations(n):
    """One chunk of the world station directory (see directory.py): a real page for every station."""
    from . import lowdb
    if lowdb.enabled():
        hit, xml = lowdb.cache_get(f"sitemap-dir:{n}")
        if hit:
            return Response(xml, mimetype="application/xml")
    from . import directory
    stations = directory.chunk_stations(n)
    if not stations:
        abort(404)
    site = current_app.config["SITE_URL"]
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for st in without_blocked(stations):
        if isinstance(st, dict) and st.get("uuid") and strong_station(st):
            parts.append(f"<url><loc>{escape(site + station_path(st))}</loc></url>")
    parts.append("</urlset>")
    xml = "\n".join(parts)
    if lowdb.enabled():
        lowdb.cache_set(f"sitemap-dir:{n}", xml, 6 * 3600)
    return Response(xml, mimetype="application/xml")


@bp.route("/ping")
def ping():
    """Tiny check for uptime monitors and the host's health check; does not wake the database."""
    return "ok", 200, {"Content-Type": "text/plain", "Cache-Control": "no-store"}


@bp.route("/healthz")
def healthz():
    import os
    import tempfile
    checks = {}
    try:
        get_db().scalar("SELECT 1")
        checks["database"] = "ok"
    except Exception:  # pragma: no cover
        checks["database"] = "error"
    try:
        with tempfile.NamedTemporaryFile(dir=os.path.join(current_app.config["STORAGE_DIR"], "files"),
                                         prefix=".health-"):
            pass
        checks["storage"] = "ok"
    except OSError:
        checks["storage"] = "error"
    ok = all(v == "ok" for v in checks.values())
    info = {}
    try:                                       # facts for checking a deploy (no secrets)
        from . import directory, persist
        info = {"stations": directory.count(), "permanent_disk": bool(current_app.config.get("STORAGE_PERSISTENT")),
                "data_backup": persist.status()["where"] or False, "data_backup_last_ok": persist.status()["last_ok"],
                "restore_at_start": current_app.config.get("DATA_RESTORE", "")}
    except Exception:  # pragma: no cover
        pass
    return {"status": "ok" if ok else "error", "checks": checks, "info": info}, (200 if ok else 503)


@bp.route("/menu/<any(country, types, flags):which>")
def header_menu(which):
    """The long header drop-downs (hundreds of links) are sent only when someone opens them, and then kept by the
    browser for a day, instead of riding along with every page (about 40% of each page before)."""
    from . import lowdb
    key = f"menu:{which}"
    hit, html = lowdb.cache_get(key) if lowdb.enabled() else (False, None)
    if not hit:
        html = render_template(f"menus/{which}.html")
        if lowdb.enabled():
            lowdb.cache_set(key, html, 6 * 3600)
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = "public, max-age=86400"
    resp.headers["X-Robots-Tag"] = "noindex"
    return resp


@bp.route("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="img/favicon-32.png"), code=301)


@bp.app_template_global()
def media_src(name):
    return media_url(name)


@bp.app_template_global()
def station_json(st):
    return json.dumps(st, ensure_ascii=False)


@bp.app_template_global()
def listen_locked():
    return gate_active() and current_user() is None


@bp.app_template_global()
def thumb_class(name):
    h = 0
    for ch in name or "":
        h = (h * 31 + ord(ch)) % 360
    return f"c{h % 7}"


@bp.app_template_global()
def ad_slot_id(name):
    """Return the AdSense slot ID for a placement, or '' if ads are off / slot not set."""
    if not ads_active():
        return ""
    if name == "player" and get_settings().get("ads_player_enabled") != "1":
        return ""                         # the big player's ad has its own switch, off until the owner turns it on
    return get_settings().get(f"ad_slot_{name}", "")
