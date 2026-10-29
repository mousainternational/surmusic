"""Admin panel (role = admin only)."""
import json
from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, abort, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from . import analytics
from .backup import export_data, restore_data
from .db import get_db, utcnow
from .mailer import smtp_ready
from .security import admin_required, audit, purge_rate_limits
from .settings import (AD_SLOT_RE, ADSENSE_CLIENT_RE, BOOL_KEYS, DEFAULTS, PAGE_KEYS, donation_method, get_settings,
                       save_settings, setup_warnings, sponsored_stations)
from .storage import UploadError, delete_file, delete_media, save_image, save_software
from .util import clamp_int, valid_email, valid_url

bp = Blueprint("admin", __name__, url_prefix="/admin")
META = {"title": "Admin | Sur Music", "noindex": True}


def _since(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------- dashboard

@bp.route("/")
@admin_required
def dashboard():
    db = get_db()
    counts = {
        "users": db.scalar("SELECT COUNT(*) FROM users"),
        "users_7d": db.scalar("SELECT COUNT(*) FROM users WHERE created_at > ?", (_since(7),)),
        "plays_24h": db.scalar("SELECT COUNT(*) FROM plays WHERE created_at > ?", (_since(1),)),
        "plays_7d": db.scalar("SELECT COUNT(*) FROM plays WHERE created_at > ?", (_since(7),)),
        "favorites": db.scalar("SELECT COUNT(*) FROM favorites"),
        "unread": db.scalar("SELECT COUNT(*) FROM messages WHERE is_read = 0"),
        "downloads": db.scalar("SELECT COALESCE(SUM(download_count), 0) FROM apps"),
    }
    top = db.all("SELECT station_name, category, COUNT(*) AS n FROM plays WHERE created_at > ? "
                 "GROUP BY station_name, category ORDER BY n DESC LIMIT 10", (_since(7),))
    days = []
    today = datetime.now(timezone.utc).date()
    rows = db.all("SELECT SUBSTR(created_at, 1, 10) AS day, COUNT(*) AS n FROM plays WHERE created_at > ? "
                  "GROUP BY SUBSTR(created_at, 1, 10)", ((today - timedelta(days=14)).isoformat(),))
    by_day = {r["day"]: r["n"] for r in rows}
    for i in range(13, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        days.append({"day": d, "n": by_day.get(d, 0)})
    peak = max([d["n"] for d in days] + [1])
    purge_rate_limits()
    analytics.purge_old()
    live = analytics.live_now()
    today = analytics.summary(1)["totals"]
    return render_template("admin/dashboard.html", meta=META, counts=counts, top=top, days=days, peak=peak,
                           warnings=setup_warnings(smtp_ready()), live=live, today=today,
                           recent=analytics.recent(limit=12))


# ---------------------------------------------------------------- analytics

@bp.route("/analytics")
@admin_required
def analytics_page():
    days = clamp_int(request.args.get("days"), 1, 400, 7)
    return render_template("admin/analytics.html", meta=META, days=days, a=analytics.summary(days))


@bp.route("/live")
@admin_required
def live():
    return render_template("admin/live.html", meta=META, live=analytics.live_now())


@bp.route("/live.json")
@admin_required
def live_json():
    data = analytics.live_now()
    rows = []
    for r in data["listeners"]:
        rows.append({"user_id": r["user_id"], "who": (r["display_name"] or r["email"]) if r["user_id"] else "Guest",
                     "email": r["email"] or "", "station": r["station_name"], "category": r["category"],
                     "flag": r["flag"],
                     "place": ", ".join(x for x in (r["region"], r["country_name"] if r["country"] else "") if x)
                     or "Unknown",
                     "device": r["device"], "browser": r["browser"], "since": r["started_at"], "minutes": r["minutes"]})
    resp = jsonify({"listening": len(rows), "online": data["online"], "rows": rows})
    resp.headers["Cache-Control"] = "no-store"
    return resp


@bp.route("/activity")
@admin_required
def activity():
    kind = request.args.get("kind", "")
    page = clamp_int(request.args.get("page"), 1, 1000, 1)
    rows = analytics.recent(kind=kind or None, limit=100, offset=(page - 1) * 100)
    return render_template("admin/activity.html", meta=META, rows=rows, kind=kind, kinds=analytics.KINDS,
                           page=page)


@bp.route("/users/<int:uid>")
@admin_required
def user_detail(uid):
    db = get_db()
    u = db.one("SELECT * FROM users WHERE id = ?", (uid,))
    if not u:
        abort(404)
    stats = {
        "favorites": db.scalar("SELECT COUNT(*) FROM favorites WHERE user_id = ?", (uid,)),
        "plays": db.scalar("SELECT COUNT(*) FROM events WHERE user_id = ? AND kind = 'play'", (uid,)),
        "logins": db.scalar("SELECT COUNT(*) FROM events WHERE user_id = ? AND kind = 'login'", (uid,)),
        "minutes": analytics.listening_minutes(uid),
    }
    signup = db.one("SELECT country, region, device, browser, os, created_at FROM events "
                    "WHERE user_id = ? AND kind = 'signup' ORDER BY id LIMIT 1", (uid,))
    if signup:
        signup["flag"], signup["country_name"] = analytics.flag(signup["country"]), analytics.country_name(signup["country"])
    favs = [json.loads(r["station_json"])["name"] for r in
            db.all("SELECT station_json FROM favorites WHERE user_id = ? ORDER BY created_at DESC LIMIT 30", (uid,))]
    return render_template("admin/user_detail.html", meta=META, u=u, stats=stats, signup=signup, favs=favs,
                           rows=analytics.recent(user_id=uid, limit=200))


@bp.route("/cache/clear", methods=["POST"])
@admin_required
def cache_clear():
    db = get_db()
    db.execute("DELETE FROM station_cache")
    db.commit()
    audit("station_cache_clear")
    flash("Station lists will be refreshed from Radio Browser on the next visit.", "success")
    return redirect(url_for("admin.dashboard"))


# ---------------------------------------------------------------- users

@bp.route("/users")
@admin_required
def users():
    q = (request.args.get("q") or "").strip().lower()[:100]
    db = get_db()
    base = ("SELECT u.id, u.email, u.display_name, u.role, u.is_active, u.email_verified, u.created_at, "
            "u.last_login_at, (SELECT COUNT(*) FROM favorites f WHERE f.user_id = u.id) AS favs, "
            "(SELECT t.enabled FROM user_2fa t WHERE t.user_id = u.id) AS twofa FROM users u ")
    if q:
        rows = db.all(base + "WHERE LOWER(u.email) LIKE ? OR LOWER(u.display_name) LIKE ? "
                             "ORDER BY u.created_at DESC LIMIT 200", (f"%{q}%", f"%{q}%"))
    else:
        rows = db.all(base + "ORDER BY u.created_at DESC LIMIT 200")
    return render_template("admin/users.html", meta=META, rows=rows, q=q,
                           places=analytics.user_locations([r["id"] for r in rows]))


@bp.route("/users/<int:uid>/<any(suspend, activate, verify, signout, delete, reset_2fa):action>", methods=["POST"])
@admin_required
def user_action(uid, action):
    db = get_db()
    u = db.one("SELECT * FROM users WHERE id = ?", (uid,))
    if not u:
        abort(404)
    if u["role"] == "admin" and action in ("suspend", "delete"):
        flash("Administrator accounts cannot be suspended or deleted here.", "error")
        return redirect(url_for("admin.users"))
    if action == "suspend":
        db.execute("UPDATE users SET is_active = 0, session_version = session_version + 1 WHERE id = ?", (uid,))
    elif action == "activate":
        db.execute("UPDATE users SET is_active = 1, failed_attempts = 0, locked_until = NULL WHERE id = ?", (uid,))
    elif action == "verify":
        db.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (uid,))
    elif action == "signout":
        db.execute("UPDATE users SET session_version = session_version + 1 WHERE id = ?", (uid,))
    elif action == "reset_2fa":
        db.execute("DELETE FROM user_2fa WHERE user_id = ?", (uid,))
    elif action == "delete":
        db.execute("DELETE FROM favorites WHERE user_id = ?", (uid,))
        db.execute("DELETE FROM history WHERE user_id = ?", (uid,))
        db.execute("DELETE FROM live_sessions WHERE user_id = ?", (uid,))
        db.execute("UPDATE events SET user_id = NULL WHERE user_id = ?", (uid,))
        db.execute("DELETE FROM user_2fa WHERE user_id = ?", (uid,))
        db.execute("DELETE FROM users WHERE id = ?", (uid,))
    db.commit()
    audit(f"user_{action}", u["email"])
    flash(f"User {u['email']}: {action} done.", "success")
    return redirect(url_for("admin.users"))


# ---------------------------------------------------------------- messages

@bp.route("/messages")
@admin_required
def messages():
    return render_template("admin/messages.html", meta=META,
                           rows=get_db().all("SELECT * FROM messages ORDER BY created_at DESC LIMIT 500"))


@bp.route("/messages/<int:mid>")
@admin_required
def message_view(mid):
    db = get_db()
    m = db.one("SELECT * FROM messages WHERE id = ?", (mid,))
    if not m:
        abort(404)
    if not m["is_read"]:
        db.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (mid,))
        db.commit()
    return render_template("admin/message_view.html", meta=META, m=m)


