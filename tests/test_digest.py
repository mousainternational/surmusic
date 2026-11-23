from app import digest
from app.db import get_db
from tests.conftest import post, signup


def _member(app, name="Sara", verified=1):
    with app.app_context():
        db = get_db()
        uid = db.insert("users", {"email": f"{name.lower()}@example.com", "password_hash": "x", "display_name": name, "role": "user",
                                  "is_active": 1, "email_verified": verified, "created_at": "2026-01-01"})
        digest.set_optin(db, uid, True)
        return uid


def test_weekly_message_only_for_opted_in_confirmed_members_within_limit(app):
    _member(app, "Sara")
    _member(app, "Noor")
    _member(app, "Pending", verified=0)
    sent = []
    with app.app_context():
        db = get_db()
        n = digest.send_due(db, lambda to, subject, body: sent.append((to, body)) or "sent", "https://x.test",
                            [{"term": "Big match", "t": "Fans arrive"}], [{"t": "World headline"}], limit=250, pause=0)
        assert n == 2 and len(sent) == 2 and not any("pending@" in to for to, _ in sent)
        assert "Fans arrive" in sent[0][1] and "/unsubscribe/" in sent[0][1] and "World headline" in sent[0][1]
        again = digest.send_due(db, lambda to, subject, body: "sent", "https://x.test", [], [], limit=250, pause=0)
        assert again == 0                                              # once a week: nobody is mailed twice
        assert digest.sent_today(db) == 2


def test_daily_limit_and_unsent_setup(app):
    for i in range(3):
        _member(app, f"M{i}")
    with app.app_context():
        db = get_db()
        assert digest.send_due(db, lambda *a: "pending_setup", "https://x.test", [], [{"t": "h"}], limit=250, pause=0) == 0
        assert digest.send_due(db, lambda *a: "sent", "https://x.test", [], [{"t": "h"}], limit=2, pause=0) == 2
        assert digest.send_due(db, lambda *a: "sent", "https://x.test", [], [{"t": "h"}], limit=2, pause=0) == 0     # today's room is used up


def test_unsubscribe_link_and_account_switch(app, client):
    uid = _member(app, "Sara")
    with app.app_context():
        token = get_db().one("SELECT token FROM digest_optin WHERE user_id = ?", (uid,))["token"]
    assert "Yes, stop it" in client.get(f"/unsubscribe/{token}").get_data(as_text=True)
    assert "Done" in post(client, f"/unsubscribe/{token}", {}, page=f"/unsubscribe/{token}").get_data(as_text=True)
    with app.app_context():
        assert not digest.is_on(get_db(), uid)
    assert "not valid" in client.get("/unsubscribe/nope").get_data(as_text=True)


def test_signup_checkbox_turns_the_weekly_message_on(app, client):
    client.get("/signup")
    post(client, "/signup", {"email": "lina@example.com", "password": "listen-to-ghazals-42", "password2": "listen-to-ghazals-42",
                             "display_name": "Lina", "agree": "1", "digest": "1"}, page="/signup")
    with app.app_context():
        db = get_db()
        uid = db.one("SELECT id FROM users WHERE email = ?", ("lina@example.com",))["id"]
        assert digest.is_on(db, uid)


def test_account_page_has_the_weekly_switch(client):
    from tests.conftest import login
    login(client)
    html = client.get("/account").get_data(as_text=True)
    assert "Weekly message" in html and 'name="digest"' in html


def test_podcast_pause_keeps_the_place():
    js = open("app/static/js/player.js", encoding="utf-8").read()
    assert "function isEpisode" in js and "function resumeEpisode" in js and "keep the place in the episode" in js
