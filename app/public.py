"""Public pages, the station JSON API, favourites, downloads and infrastructure routes."""
import json
import re
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
from .seo import (absolute, article_ld, breadcrumb_ld, build_meta, collection_ld, faq_items_ld, faq_ld, topic_keywords, media_url, organization_ld, page_ld, station_ld, webapp_ld, android_app_ld,
                  website_ld)
from .settings import (ADSENSE_CLIENT_RE, ads_active, affiliate_offers, donation_method, get_settings, is_blocked,
                       offers_for, sponsored_stations, without_blocked)
from .storage import file_path, media_bytes, media_path, software_mime
from .util import valid_email, valid_url

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


from .topics import CONTINENTS, COUNTRY_PAGES, GENRE_PAGES, TOPICS, countries_in, grouped, topic_path  # noqa: E402


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
    ("health", "🩺", "Health and calm", ["health", "meditation"]),
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
                      if k not in placed and not radio.known_empty(k))
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
    if not isinstance(st, dict) or st.get("sponsored") or not st.get("uuid"):
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
    return [(topic_path(k), TOPICS[k]["label"], TOPICS[k].get("code")) for k in _FLAG_FIRST if k in TOPICS]


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
            ("Accessibility", "/accessibility")]
    return countries, languages, cats


@bp.route("/")
def home():
    stations, error = _stations_for("bollywood")
    meta = build_meta(page="home", canonical_path="/")
    return render_template("home.html", meta=meta, stations=protect(stations[:60]), error=error, cat="bollywood",
                           popular=_popular(), home_faq=islam_data.HOME_FAQ, market_sections=markets.view(),
                           guides=blog_data.posts_sorted()[:3],
                           filters=_home_filters(),
                           trending=trends.top(6),
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


def _topic_page(slug):
    info = TOPICS[slug]
    try:
        stations, error = without_blocked(radio.genre_stations(slug)), None
    except radio.RadioError as exc:
        stations, error = [], str(exc)
    total = len(stations)
    all_stations = stations
    stations, page_no, pages = _paginate(stations)
    meta = build_meta(info["seo_title"], info["description"], page=f"genre-{slug}",
                      noindex=(not stations) or page_no > 1)      # an empty page (or page 2, 3 …) is not shown in Google
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
    crumbs = [("Home", "/"), ("All radio", "/radio-stations")]
    if info["kind"] == "country" and info["group"] in CONTINENTS:
        crumbs.append((CONTINENTS[info["group"]][0], f"/continent/{info['group']}"))
    crumbs.append((info["h1"].split(" — ")[0], topic_path(slug)))
    trending = trends.top(8) if slug in ("sports", "news", "english-news", "talk", "pop") else []
    ld = [breadcrumb_ld(crumbs), collection_ld(info["h1"], info["description"], topic_path(slug), all_stations)]
    if page_no == 1 and faqs:
        ld.append(faq_items_ld(faqs))
    return render_template("category.html", meta=meta, stations=protect(stations), error=error, cat=slug,
                           info=info, genre=slug, crumbs=crumbs, ld=ld, trending=trending, faqs=faqs if page_no == 1 else [], popular=popular if page_no == 1 else [],
                           total=total, page_no=page_no, pages=pages, page_base=request.path)


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


@bp.route("/og/station/<uuid>.png")
def station_card(uuid):
    """Share picture of one station (shown next to the link in WhatsApp, Facebook, …)."""
    from . import ogcard
    if not ogcard.UUID_RE.match(uuid):
        abort(404)
    st, _key = radio.station_by_uuid(uuid)
    if not st or is_blocked(st):
        abort(404)
    png = ogcard.render((st.get("name") or "Radio").strip()[:90], (st.get("country") or "").strip()[:40])
    return Response(png, mimetype="image/png", headers={"Cache-Control": "public, max-age=86400"})


@bp.route("/station/<uuid>")
@bp.route("/station/<uuid>/<slug>")
def station_page(uuid, slug=None):
    """Each station's own page: play button, details, similar stations and ads."""
    st, key = radio.station_by_uuid(uuid)
    if not st:
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
    desc = (f"Listen to {st['name']} live online free on Sur Music. A radio station from {place} playing {tags}. "
            "No download, no sign-up — press play.")
    meta = build_meta(title, desc, canonical_path=want)
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
        ("Worldwide votes", f"{st['votes']:,} on the Radio Browser directory" if st.get("votes") else ""),
    ] if value]
    likes, dislikes = like_counts(st["uuid"])
    return render_template("station.html", meta=meta, st=protect([st])[0], similar=protect(similar), cat=key or "", faqs=faqs,
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


@bp.route("/api/headlines")
def api_headlines():
    """Headlines for the news strip: the visitor's own country (English edition), refreshed by itself."""
    from . import headlines
    if current_app.config.get("TESTING") or current_app.config.get("RADIO_DEMO"):
        items = []
    else:
        items = headlines.get(visitor_country())
    resp = jsonify({"items": items})
    resp.headers["Cache-Control"] = "private, max-age=120"
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


@bp.route("/ads.txt")
@bp.route("/app-ads.txt")                # the same publisher lines authorise the Android app's AdMob ads
def ads_txt():
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
    if not lines:
        lines.append("# No advertising partners configured yet.")
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


@bp.route("/robots.txt")
def robots():
    site = current_app.config["SITE_URL"]
    rules = ("Disallow: /admin\nDisallow: /account\nDisallow: /api/\nDisallow: /login\nDisallow: /signup\n"
             "Disallow: /forgot\nDisallow: /reset/\nDisallow: /search\nAllow: /\n")
    # Search and AI-answer crawlers are named on purpose (a named group must repeat the rules).
    bots = ["Googlebot", "Bingbot", "OAI-SearchBot", "ChatGPT-User", "GPTBot", "ClaudeBot", "Claude-SearchBot",
            "Claude-User", "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot", "Applebot-Extended",
            "DuckDuckBot", "YandexBot", "Amazonbot"]
    body = "User-agent: *\n" + rules + "\n"
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
                           trending=trends.top(8), ld=[breadcrumb_ld(crumbs), faq_ld(islam_data.LIVE_NEWS_FAQ)])


