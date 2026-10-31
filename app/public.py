"""Public pages, the station JSON API, favourites, downloads and infrastructure routes."""
import json
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

from flask import (Blueprint, Response, abort, current_app, flash, g, jsonify, redirect, render_template,
                   request, send_file, session, url_for)

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from . import analytics, radio
from .db import get_db, utcnow
from .mailer import send_mail
from .security import current_user, ip_hash, rate_limited
from .seo import (breadcrumb_ld, build_meta, faq_ld, media_url, organization_ld, page_ld, station_ld, webapp_ld,
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
        "intro": "Tune in to the best live Bollywood radio stations, all in one place. From the golden voices of Lata Mangeshkar and Kishore Kumar to today's chart-toppers, these stations play Hindi film music around the clock — romantic songs, dance numbers, 90s classics and devotional music. Pick a station, press play, and keep browsing: the music keeps going.",
    },
    "lollywood": {
        "h1": "Lollywood & Pakistani Radio — Urdu, Punjabi, Ghazal & Qawwali",
        "seo_title": "Pakistani Radio Live — Urdu Songs, Ghazal & Qawwali",
        "description": "Listen to live Pakistani radio free: Lollywood film songs, Urdu pop, Punjabi music, ghazals, qawwali and FM stations from Pakistan.",
        "intro": "Listen to live Pakistani radio from Lahore, Karachi, Islamabad and beyond. These stations play Lollywood film songs, Urdu and Punjabi pop, timeless ghazals, Sufi music and qawwali, plus news and talk from FM stations across Pakistan. Wherever you are in the world, stay connected to the sound of home.",
    },
    "hollywood": {
        "h1": "Hollywood & English Hits Radio — Top 40, Pop & Soundtracks",
        "seo_title": "English Radio Live — Top 40 Hits & Pop Online",
        "description": "Listen to live English radio free: Top 40 hits, pop, 80s and 90s classics and Hollywood movie soundtracks from stations worldwide.",
        "intro": "Enjoy live English music radio: Top 40 chart hits, pop and dance, timeless 80s and 90s classics, and Hollywood movie soundtracks from stations around the world. Perfect for work, study, workouts and long drives — free, with no download and no sign-up needed.",
    },
}


from .topics import CONTINENTS, COUNTRY_PAGES, GENRE_PAGES, TOPICS, countries_in, grouped, topic_path  # noqa: E402


def station_path(st):
    """Address of a station's own page, e.g. /station/9617a9-…/geo-fm-100."""
    import re as _re
    slug = _re.sub(r"[^a-z0-9]+", "-", (st.get("name") or "station").lower()).strip("-")[:60] or "station"
    return f"/station/{st['uuid']}/{slug}"


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


@bp.app_template_global("chips_here")
def _chips_here():
    from .topics import chips_for
    return chips_for(visitor_country())


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
    rows = get_db().all("SELECT station_name, MAX(station_uuid) AS station_uuid, MAX(category) AS category, "
                        "COUNT(*) AS n FROM plays WHERE created_at > ? GROUP BY station_name "
                        "ORDER BY n DESC LIMIT ?", (since, limit + 5))
    import re as _re
    out = []
    for r in rows:
        r = dict(r)
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

@bp.route("/")
def home():
    stations, error = _stations_for("bollywood")
    meta = build_meta(page="home", canonical_path="/")
    return render_template("home.html", meta=meta, stations=protect(stations[:60]), error=error, cat="bollywood",
                           popular=_popular(), ld=[website_ld(), webapp_ld(), organization_ld()])


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


