"""Run the Sur Music website on your own computer in one step (Windows, macOS or Linux).

    python run_local.py

What it does:
  1. Installs the required Python packages (first time only).
  2. Creates a local .env file with a random secret key (first time only).
  3. Asks you for an admin email and password (first time only).
  4. Starts the website at http://127.0.0.1:8100 and opens your browser.

This is for trying the site on your computer. For the real public website, see README §4.
"""
import getpass
import os
import secrets
import socket
import subprocess
import sys
import threading
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
URL = "http://127.0.0.1:8100"


def step(msg):
    print(f"\n==> {msg}")


def ensure_python():
    if sys.version_info < (3, 10):
        sys.exit("Python 3.10 or newer is required. Download it from https://www.python.org/downloads/")


def ensure_packages():
    try:
        import flask, markdown, PIL, dotenv, cryptography, babel  # noqa: F401
        return
    except ImportError:
        pass
    step("Installing required packages (first time only, needs internet)...")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-local.txt"])
    if r.returncode:
        sys.exit("Package installation failed. Check your internet connection and try again.")


def ensure_env():
    if os.path.exists(".env"):
        return
    step("Creating local settings file (.env)...")
    data_dir = os.path.join(HERE, "data").replace("\\", "/")
    with open(".env", "w", encoding="utf-8") as f:
        f.write(
            "# Local development settings created by run_local.py\n"
            f"SECRET_KEY={secrets.token_urlsafe(48)}\n"
            f"SITE_URL={URL}\n"
            f"DATABASE_URL=sqlite:///{data_dir}/surmusic.db\n"
            f"STORAGE_DIR={data_dir}/storage\n"
            "SESSION_COOKIE_SECURE=0\n"
            "TRUSTED_PROXIES=0\n"
        )


def ensure_admin(app):
    from werkzeug.security import generate_password_hash

    from app.db import Database, utcnow
    from app.util import valid_email

    db = Database(app.config["DATABASE_URL"])
    try:
        if db.scalar("SELECT COUNT(*) FROM users WHERE role = 'admin'"):
            return
        step("Create your ADMIN account (sign in with it at /login to open the admin panel)")
        email = os.environ.get("MISH_ADMIN_EMAIL") or input("Admin email: ").strip().lower()
        while not valid_email(email):
            email = input("Please enter a valid email (must contain @): ").strip().lower()
        password = os.environ.get("MISH_ADMIN_PASSWORD") or ""
        while len(password) < 12:
            password = getpass.getpass("Password (at least 12 characters, hidden while typing): ")
            if len(password) < 12:
                print("Too short — use at least 12 characters.")
                password = ""
                continue
            if getpass.getpass("Repeat password: ") != password:
                print("Passwords did not match. Try again.")
                password = ""
        db.insert("users", {"email": email, "password_hash": generate_password_hash(password, method="scrypt"),
                            "display_name": "Admin", "role": "admin", "is_active": 1, "email_verified": 1,
                            "created_at": utcnow()})
        db.commit()
        print("Admin account created.")
    finally:
        db.close()


def ensure_geoip(app):
    """Import the newest DB-IP CSV placed in the 'geoip' folder (for visitor cities in the admin panel)."""
    import glob
    files = sorted(glob.glob(os.path.join(HERE, "geoip", "dbip-*.csv*")), key=os.path.getmtime)
    if not files:
        return
    src, dest = files[-1], app.config["GEOIP_DB"]
    if os.path.exists(dest) and os.path.getmtime(dest) >= os.path.getmtime(src):
        return
    from app import geo
    step(f"Importing visitor-location database {os.path.basename(src)} (one time, a few minutes)...")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    n = geo.import_csv(src, dest, progress=lambda c: print(f"  {c:,} ranges...", end="\r"))
    print(f"\nDone: {n:,} IP ranges.")


def port_in_use():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", 8100)) == 0


def main():
    if port_in_use():
        print("\n" + "=" * 70)
        print("Sur Music (or another program) is ALREADY RUNNING on port 8100.")
        print("That is probably an OLD window of the website - your browser would")
        print("show the old version.  Close every old Sur Music / black command")
        print("window (or restart the computer), then start this file again.")
        print("Roman Urdu: Purani Sur Music window abhi khuli hai - usay band karein")
        print("(ya computer restart karein), phir yeh file dobara chalayein.")
        print("=" * 70)
        sys.exit(1)
    ensure_python()
    ensure_packages()
    ensure_env()
    from app import create_app
    app = create_app()
    ensure_admin(app)
    ensure_geoip(app)
    step(f"Sur Music running at {URL}   (admin: sign in at {URL}/login)")
    print("Keep this window open while you use the site. Press Ctrl+C to stop.\n")
    if not os.environ.get("MISH_NO_BROWSER"):
        threading.Timer(1.5, lambda: webbrowser.open(URL)).start()
    app.run(host="127.0.0.1", port=8100, debug=False, threaded=True)


if __name__ == "__main__":
    main()