@bp.route("/messages/<int:mid>/delete", methods=["POST"])
@admin_required
def message_delete(mid):
    db = get_db()
    db.execute("DELETE FROM messages WHERE id = ?", (mid,))
    db.commit()
    audit("message_delete", str(mid))
    flash("Message deleted.", "success")
    return redirect(url_for("admin.messages"))


# ---------------------------------------------------------------- settings

SECTIONS = {
    "general": ["site_name", "site_full_name", "owner_name", "owner_brand", "owner_url", "tagline", "hero_title",
                "hero_subtitle", "about_md", "contact_email", "support_url"],
    "accounts": ["play_requires_login", "signup_enabled", "require_email_verification"],
    "social": ["social_facebook", "social_youtube", "social_x", "social_instagram", "social_tiktok"],
    "seo": ["seo_default_title", "seo_default_description", "google_site_verification", "analytics_provider",
            "analytics_domain"],
    "policies": ["faq_md", "privacy_md", "terms_md", "disclaimer_md", "donation_disclaimer_md", "cookies_md",
                 "policies_updated"],
}
HTTPS_KEYS = {"owner_url", "support_url", "social_facebook", "social_youtube", "social_x", "social_instagram",
              "social_tiktok"}


@bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    section = request.args.get("section", "general")
    if section not in SECTIONS:
        section = "general"
    if request.method == "POST":
        values, errors = {}, []
        for key in SECTIONS[section]:
            if key in BOOL_KEYS or key in ("signup_enabled", "play_requires_login"):
                values[key] = "1" if request.form.get(key) else "0"
                continue
            val = (request.form.get(key) or "").strip()[:30000]
            if key in HTTPS_KEYS and val and not valid_url(val, https_only=True):
                errors.append(f"{key.replace('_', ' ').title()} must be an https:// link.")
            if key == "contact_email" and val and not valid_email(val):
                errors.append("Contact email is not a valid address (it must contain @ and a domain).")
            if key == "analytics_provider" and val not in ("none", "plausible"):
                val = "none"
            if key == "google_site_verification":
                val = "".join(ch for ch in val if ch.isalnum() or ch in "-_")[:100]
            values[key] = val
        if section == "seo":
            page_seo = {}
            for p in PAGE_KEYS:
                t = (request.form.get(f"page_{p}_title") or "").strip()[:70]
                d = (request.form.get(f"page_{p}_description") or "").strip()[:170]
                if t or d:
                    page_seo[p] = {"title": t, "description": d}
            values["page_seo"] = json.dumps(page_seo)
            og = request.files.get("seo_og_image")
            if og and og.filename:
                try:
                    old = get_settings().get("seo_og_image")
                    values["seo_og_image"] = save_image(og, "og")
                    delete_media(old)
                except UploadError as exc:
                    errors.append(str(exc))
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            save_settings(values)
            audit("settings_update", section)
            flash("Settings saved.", "success")
        return redirect(url_for("admin.settings", section=section))
    try:
        page_seo = json.loads(get_settings().get("page_seo") or "{}")
    except ValueError:
        page_seo = {}
    return render_template("admin/settings.html", meta=META, section=section, sections=SECTIONS,
                           page_keys=PAGE_KEYS, page_seo=page_seo, smtp=smtp_ready())


