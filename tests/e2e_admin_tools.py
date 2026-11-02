"""Browser checks for the admin tools: 🚫 remove-station button and 2-step sign-in (QR code + code step).

Start the site with RADIO_DEMO=1 and admin admin@example.com / demo-password-123, then
    MISH_BASE=http://127.0.0.1:8100 python tests/e2e_admin_tools.py
"""
import math
import os
import re
import struct
import sys
import wave
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from playwright.sync_api import expect, sync_playwright  # noqa: E402

BASE = os.environ.get("MISH_BASE", "http://127.0.0.1:8100")
EMAIL, PASSWORD = "admin@example.com", "demo-password-123"
OUT = os.environ.get("SHOTS_DIR", "/tmp/surmusic-admin-tools")
os.makedirs(OUT, exist_ok=True)
buf = io.BytesIO()
with wave.open(buf, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
    w.writeframes(b"".join(struct.pack("<h", int(2500 * math.sin(i / 3))) for i in range(8000 * 30)))
TONE = buf.getvalue()
results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


def totp(secret, offset=0):
    import base64, hashlib, hmac, time
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    step = int(time.time() // 30) + offset
    d = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    o = d[-1] & 15
    return str((struct.unpack(">I", d[o:o + 4])[0] & 0x7FFFFFFF) % 1000000).zfill(6)


with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    errors = []

    # ---- a visitor saves a station in the browser
    g = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    g.route("https://stream.example.com/**", lambda r: r.fulfill(status=200, body=TONE, headers={"Content-Type": "audio/wav"}))
    gp = g.new_page()
    gp.on("pageerror", lambda e: errors.append(str(e)))
    gp.goto(BASE + "/hollywood")
    target = gp.locator("li.st .st-name").first.inner_text()
    gp.locator("li.st .st-fav").first.click()
    check("visitor sees no admin button", gp.locator(".st-remove").count() == 0)

    # ---- admin removes it with the 🚫 button
    a = b.new_context(viewport={"width": 1366, "height": 900})
    ap = a.new_page()
    ap.on("pageerror", lambda e: errors.append(str(e)))
    ap.on("dialog", lambda d: d.accept())
    ap.goto(BASE + "/login"); ap.fill("#email", EMAIL); ap.fill("#password", PASSWORD)
    ap.click("button:has-text('Sign in')"); ap.wait_for_url("**/admin/")
    ap.goto(BASE + "/hollywood")
    check("admin sees 🚫 on every station", ap.locator(".st-remove").count() == ap.locator("li.st:not(.st-sponsored)").count() > 0)
    ap.screenshot(path=f"{OUT}/admin-remove-button.png")
    ap.locator("li.st").first.locator(".st-remove button").click()
    ap.wait_for_load_state()
    check("confirmation message after removing", "was removed from Sur Music" in ap.inner_text("body"))
    check("station gone from the list", target not in ap.locator("li.st .st-name").all_inner_texts())

    # ---- the visitor's saved copy no longer plays
    gp.goto(BASE + "/favorites")
    gp.locator("li.st .st-play").first.click()
    expect(gp.locator("#player")).to_have_attribute("data-state", "removed", timeout=8000)
    check("saved copy refused in the visitor's browser", "no longer available" in gp.inner_text("#pl-status"))
    check("…and forgotten from browser favourites",
          not any(s.get("name") == target for s in gp.evaluate("JSON.parse(localStorage.getItem('sm-favs') || '[]')")))
    gp.screenshot(path=f"{OUT}/visitor-removed.png")

    # ---- restore from Admin → Stations
    ap.goto(BASE + "/admin/stations")
    check("removed list in admin", target in ap.inner_text("main"))
    ap.screenshot(path=f"{OUT}/admin-stations.png", full_page=True)
    ap.locator("form:has(input[value=unblock]) button").first.click(); ap.wait_for_load_state()
    ap.goto(BASE + "/hollywood")
    check("restored station is back", target in ap.locator("li.st .st-name").all_inner_texts())

    # ---- owner removal request page
    gp.goto(BASE + "/contact?topic=removal")
    check("station owner removal page", "removal request" in gp.inner_text("main").lower())

    # ---- 2-step sign-in
    ap.goto(BASE + "/account")
    ap.click("text=Turn on 2-step sign-in")
    ap.click("button:has-text('Set up 2-step sign-in')")
    expect(ap.locator("#qr svg")).to_have_count(1, timeout=5000)
    check("QR code drawn on the page", ap.locator("#qr svg path").count() == 1)
    ap.screenshot(path=f"{OUT}/two-step-setup.png", full_page=True)
    secret = re.search(r"Key: ([A-Z2-7 ]+)", ap.inner_text("main")).group(1).replace(" ", "")
    ap.fill("#c2", totp(secret)); ap.click("button:has-text('Turn on')")
    codes = ap.inner_text("#recovery-codes").split()
    check("10 recovery codes shown once", len(codes) == 10)
    ap.screenshot(path=f"{OUT}/two-step-codes.png", full_page=True)

    n = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    np_ = n.new_page()
    np_.on("pageerror", lambda e: errors.append(str(e)))
    np_.goto(BASE + "/login"); np_.fill("#email", EMAIL); np_.fill("#password", PASSWORD)
    np_.click("button:has-text('Sign in')")
    np_.wait_for_url("**/login/code")
    check("password alone → asks for code", "sign-in code" in np_.inner_text("main").lower())
    np_.screenshot(path=f"{OUT}/code-step-phone.png")
    np_.fill("#code", totp(secret, 1)); np_.click("button:has-text('Continue')")
    np_.wait_for_url("**/admin/")
    check("code accepted → admin panel", "Dashboard" in np_.inner_text("body"))
    w = np_.evaluate("document.documentElement.scrollWidth")
    check(f"code step fits the phone ({w}px)", w <= 390)

    # switch it off again with password + recovery code
    ap.goto(BASE + "/account/two-step")
    ap.fill("#pw", PASSWORD); ap.fill("#c1", codes[0]); ap.click("button:has-text('Turn off 2-step sign-in')")
    ap.wait_for_load_state()
    check("turned off with a recovery code", "Turn on 2-step sign-in" in ap.inner_text("main"))
    check("no browser errors", not errors)
    for e in errors[:5]:
        print("  ", e)
    b.close()

print(f"\n{sum(results)}/{len(results)} admin-tool checks passed · screenshots in {OUT}")
sys.exit(0 if all(results) else 1)