def _topic_page(slug):
    info = TOPICS[slug]
    try:
        stations, error = without_blocked(radio.genre_stations(slug)), None
    except radio.RadioError as exc:
        stations, error = [], str(exc)
    meta = build_meta(info["seo_title"], info["description"], page=f"genre-{slug}",
                      noindex=not stations)               # an empty page is not shown in Google
    crumbs = [("Home", "/"), ("All radio", "/radio-stations")]
    if info["kind"] == "country" and info["group"] in CONTINENTS:
        crumbs.append((CONTINENTS[info["group"]][0], f"/continent/{info['group']}"))
    crumbs.append((info["h1"].split(" — ")[0], topic_path(slug)))
    return render_template("category.html", meta=meta, stations=protect(stations), error=error, cat=slug,
                           info=info, genre=slug, crumbs=crumbs, ld=[breadcrumb_ld(crumbs)])


def _listed_countries(continent, minimum=3):
    """Countries of one continent that really have stations (all of them if the counts are not known)."""
    counts = radio.country_counts()
    out = []
    for slug, t in countries_in(continent):
        n = counts.get(t.get("code", ""), 0) if counts is not None else None
        if n is None or n >= minimum:
            out.append((slug, t, n))
    return out


def _listed_types():
    return [(g, [(k, v) for k, v in items if not radio.known_empty(k)]) for g, items in grouped()]


@bp.route("/accessibility")
def accessibility():
    """How blind and low-vision listeners use Sur Music (screen readers, keyboard)."""
    meta = build_meta("Accessible Radio for Blind & Low-Vision Listeners — Screen Reader Friendly",
                      "Sur Music works with screen readers (TalkBack, VoiceOver, NVDA, JAWS) and the keyboard: "
                      "spoken station names, simple shortcuts and thousands of live radio stations.",
                      page="accessibility")
    return render_template("accessibility.html", meta=meta,
                           ld=[breadcrumb_ld([("Home", "/"), ("Accessibility", "/accessibility")])])


@bp.route("/radio-stations")
def all_topics():
    """One page that links to every type, continent and country — helps visitors and Google find them all."""
    meta = build_meta("All Radio Stations — World Radio by Country, Naat, Quran, News & Music",
                      "Live radio from every continent: Europe, America, Africa, Asia, the Middle East and Oceania, "
                      "plus Naat, Quran, qawwali, news, pop, rock, jazz and more — free in your browser.",
                      page="radio-stations")
    world = [(c, CONTINENTS[c][0], _listed_countries(c)) for c in CONTINENTS]
    return render_template("topics.html", meta=meta, groups=_listed_types(), world=world, topic_path=topic_path,
                           ld=[breadcrumb_ld([("Home", "/"), ("All radio", "/radio-stations")])])


@bp.route("/continent/<slug>")
def continent(slug):
    """Radio from one continent: a list of its countries."""
    if slug not in CONTINENTS:
        abort(404)
    name, adjective = CONTINENTS[slug]
    items = _listed_countries(slug)
    meta = build_meta(f"{name} Radio Stations Live — {adjective} Radio by Country",
                      f"Listen to live {adjective} radio free: choose a country in {name} and play its music, news "
                      "and talk stations in your browser.", page=f"continent-{slug}", noindex=not items)
    crumbs = [("Home", "/"), ("All radio", "/radio-stations"), (name, f"/continent/{slug}")]
    return render_template("continent.html", meta=meta, name=name, adjective=adjective, items=items,
                           topic_path=topic_path, crumbs=crumbs, ld=[breadcrumb_ld(crumbs)])


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
    ld = [breadcrumb_ld(crumbs), station_ld(st, want)]
    return render_template("station.html", meta=meta, st=protect([st])[0], similar=protect(similar), cat=key or "",
                           back=back, back_href=back_href, crumbs=crumbs, ld=ld)


@bp.app_template_global("offers_for")
def _offers_for(place, limit=3):
    return offers_for(place, limit)


@bp.route("/deals")
def deals():
    items = affiliate_offers(True) if get_settings().get("affiliate_enabled") == "1" else []
    meta = build_meta("Deals & recommendations — headphones, speakers and more",
                      "Hand-picked headphones, speakers and gadgets for better listening. Affiliate links.", page="deals")
    return render_template("deals.html", meta=meta, items=items)


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
                      "Sur Music for Android (US$5 one-time on Google Play) and the Chrome extension (7-day free "
                      "trial, then US$1/month): background play, lock-screen controls and favourites.", page="download")
    return render_template("download.html", meta=meta, apps=apps,
                           ld=[breadcrumb_ld([("Home", "/"), ("Download", "/download")])])


