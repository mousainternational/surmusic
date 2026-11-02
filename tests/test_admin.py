import io
import os
import re

from conftest import apk_bytes, login, png_bytes, post


def test_ads_off_by_default(client):
    html = client.get("/").get_data(as_text=True)
    assert "adsbygoogle" not in html
    assert "strict-dynamic" not in client.get("/").headers["Content-Security-Policy"]


def test_ads_settings_validation_and_rendering(client, app):
    login(client)
    r = post(client, "/admin/ads", {"adsense_client": "pub-123", "ads_enabled": "1"}, page="/admin/ads",
             follow_redirects=True)
    assert b"must look like ca-pub-" in r.data
    form = {"adsense_client": "ca-pub-1234567890123456", "ad_slot_top": "1111111111",
            "ad_slot_list": "2222222222", "ad_slot_side": "3333333333", "ad_slot_footer": "4444444444",
            "ads_enabled": "1"}
    # the European consent message must be confirmed first (reminder on the dashboard until then)
    r = post(client, "/admin/ads", form, page="/admin/ads", follow_redirects=True)
    assert b"European consent message" in r.data and "adsbygoogle" not in app.test_client().get("/").get_data(as_text=True)
    post(client, "/admin/ads", dict(form, ads_enabled="0"), page="/admin/ads")
    assert "European regulations" in client.get("/admin/").get_data(as_text=True)
    post(client, "/admin/ads", dict(form, ads_eu_consent="1"), page="/admin/ads")
    assert "European regulations" not in client.get("/admin/").get_data(as_text=True)
    anon = app.test_client()
    r = anon.get("/bollywood")
    html = r.get_data(as_text=True)
    nonce = re.search(r"'nonce-([^']+)'", r.headers["Content-Security-Policy"]).group(1)
    assert f'nonce="{nonce}" src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1234567890123456"' in html
    assert 'data-ad-slot="1111111111"' in html and 'data-ad-slot="3333333333"' in html
    assert "Advertisement" in html
    assert "strict-dynamic" in r.headers["Content-Security-Policy"]
    assert anon.get("/ads.txt").get_data(as_text=True).strip() == \
        "google.com, pub-1234567890123456, DIRECT, f08c47fec0942fa0"
    # the new header never holds an ad, and the home and new pages keep their ad slots
    home = anon.get("/").get_data(as_text=True)
    assert 'data-ad-slot="1111111111"' in home
    assert "adsbygoogle" not in home.split("<body", 1)[1].split("</header>", 1)[0]
    for path in ("/markets", "/islam", "/live-news", "/radio-stations", "/blog", "/blog/listen-quran-radio-online-free"):
        assert 'data-ad-slot="1111111111"' in anon.get(path).get_data(as_text=True), path
    # never on admin or account pages
    assert "adsbygoogle" not in client.get("/admin/").get_data(as_text=True)
    assert "strict-dynamic" not in client.get("/admin/").headers["Content-Security-Policy"]


def test_sponsored_station(client, app):
    login(client)
    r = post(client, "/admin/stations", {"action": "add", "name": "City FM", "url": "http://insecure.example"},
             page="/admin/stations", follow_redirects=True)
    assert b"https://" in r.data
    post(client, "/admin/stations", {"action": "add", "name": "City FM 89", "url": "https://city.example/stream",
                                     "category": "lollywood"}, page="/admin/stations")
    html = app.test_client().get("/lollywood").get_data(as_text=True)
    assert "City FM 89" in html and "Sponsored" in html
    assert "City FM 89" not in app.test_client().get("/hollywood").get_data(as_text=True)


def test_app_downloads(client, app, tmp_path, monkeypatch):
    from app import public
    monkeypatch.setattr(public, "APK_DIR", str(tmp_path))        # no shipped APK in this test: only the uploaded-file rules
    anon = app.test_client()
    assert b"Coming soon" in anon.get("/download").data
    login(client)
    r = post(client, "/admin/apps", {"platform": "android", "version": "1.0.0",
                                     "file": (io.BytesIO(b"not an apk"), "SurMusic.apk")},
             page="/admin/apps", content_type="multipart/form-data", follow_redirects=True)
    assert b"does not match" in r.data
    r = post(client, "/admin/apps", {"platform": "android", "version": "1.0.0",
                                     "file": (io.BytesIO(apk_bytes()), "evil.exe")},
             page="/admin/apps", content_type="multipart/form-data", follow_redirects=True)
    assert b"upload a .apk file" in r.data
    post(client, "/admin/apps", {"platform": "android", "version": "1.0.0",
                                 "file": (io.BytesIO(apk_bytes()), "SurMusic-1.0.0.apk")},
         page="/admin/apps", content_type="multipart/form-data")
    page = anon.get("/download").get_data(as_text=True)
    assert "US$5 per year" in page and "mousainternational@gmail.com" in page and "Download the Android app" not in page
    assert anon.get("/download/android").status_code == 404              # the file is never given away
    post(client, "/admin/apps", {"platform": "android",
                                 "external_url": "https://play.google.com/store/apps/details?id=com.mousainternational.surmusic"},
         page="/admin/apps")
    assert "Get the Android app" in anon.get("/download").get_data(as_text=True)
    assert anon.get("/download/android").headers["Location"].startswith("https://play.google.com/")
    post(client, "/admin/apps", {"platform": "chrome", "external_url": "https://chromewebstore.google.com/detail/x"},
         page="/admin/apps")
    r = anon.get("/download/chrome")
    assert r.status_code == 302 and r.headers["Location"].startswith("https://chromewebstore.google.com/")


