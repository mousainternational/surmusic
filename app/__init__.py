"""Sur Music Player & Radio — website (by Mousa International Software House)."""
import hashlib
import logging
import os
from datetime import datetime

import click
from flask import Flask, g, redirect, render_template, request, url_for
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash

from . import db as dbmod
from .config import Config
from .security import csp_nonce, csrf_protect, csrf_token, current_user, security_headers
from .settings import ads_active, get_settings
from .util import human_size, render_markdown, valid_email

__version__ = "1.7.4"


def create_app(overrides=None):
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:  # pragma: no cover
        pass

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", app.config["SECRET_KEY"])
    if overrides:
        app.config.update(overrides)
    if len(app.config["SECRET_KEY"] or "") < 32:
        raise RuntimeError("SECRET_KEY must be set to a random value of at least 32 characters (see .env.example).")

    if app.config["TRUSTED_PROXIES"] > 0:
        n = app.config["TRUSTED_PROXIES"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=n, x_proto=n, x_host=n)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    dbmod.ensure_dirs(app)
    dbmod.migrate(app.config["DATABASE_URL"])
    _bootstrap_admin(app)
    _apply_setting_changes(app)
    from . import geo as _geo
    _geo.start_auto_update(app)

    from .admin import bp as admin_bp
    from .auth import bp as auth_bp
    from .public import bp as public_bp
    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)

    app.teardown_appcontext(dbmod.close_db)
    app.before_request(_to_main_address)
    app.before_request(_lowdb_touch)
    app.before_request(csrf_protect)

    @app.after_request
    def _headers(resp):
        if request.path == "/ping":
            return resp
        try:
            ads = ads_active()
        except Exception:  # database unavailable during an error page
            ads = False
        resp = security_headers(resp, ads_enabled=ads)
        if request.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "public, max-age=604800"
        return resp

    asset_hashes = {}

    def asset(filename):
        """Static URL with a hash of the file's contents, so browsers always load the newest version."""
        path = os.path.join(app.static_folder, filename)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return url_for("static", filename=filename)
        cached = asset_hashes.get(filename)
        if not cached or cached[0] != mtime:
            with open(path, "rb") as fh:
                cached = (mtime, hashlib.sha256(fh.read()).hexdigest()[:12])
            asset_hashes[filename] = cached
        return url_for("static", filename=filename, v=cached[1])

    @app.context_processor
    def _globals():
        return {
            "S": get_settings(),
            "csrf_token": csrf_token,
            "csp_nonce": csp_nonce,
            "user": current_user(),
            "ads_on": ads_active(),
            "now_year": datetime.now().year,
            "geoip_on": _geo_available(),
            "app_version": __version__,
            "asset": asset,
        }

    app.jinja_env.filters["markdown"] = render_markdown
    app.jinja_env.filters["filesize"] = human_size
    app.jinja_env.filters["date"] = lambda v: (v or "")[:10]

    @app.errorhandler(HTTPException)
    def _http_error(err):
        if request.path.startswith("/api/") or request.path == "/healthz":
            return {"error": err.name}, err.code
        title = "Page not found" if err.code == 404 else "Something went wrong"
        tpl = "errors/404.html" if err.code == 404 else "errors/error.html"
        return render_template(tpl, error=err, meta={"title": f"{title} | Sur Music", "noindex": True}), err.code

    @app.errorhandler(Exception)
    def _server_error(err):
        app.logger.exception("Unhandled error")
        if request.path.startswith("/api/"):
            return {"error": "Server error"}, 500
        return render_template("errors/error.html", error=None,
                               meta={"title": "Something went wrong | Sur Music", "noindex": True}), 500

    register_cli(app)
    return app


def _geo_available():
    from . import geo
    return geo.available()


def register_cli(app):
    @app.cli.command("import-geoip")
    @click.argument("csv_file", type=click.Path(exists=True, dir_okay=False))
    def import_geoip(csv_file):
        """Import the free DB-IP 'IP to City Lite' (or Country Lite) CSV for visitor locations."""
        from . import geo
        dest = app.config["GEOIP_DB"]
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        click.echo(f"Importing {csv_file} → {dest} (this can take a few minutes)…")
        n = geo.import_csv(csv_file, dest, progress=lambda c: click.echo(f"  {c:,} ranges…"))
        click.echo(f"Done: {n:,} IP ranges. Visitor cities and countries will now appear in the admin panel.")

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.password_option()
    def create_admin(email, password):
        """Create an administrator (or make an existing account admin and reset its password)."""
        from .db import Database, utcnow
        email = email.strip().lower()
        if not valid_email(email):
            raise click.ClickException("Please enter a valid email address.")
        if len(password) < 12:
            raise click.ClickException("Admin password must be at least 12 characters.")
        db = Database(app.config["DATABASE_URL"])
        try:
            h = generate_password_hash(password, method="scrypt")
            row = db.one("SELECT id FROM users WHERE email = ?", (email,))
            if row:
                db.execute("UPDATE users SET password_hash = ?, role = 'admin', is_active = 1, email_verified = 1, "
                           "session_version = session_version + 1, failed_attempts = 0, locked_until = NULL "
                           "WHERE id = ?", (h, row["id"]))
                db.execute("DELETE FROM user_2fa WHERE user_id = ?", (row["id"],))
                click.echo("Account updated to administrator; its sessions were signed out and 2-step sign-in "
                           "was switched off (turn it on again in My account).")
            else:
                db.insert("users", {"email": email, "password_hash": h, "display_name": "Admin", "role": "admin",
                                    "is_active": 1, "email_verified": 1, "created_at": utcnow()})
                click.echo("Administrator created.")
            db.commit()
        finally:
            db.close()