# ---------------------------------------------------------------- ads

@bp.route("/ads", methods=["GET", "POST"])
@admin_required
def ads():
    if request.method == "POST":
        errors = []
        client = (request.form.get("adsense_client") or "").strip()
        slots = {k: (request.form.get(k) or "").strip() for k in ("ad_slot_top", "ad_slot_list", "ad_slot_side",
                                                                  "ad_slot_footer")}
        extra = (request.form.get("ads_txt_extra") or "").strip()[:5000]
        enabled = "1" if request.form.get("ads_enabled") else "0"
        if client and not ADSENSE_CLIENT_RE.match(client):
            errors.append("Publisher ID must look like ca-pub-1234567890123456.")
        for k, v in slots.items():
            if v and not AD_SLOT_RE.match(v):
                errors.append(f"{k.replace('ad_slot_', '').title()} slot ID must be digits only (from AdSense).")
        if enabled == "1" and not client:
            errors.append("Enter your AdSense publisher ID before switching ads on.")
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            save_settings(dict(slots, adsense_client=client, ads_txt_extra=extra, ads_enabled=enabled))
            audit("ads_update", f"enabled={enabled}")
            flash("Ad settings saved.", "success")
        return redirect(url_for("admin.ads"))
    return render_template("admin/ads.html", meta=META)