@bp.route("/trending")
def trending_page():
    countries = trends.by_country()
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
    types = [(k, v) for k, v in GENRE_PAGES.items() if not radio.known_empty(k)][:40]
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
            "- Station lists come from the open Radio Browser directory and update through the day.\n"
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
    pages += ["/for-stations", "/radio-stations", "/top-100", "/pakistan-fm-radio", "/accessibility", "/reviews", "/islam", "/markets", "/live-news", "/blog"] + (["/trending"] if trends.by_country() else []) + [f"/blog/{p['slug']}" for p in blog_data.POSTS] + [f"/continent/{c}" for c in CONTINENTS]
    pages += [topic_path(k) for _, items in _listed_types() for k, _ in items]
    pages += [topic_path(k) for c in CONTINENTS for k, _, _ in _listed_countries(c)] + ["/deals"]
    seen = set()
    keys = {"cat:" + c for c in radio.CATEGORIES} | {"genre:" + g for g in radio.GENRES}
    db = get_db()
    for key_row in db.all("SELECT cache_key FROM station_cache"):             # one list at a time: low memory
        if key_row["cache_key"] not in keys:
            continue
        row = db.one("SELECT body FROM station_cache WHERE cache_key = ?", (key_row["cache_key"],))
        try:
            stations = json.loads(row["body"]) or []
        except (ValueError, TypeError):
            continue
        for st in without_blocked(stations):
            if isinstance(st, dict) and st.get("uuid") and st["uuid"] not in seen and len(seen) < 45000:
                seen.add(st["uuid"])
                pages.append(station_path(st))
    pages += [f"/stations/{c}" for c in "0" + LETTERS]
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in pages:
        parts.append(f"<url><loc>{escape(site + p)}</loc></url>")
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
        if isinstance(st, dict) and st.get("uuid"):
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