def _bootstrap_admin(app):
    """Free hosts (Render free) have no shell for `create-admin`, so the first admin can come from
    ADMIN_EMAIL + ADMIN_PASSWORD. A NEW account is created only if that email is not registered yet;
    an existing account is never changed. Remove both variables after the first sign-in."""
    email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD") or ""
    if not email and not password:
        return
    if not valid_email(email) or len(password) < 12:
        app.logger.warning("ADMIN_EMAIL / ADMIN_PASSWORD ignored: need a valid email and a 12+ character password.")
        return
    from .db import Database, utcnow
    db = Database(app.config["DATABASE_URL"])
    try:
        if db.one("SELECT id FROM users WHERE email = ?", (email,)):
            return
        db.insert("users", {"email": email, "password_hash": generate_password_hash(password, method="scrypt"),
                            "display_name": "Admin", "role": "admin", "is_active": 1, "email_verified": 1,
                            "created_at": utcnow()})
        db.commit()
        app.logger.info("Administrator %s created from ADMIN_EMAIL. Remove ADMIN_PASSWORD from the host now.", email)
    except Exception:  # two workers starting together: the other one created it
        db.rollback()
    finally:
        db.close()


def _apply_setting_changes(app):
    """One-time changes to saved settings when an update changes a default (each runs once per database)."""
    from .db import Database
    db = Database(app.config["DATABASE_URL"])
    try:
        # v1.2: listening is free for everyone; the owner can switch "sign in to listen" back on in Settings
        if not db.scalar("SELECT COUNT(*) FROM settings WHERE key = ?", ("_done_free_listening_v12",)):
            db.execute("DELETE FROM settings WHERE key = ?", ("play_requires_login",))
            db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("_done_free_listening_v12", "1"))
            db.commit()
        # v1.6: the home page title/description name more kinds of radio (only if never changed by the owner)
        if not db.scalar("SELECT COUNT(*) FROM settings WHERE key = ?", ("_done_seo_text_v16",)):
            from .settings import DEFAULTS
            for key, old in (("seo_default_title", "Sur Music — Live Bollywood, Lollywood & Hollywood Radio"),
                             ("seo_default_description", "Listen free to live Bollywood, Lollywood (Pakistani) and "
                              "Hollywood radio. Hindi, Urdu, Punjabi and English music stations — by Mousa "
                              "International Software House.")):
                db.execute("UPDATE settings SET value = ? WHERE key = ? AND value = ?", (DEFAULTS[key], key, old))
            db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("_done_seo_text_v16", "1"))
            db.commit()
        # v1.7.4: a shorter home title that fits in a Google result (only if the owner never changed it)
        if not db.scalar("SELECT COUNT(*) FROM settings WHERE key = ?", ("_done_seo_text_v17",)):
            from .settings import DEFAULTS
            db.execute("UPDATE settings SET value = ? WHERE key = ? AND value = ?",
                       (DEFAULTS["seo_default_title"], "seo_default_title",
                        "Sur Music — Live Radio: Naat, Quran, Qawwali, News, Bollywood & Pakistani FM"))
            db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("_done_seo_text_v17", "1"))
            db.commit()
    except Exception:  # two workers starting together
        db.rollback()
    finally:
        db.close()


def _to_main_address():
    """After your own domain is set in SITE_URL, send visitors (and Google) from the old *.onrender.com
    address to it with a permanent redirect, so search engines see one website, not two."""
    from urllib.parse import urlsplit
    from flask import current_app
    if request.path in ("/ping", "/healthz"):
        return None
    site = urlsplit(current_app.config.get("SITE_URL", ""))
    host = (request.host or "").split(":")[0].lower()
    if site.scheme == "https" and site.hostname and not site.hostname.endswith(".onrender.com") \
            and host.endswith(".onrender.com"):
        target = f"https://{site.netloc}{request.full_path if request.query_string else request.path}"
        return redirect(target, code=301)
    return None


def _lowdb_touch():
    from . import lowdb
    if lowdb.enabled():
        lowdb.touch_request()
        if request.path.startswith(("/admin", "/account")):
            lowdb.flush()                  # up-to-date numbers and sign-ins (the database is awake for these anyway)
    return None