def test_donations_hidden_until_verified(client, app):
    assert "03217913507" not in app.test_client().get("/donate").get_data(as_text=True)
    login(client)
    post(client, "/admin/donations", {"method": "jazzcash", "jazzcash_holder": "Owner Name",
                                      "jazzcash_number": "03217913507", "jazzcash_enabled": "1",
                                      "jazzcash_verified": "1", "qr": (io.BytesIO(png_bytes((400, 400))), "qr.png")},
         page="/admin/donations", content_type="multipart/form-data")
    html = app.test_client().get("/donate").get_data(as_text=True)
    assert "Owner Name" in html and "03217913507" in html and "JazzCash QR code" in html


def test_contact_email_validation(client):
    login(client)
    r = post(client, "/admin/settings?section=general", {"site_name": "Sur Music", "contact_email": "mousainternational.gami.com"},
             page="/admin/settings", follow_redirects=True)
    assert b"not a valid address" in r.data


def test_backup_roundtrip(client, app):
    login(client)
    post(client, "/admin/stations", {"action": "add", "name": "Backup FM", "url": "https://b.example/s",
                                     "category": "all"}, page="/admin/stations")
    data = post(client, "/admin/backup/download", page="/admin/backup").data
    assert b'"surmusic-backup-v1"' in data
    post(client, "/admin/stations", {"action": "remove", "index": "0"}, page="/admin/stations")
    r = post(client, "/admin/backup/restore", {"confirm": "RESTORE", "backup": (io.BytesIO(data), "b.json")},
             page="/admin/backup", content_type="multipart/form-data", follow_redirects=True)
    assert b"Backup restored" in r.data
    assert b"Backup FM" in app.test_client().get("/bollywood").data
    r = post(client, "/admin/backup/restore", {"confirm": "RESTORE", "backup": (io.BytesIO(
        b'{"format": "surmusic-backup-v1", "tables": {"users": []}}'), "b.json")}, page="/admin/backup",
        content_type="multipart/form-data", follow_redirects=True)
    assert b"lock you out" in r.data


def test_audit_log(client):
    login(client)
    post(client, "/admin/cache/clear", page="/admin/")
    html = client.get("/admin/audit").get_data(as_text=True)
    assert "admin_login" in html and "station_cache_clear" in html


def test_upload_never_trusts_filename(client, app):
    login(client)
    post(client, "/admin/apps", {"platform": "android", "file": (io.BytesIO(apk_bytes()), "../../evil.apk")},
         page="/admin/apps", content_type="multipart/form-data")
    names = [n for n in os.listdir(os.path.join(app.config["STORAGE_DIR"], "files")) if not n.startswith(".")]
    assert len(names) == 1 and re.fullmatch(r"[0-9a-f]{32}\.apk", names[0])


def test_free_hosting_images_survive_and_uploads_become_links(client, app):
    """Render free has no permanent disk: QR images come back from the database; app files must be links."""
    login(client)
    post(client, "/admin/donations", {"method": "nayapay", "nayapay_holder": "Owner Name",
                                      "nayapay_number": "03217913507", "nayapay_enabled": "1",
                                      "nayapay_verified": "1", "qr": (io.BytesIO(png_bytes((300, 300))), "qr.png")},
         page="/admin/donations", content_type="multipart/form-data")
    html = app.test_client().get("/donate").get_data(as_text=True)
    name = re.search(r"/media/([0-9a-f]{32}\.\w+)", html).group(1)
    os.remove(os.path.join(app.config["STORAGE_DIR"], "media", name))   # disk wiped by a restart
    r = app.test_client().get("/media/" + name)
    assert r.status_code == 200 and r.mimetype.startswith("image/") and r.data[:4] == b"\x89PNG"

    app.config["EPHEMERAL_STORAGE"] = True
    page = client.get("/admin/apps").get_data(as_text=True)
    assert "GitHub Releases" in page and 'type="file"' not in page
    r = post(client, "/admin/apps", {"platform": "android", "version": "1.0.0",
                                     "file": (io.BytesIO(apk_bytes()), "SurMusic.apk")},
             page="/admin/apps", content_type="multipart/form-data", follow_redirects=True)
    assert b"no permanent disk" in r.data