# ---------------------------------------------------------------- donations

DONATION_KEYS = {
    "jazzcash": ["jazzcash_enabled", "jazzcash_verified", "jazzcash_holder", "jazzcash_number", "jazzcash_title",
                 "jazzcash_instructions"],
    "nayapay": ["nayapay_enabled", "nayapay_verified", "nayapay_holder", "nayapay_details", "nayapay_instructions"],
    "wise": ["wise_enabled", "wise_verified", "wise_holder", "wise_link", "wise_details", "wise_currencies",
             "wise_instructions", "wise_fee_note"],
    "general": ["donation_purpose_md", "refund_policy_md"],
}


@bp.route("/donations", methods=["GET", "POST"])
@admin_required
def donations():
    if request.method == "POST":
        method = request.form.get("method", "")
        if method not in DONATION_KEYS:
            abort(400)
        values, errors = {}, []
        for key in DONATION_KEYS[method]:
            if key in BOOL_KEYS:
                values[key] = "1" if request.form.get(key) else "0"
                continue
            val = (request.form.get(key) or "").strip()[:5000]
            if key == "wise_link" and val and not valid_url(val, https_only=True):
                errors.append("Wise payment link must be an https:// link.")
            if key == "jazzcash_number" and val and not all(ch.isdigit() or ch in " +-" for ch in val):
                errors.append("JazzCash number may contain only digits, spaces, + and -.")
            values[key] = val
        if method in ("jazzcash", "nayapay"):
            if request.form.get("remove_qr"):
                delete_media(get_settings().get(f"{method}_qr"))
                values[f"{method}_qr"] = ""
            qr = request.files.get("qr")
            if qr and qr.filename:
                try:
                    old = get_settings().get(f"{method}_qr")
                    values[f"{method}_qr"] = save_image(qr, "qr")
                    delete_media(old)
                except UploadError as exc:
                    errors.append(str(exc))
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            save_settings({k: v for k, v in values.items() if k in DEFAULTS})
            audit("donation_update", method)
            flash("Donation settings saved.", "success")
        return redirect(url_for("admin.donations") + f"#{method}")
    status = {m: donation_method(m) is not None for m in ("jazzcash", "nayapay", "wise")}
    return render_template("admin/donations.html", meta=META, status=status)


# ---------------------------------------------------------------- app downloads

PLATFORM_EXT = {"android": {".apk"}, "chrome": {".zip", ".crx"}}


