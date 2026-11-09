"""Stage 1: accounts, admin and settings survive a restart on hosting without a permanent disk;
the A–Z list is full right after a restart; settings can come from the code / environment."""
import base64
import gzip
import json

from app import persist
from app.db import Database
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, post


class FakeGitHub:
    """Stands in for the GitHub contents API (one file)."""

    def __init__(self):
        self.content = None
        self.sha = None
        self.puts = 0

    def __call__(self, method, url, body=None, token=None):
        assert token == "tok" and url.startswith("https://api.github.com/repos/me/backup/contents/")
        if method == "GET":
            if self.content is None:
                return 404, b"{}"
            return 200, json.dumps({"sha": self.sha, "content": self.content}).encode()
        if method == "PUT":
            if self.sha and body.get("sha") != self.sha:
                return 409, b"{}"
            self.puts += 1
            self.content = body["content"]
            self.sha = f"sha{self.puts}"
            return 201, json.dumps({"content": {"sha": self.sha}}).encode()
        raise AssertionError(method)


def _env(monkeypatch):
    monkeypatch.setenv("BACKUP_GITHUB_REPO", "me/backup")
    monkeypatch.setenv("BACKUP_GITHUB_TOKEN", "tok")
    fake = FakeGitHub()
    monkeypatch.setattr(persist, "_http", fake)
    persist._state.update({"last_hash": None, "sha": None})
    return fake


def test_backup_is_encrypted_and_restores_into_an_empty_database(app, tmp_path, monkeypatch):
    fake = _env(monkeypatch)
    url = app.config["DATABASE_URL"]
    db = Database(url)
    db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("adsense_client", "ca-pub-1234567890123456"))
    db.commit()
    db.close()
    assert persist.push_url(url) == "pushed"
    assert persist.push_url(url) == "unchanged"          # nothing changed: no new commit
    assert fake.puts == 1
    blob = base64.b64decode(fake.content)
    assert ADMIN_EMAIL.encode() not in blob and b"ca-pub" not in blob   # encrypted, not readable on GitHub

    # a restart on a free host: brand-new empty database file
    from app import db as dbmod
    fresh = f"sqlite:///{tmp_path / 'fresh.db'}"
    dbmod.migrate(fresh)
    persist._state.update({"last_hash": None, "sha": None})
    assert persist.restore_if_empty(fresh) == "restored"
    db = Database(fresh)
    assert db.scalar("SELECT role FROM users WHERE email = ?", (ADMIN_EMAIL,)) == "admin"
    assert db.scalar("SELECT value FROM settings WHERE key = 'adsense_client'") == "ca-pub-1234567890123456"
    db.close()
    assert persist.restore_if_empty(fresh) == "not-needed"   # never overwrites a database that has accounts


def test_an_empty_database_never_replaces_a_good_copy(app, tmp_path, monkeypatch):
    fake = _env(monkeypatch)
    assert persist.push_url(app.config["DATABASE_URL"]) == "pushed"
    from app import db as dbmod
    empty = f"sqlite:///{tmp_path / 'empty.db'}"
    dbmod.migrate(empty)
    assert persist.push_url(empty) == "unchanged"
    assert fake.puts == 1