def test_station_removal_by_admin(client, app):
    """Owner removes a station (e.g. after a station owner's request): hidden and unplayable for everyone."""
    from conftest import api
    anon = app.test_client()
    html = anon.get("/hollywood").get_data(as_text=True)
    first = re.search(r'data-station="([^"]+)"', html).group(1)
    import html as _h, json as _j
    st = _j.loads(_h.unescape(first))
    assert 'class="st-remove"' not in html                       # visitors never see the button
    login(client)
    page = client.get("/hollywood").get_data(as_text=True)
    assert 'class="st-remove"' in page                            # admin sees 🚫 on each row
    r = post(client, "/admin/stations/block", {"uuid": st["uuid"], "url": st["url"], "name": st["name"],
                                               "back": "/hollywood"}, page="/hollywood")
    assert r.status_code == 302 and r.headers["Location"].endswith("/hollywood")
    after = anon.get("/hollywood").get_data(as_text=True)
    assert st["url"] not in after
    assert st["uuid"] not in [s["uuid"] for s in anon.get("/api/stations/hollywood").get_json()["stations"]]
    assert api(anon, "POST", "/api/play", {"station": st}).status_code == 410        # saved in a browser: refused
    same_stream = dict(st, uuid="other-id")
    assert api(anon, "POST", "/api/play", {"station": same_stream}).status_code == 410
    admin_page = client.get("/admin/stations").get_data(as_text=True)
    assert st["name"] in admin_page and "Restore" in admin_page
    post(client, "/admin/stations", {"action": "unblock", "index": "0"}, page="/admin/stations")
    assert api(anon, "POST", "/api/play", {"station": st}).status_code == 200
    # by address only (from an owner's email)
    post(client, "/admin/stations", {"action": "block", "url": st["url"]}, page="/admin/stations")
    assert api(anon, "POST", "/api/play", {"station": st}).status_code == 410
    # non-admins cannot remove stations
    assert anon.post("/admin/stations/block", data={"uuid": "x"}).status_code in (302, 400, 403)


def test_station_owner_removal_request_page(client):
    html = client.get("/contact?topic=removal&station=Radio%20X").get_data(as_text=True)
    assert "Station owners: removal request" in html and 'value="Station removal request: Radio X"' in html
    assert "Station owners: remove a station" in client.get("/").get_data(as_text=True)


def test_apk_button_appears_when_the_file_is_shipped(app, tmp_path, monkeypatch):
    from app import public
    apk = tmp_path / "SurMusic.apk"
    apk.write_bytes(apk_bytes())
    monkeypatch.setattr(public, "APK_DIR", str(tmp_path))
    anon = app.test_client()
    page = anon.get("/download").get_data(as_text=True)
    assert "Download the Android app (APK)" in page and "Create a free account" in page
    r = anon.get("/download/android")
    assert r.status_code == 200 and r.mimetype == "application/vnd.android.package-archive"
    assert "attachment" in r.headers["Content-Disposition"] and r.data == apk_bytes()


def test_admin_can_make_a_one_time_password_reset_link(client, app):
    import re
    from conftest import USER_PASSWORD, signup
    member = app.test_client()
    signup(member, "forgot@example.com")
    login(client)
    uid = client.get("/admin/users").get_data(as_text=True)
    m = re.search(r'/admin/users/(\d+)/reset_link', uid)
    assert m, "the button is shown for a member"
    r = post(client, f"/admin/users/{m.group(1)}/reset_link", page="/admin/users", follow_redirects=True)
    link = re.search(r"(http\S*/reset/[\w.\-]+)", r.get_data(as_text=True).replace("&#34;", '"'))
    assert link, "the link is shown to the owner once"
    path = "/reset/" + link.group(1).split("/reset/")[1]
    visitor = app.test_client()
    assert visitor.get(path).status_code == 200
    new_pw = "brand-new-password-4567"
    assert post(visitor, path, {"password": new_pw, "password2": new_pw}, page=path).status_code == 302
    again = app.test_client()
    assert again.get(path, follow_redirects=True).status_code == 200 and b"already used" in again.get(path, follow_redirects=True).data
    assert post(app.test_client(), "/login", {"email": "forgot@example.com", "password": new_pw}).status_code == 302
    # an administrator's own account is never reset this way
    admin_id = re.search(r"/admin/users/(\d+)/suspend", uid)
    assert b"cannot be suspended, deleted or reset" in post(client, "/admin/users/1/reset_link", page="/admin/users", follow_redirects=True).data


def test_messages_list_has_reply_and_delete_buttons(client, app):
    import re
    from conftest import post as _post
    anon = app.test_client()
    _post(anon, "/contact", {"name": "Spammer", "email": "spam@example.com", "subject": "Improve Your Search Engine Visibility",
                            "message": "buy seo now please"}, page="/contact")
    login(client)
    page = client.get("/admin/messages").get_data(as_text=True)
    assert "mailto:spam@example.com" in page and ">Reply<" in page
    m = re.search(r"/admin/messages/(\d+)/delete", page)
    assert m, "a Delete button sits in the list itself"
    r = post(client, f"/admin/messages/{m.group(1)}/delete", page="/admin/messages", follow_redirects=True)
    assert b"Message deleted" in r.data and b"spam@example.com" not in client.get("/admin/messages").data