@bp.route("/apps", methods=["GET", "POST"])
@admin_required
def apps():
    db = get_db()
    if request.method == "POST":
        platform = request.form.get("platform")
        if platform not in PLATFORM_EXT:
            abort(400)
        row = db.one("SELECT * FROM apps WHERE platform = ?", (platform,))
        data = {"version": (request.form.get("version") or "").strip()[:40],
                "external_url": (request.form.get("external_url") or "").strip()[:500], "updated_at": utcnow()}
        if data["external_url"] and not valid_url(data["external_url"], https_only=True):
            flash("Download link must be an https:// link.", "error")
            return redirect(url_for("admin.apps"))
        fs = request.files.get("file")
        if fs and fs.filename and current_app.config["EPHEMERAL_STORAGE"]:
            flash("This free hosting has no permanent disk, so uploaded files would vanish after a restart. "
                  "Upload the APK / zip to GitHub Releases and paste its https:// link instead.", "error")
            return redirect(url_for("admin.apps"))
        if fs and fs.filename:
            from .storage import software_ext
            if software_ext(fs.filename) not in PLATFORM_EXT[platform]:
                flash(f"For {platform} upload a {' or '.join(sorted(PLATFORM_EXT[platform]))} file.", "error")
                return redirect(url_for("admin.apps"))
            try:
                data.update(save_software(fs))
            except UploadError as exc:
                flash(str(exc), "error")
                return redirect(url_for("admin.apps"))
            if row and row["file_name"]:
                delete_file(row["file_name"])
        elif request.form.get("remove_file") and row and row["file_name"]:
            delete_file(row["file_name"])
            data.update({"file_name": None, "file_original_name": None, "file_size": 0, "file_sha256": None})
        if row:
            db.update("apps", row["id"], data)
        else:
            db.insert("apps", dict(data, platform=platform))
        db.commit()
        audit("app_update", platform)
        flash("Download saved.", "success")
        return redirect(url_for("admin.apps"))
    rows = {r["platform"]: r for r in db.all("SELECT * FROM apps")}
    return render_template("admin/apps.html", meta=META, apps=rows)


# ---------------------------------------------------------------- sponsored stations

def _save_blocked(rows):
    save_settings({"blocked_stations": json.dumps(rows[-2000:])})


@bp.route("/stations/block", methods=["POST"])
@admin_required
def block_station():
    """The 🚫 button on a station row (shown only to admins): hide that station for everyone."""
    from .settings import blocked_stations, stream_key
    from .security import safe_next
    name = (request.form.get("name") or "").strip()[:120]
    url = (request.form.get("url") or "").strip()[:500]
    uuid = (request.form.get("uuid") or "").strip()[:64]
    back = safe_next(request.form.get("back"), url_for("admin.stations"))
    if not (uuid or valid_url(url, https_only=True)):
        flash("This station could not be removed (no station id or stream address).", "error")
        return redirect(back)
    rows = blocked_stations()
    key = stream_key(url)
    if not any((uuid and r.get("uuid") == uuid) or (key and stream_key(r.get("url")) == key) for r in rows):
        rows.append({"name": name or "Radio station", "url": url if valid_url(url, https_only=True) else "",
                     "uuid": uuid, "reason": (request.form.get("reason") or "").strip()[:200],
                     "at": utcnow()[:16].replace("T", " ")})
        _save_blocked(rows)
        audit("station_removed", name or url or uuid)
    flash(f"“{name or 'Station'}” was removed from Sur Music. Restore it any time in Admin → Stations.", "success")
    return redirect(back)