@bp.route("/download/<any(android, chrome):platform>")
def download_file(platform):
    app_row = get_db().one("SELECT * FROM apps WHERE platform = ?", (platform,))
    if not app_row:
        abort(404)
    # Apps are sold through Google Play / the Chrome Web Store: no free file download from the website.
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
    if removal:
        station = " ".join((request.args.get("station") or "").split())[:100]
        form["subject"] = ("Station removal request: " + station) if station else "Station removal request"
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
    return _policy("terms_md", "terms", "Terms of Use", "The terms for using Sur Music: free listening, accounts, acceptable use, third-party radio streams, apps and donations.")


@bp.route("/disclaimer")
def disclaimer():
    return _policy("disclaimer_md", "disclaimer", "Disclaimer", "Sur Music plays public live radio streams from stations around the "
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


@bp.route("/ads.txt")
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
    body = ("User-agent: *\nDisallow: /admin\nDisallow: /account\nDisallow: /api/\nDisallow: /login\n"
            "Disallow: /signup\nDisallow: /forgot\nDisallow: /reset/\nDisallow: /search\nAllow: /\n\n"
            f"Sitemap: {site}/sitemap.xml\n")
    return Response(body, mimetype="text/plain")


@bp.route("/llms.txt")
def llms_txt():
    """A short plain-text summary of the site for AI assistants and search tools."""
    site = current_app.config["SITE_URL"]
    s = get_settings()
    body = (f"# {s['site_full_name']}\n\n"
            "> Free online radio: live stations from more than 200 countries, including Quran, Naat, Qawwali, "
            "news, Bollywood, Lollywood and English hits. No app and no sign-up. Works in any browser and with "
            "screen readers.\n\n"
            f"Made by {s['owner_name']}.\n\n"
            "## Main pages\n"
            f"- [All radio stations by country and type]({site}/radio-stations)\n"
            f"- [Bollywood radio]({site}/bollywood)\n"
            f"- [Pakistani radio]({site}/lollywood)\n"
            f"- [English radio]({site}/hollywood)\n"
            f"- [Quran radio]({site}/genre/quran)\n"
            f"- [Naat radio]({site}/genre/naat)\n"
            f"- [Accessibility]({site}/accessibility)\n"
            f"- [About]({site}/about)\n"
            f"- [Sitemap]({site}/sitemap.xml)\n")
    return Response(body, mimetype="text/plain")


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
    pages += ["/radio-stations", "/accessibility"] + [f"/continent/{c}" for c in CONTINENTS]
    pages += [topic_path(k) for _, items in _listed_types() for k, _ in items]
    pages += [topic_path(k) for c in CONTINENTS for k, _, _ in _listed_countries(c)] + ["/deals"]
    seen = set()
    keys = {"cat:" + c for c in radio.CATEGORIES} | {"genre:" + g for g in radio.GENRES}
    for row in get_db().all("SELECT cache_key, body FROM station_cache"):    # one query for every saved list
        if row["cache_key"] not in keys:
            continue
        try:
            stations = json.loads(row["body"]) or []
        except ValueError:
            continue
        for st in without_blocked(stations):
            if isinstance(st, dict) and st.get("uuid") and st["uuid"] not in seen and len(seen) < 20000:
                seen.add(st["uuid"])
                pages.append(station_path(st))
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in pages:
        parts.append(f"<url><loc>{escape(site + p)}</loc></url>")
    parts.append("</urlset>")
    xml = "\n".join(parts)
    if lowdb.enabled():
        lowdb.cache_set("sitemap", xml, 3600)
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
    return {"status": "ok" if ok else "error", "checks": checks}, (200 if ok else 503)


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
    return get_settings().get(f"ad_slot_{name}", "")