def test_owner_can_sign_in_after_restart_when_backup_is_on(app, tmp_path, monkeypatch):
    _env(monkeypatch)
    persist.push_url(app.config["DATABASE_URL"])
    from app import create_app
    persist._state.update({"last_hash": None, "sha": None})
    monkeypatch.setattr(persist, "storage_is_persistent", lambda d: False)
    # create_app skips the restore in TESTING mode, so call it the way a real start does
    fresh = f"sqlite:///{tmp_path / 'restart.db'}"
    from app import db as dbmod
    dbmod.migrate(fresh)
    assert persist.restore_if_empty(fresh) == "restored"
    app2 = create_app({"TESTING": True, "DATABASE_URL": fresh, "STORAGE_DIR": str(tmp_path / "s2"),
                       "SITE_URL": "https://surmusic.example", "SESSION_COOKIE_SECURE": False,
                       "RATE_LIMITS_DISABLED": True, "TRUSTED_PROXIES": 0, "RADIO_DEMO": True})
    c = app2.test_client()
    r = post(c, "/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code in (302, 303)
    assert "Incorrect" not in c.get("/login").get_data(as_text=True)


def test_backup_off_without_settings(monkeypatch):
    monkeypatch.delenv("BACKUP_GITHUB_REPO", raising=False)
    monkeypatch.delenv("BACKUP_GITHUB_TOKEN", raising=False)
    assert persist.enabled() is False
    assert persist.restore_if_empty("sqlite:///unused.db") == "off"


def test_storage_persistence_check(monkeypatch, tmp_path):
    monkeypatch.delenv("RENDER", raising=False)
    assert persist.storage_is_persistent(str(tmp_path)) is True        # own computer / VPS
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setattr("os.path.ismount", lambda p: p == "/")
    assert persist.storage_is_persistent("/data/storage") is False      # Render free: no disk mounted
    monkeypatch.setattr("os.path.ismount", lambda p: p in ("/", "/data"))
    assert persist.storage_is_persistent("/data/storage") is True       # Render paid disk at /data


def test_settings_from_environment_survive_an_empty_database(app, monkeypatch):
    from app import settings
    monkeypatch.setenv("SETTING_ADSENSE_CLIENT", "ca-pub-9999999999999999")
    monkeypatch.setenv("SETTING_ADS_ENABLED", "1")
    monkeypatch.setattr(settings, "_STATIC", None)
    with app.test_request_context("/"):
        s = settings.get_settings()
        assert s["adsense_client"] == "ca-pub-9999999999999999" and settings.ads_active()
    monkeypatch.setattr(settings, "_STATIC", None)


def _bundle(path, n_per_letter):
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        i = 0
        for letter in "ab":
            for k in range(n_per_letter):
                i += 1
                st = {"uuid": f"{i:08d}-0000-0000-0000-000000000000", "name": f"{letter.upper()}Station {k}",
                      "url": "https://example.com/s.mp3", "clicks": k}
                fh.write(json.dumps({"c": 0, "s": st}) + "\n")
        fh.write(json.dumps({"c": 1, "s": {"uuid": "99999999-0000-0000-0000-000000000000", "name": "101 FM",
                                           "url": "https://example.com/1.mp3", "clicks": 5}}) + "\n")


def test_a_to_z_is_full_right_after_a_restart(app, client, tmp_path):
    from app import directory
    bundle = tmp_path / "dir.jsonl.gz"
    _bundle(bundle, 250)
    assert directory.load_bundle(app, str(bundle)) == 501
    assert directory.letter_counts(app) == {"a": 250, "b": 250, "0": 1}
    html = client.get("/stations/a").get_data(as_text=True)
    assert "250 live radio stations" in html and "AStation 249" in html     # most listened first
    assert 'href="/stations/a?page=2"' in html
    page2 = client.get("/stations/a?page=2").get_data(as_text=True)
    assert "AStation 0" in page2
    assert client.get("/stations/a?page=9").status_code == 404
    assert "101 FM" in client.get("/stations/0").get_data(as_text=True)
    assert client.get("/sitemap-stations-1.xml").status_code == 200


def test_failed_refresh_keeps_the_old_list(app, tmp_path, monkeypatch):
    from app import directory, radio
    bundle = tmp_path / "dir.jsonl.gz"
    _bundle(bundle, 1000)
    directory.load_bundle(app, str(bundle))
    with directory._open(app) as conn:                       # make it a week old so a refresh runs
        conn.execute("UPDATE meta SET value = '2020-01-01T00:00:00+00:00' WHERE key = 'done'")

    def broken(path):
        raise radio.RadioError("down")
    monkeypatch.setattr(radio, "_fetch_json", broken)
    directory.refresh(app, pause=0)
    assert directory.count(app) == 2001