@bp.route("/stations", methods=["GET", "POST"])
@admin_required
def stations():
    from .settings import blocked_stations
    rows = sponsored_stations()
    blocked = blocked_stations()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "unblock":
            i = clamp_int(request.form.get("index"), -1, len(blocked), -1)
            if 0 <= i < len(blocked):
                restored = blocked.pop(i)
                _save_blocked(blocked)
                audit("station_restored", restored.get("name", ""))
                flash(f"“{restored.get('name', 'Station')}” is back on Sur Music.", "success")
            return redirect(url_for("admin.stations"))
        if action == "block":
            name = (request.form.get("name") or "").strip()[:120]
            url = (request.form.get("url") or "").strip()[:500]
            if url and not valid_url(url, https_only=False):
                flash("The stream address must start with https:// or http://.", "error")
            elif not url and len(name) < 2:
                flash("Enter the station's stream address, or its exact name.", "error")
            else:
                blocked.append({"name": name or url, "url": url, "uuid": "", "match_name": not url,
                                "reason": (request.form.get("reason") or "").strip()[:200],
                                "at": utcnow()[:16].replace("T", " ")})
                _save_blocked(blocked)
                audit("station_removed", name or url)
                flash("Station removed from Sur Music.", "success")
            return redirect(url_for("admin.stations"))
        if action == "add":
            st = {"name": (request.form.get("name") or "").strip()[:120],
                  "url": (request.form.get("url") or "").strip(),
                  "favicon": (request.form.get("favicon") or "").strip(),
                  "country": (request.form.get("country") or "").strip()[:60],
                  "tags": (request.form.get("tags") or "").strip()[:120],
                  "category": request.form.get("category") if request.form.get("category") in
                  ("bollywood", "lollywood", "hollywood", "all") else "all"}
            if len(st["name"]) < 2 or not valid_url(st["url"], https_only=True):
                flash("Enter a station name and an https:// stream URL (browsers block http streams).", "error")
            elif st["favicon"] and not valid_url(st["favicon"], https_only=True):
                flash("Logo URL must be https://.", "error")
            else:
                rows.append(st)
                save_settings({"sponsored_stations": json.dumps(rows)})
                audit("sponsored_add", st["name"])
                flash("Sponsored station added.", "success")
        elif action == "remove":
            i = clamp_int(request.form.get("index"), -1, len(rows), -1)
            if 0 <= i < len(rows):
                removed = rows.pop(i)
                save_settings({"sponsored_stations": json.dumps(rows)})
                audit("sponsored_remove", removed.get("name", ""))
                flash("Sponsored station removed.", "success")
        return redirect(url_for("admin.stations"))
    return render_template("admin/stations.html", meta=META, rows=rows, blocked=blocked)


# ---------------------------------------------------------------- audit & backup

@bp.route("/audit")
@admin_required
def audit_log():
    rows = get_db().all("SELECT a.*, u.email FROM audit_log a LEFT JOIN users u ON u.id = a.admin_id "
                        "ORDER BY a.id DESC LIMIT 300")
    return render_template("admin/audit.html", meta=META, rows=rows)


@bp.route("/backup")
@admin_required
def backup():
    return render_template("admin/backup.html", meta=META)


@bp.route("/backup/download", methods=["POST"])
@admin_required
def backup_download():
    audit("backup_export")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return Response(export_data(), mimetype="application/json",
                    headers={"Content-Disposition": f'attachment; filename="surmusic-backup-{stamp}.json"'})


@bp.route("/backup/restore", methods=["POST"])
@admin_required
def backup_restore():
    fs = request.files.get("backup")
    if request.form.get("confirm") != "RESTORE":
        flash("Type RESTORE to confirm. Restoring replaces all current site data.", "error")
    elif not fs or not fs.filename:
        flash("Choose a backup file.", "error")
    else:
        try:
            raw = fs.read(200 * 1024 * 1024).decode("utf-8")
            data = json.loads(raw)
            admins = [u for u in (data.get("tables", {}).get("users") or []) if isinstance(u, dict)
                      and u.get("role") == "admin"]
            if not admins:
                raise ValueError("The backup has no administrator account, so restoring it would lock you out.")
            counts = restore_data(raw)
            audit("backup_restore", json.dumps(counts))
            flash("Backup restored: " + ", ".join(f"{k} {v}" for k, v in counts.items()) +
                  ". You may need to sign in again.", "success")
        except (ValueError, UnicodeDecodeError, AttributeError) as exc:
            flash(f"Restore failed: {exc}", "error")
    return redirect(url_for("admin.backup"))


@bp.before_request
def _admin_ctx():
    g.admin_area = True
