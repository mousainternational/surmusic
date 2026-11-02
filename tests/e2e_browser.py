"""Browser end-to-end checks (Playwright + Chromium) against a running dev server.

Start the server with demo stations and an admin (see README → Testing), then:
    MISH_BASE=http://127.0.0.1:8100 python tests/e2e_browser.py
Station streams (https://stream.example.com/...) are answered with a local test tone.
"""
import math
import os
import struct
import sys
import tempfile
import wave

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("MISH_BASE", "http://127.0.0.1:8100")
OUT = os.environ.get("SHOTS_DIR", tempfile.mkdtemp(prefix="surmusic-shots-"))
os.makedirs(OUT, exist_ok=True)
TONE = os.path.join(OUT, "tone.wav")
with wave.open(TONE, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
    w.writeframes(b"".join(struct.pack("<h", int(2500 * math.sin(2 * math.pi * 440 * i / 8000))) for i in range(8000 * 60)))
TONE_BYTES = open(TONE, "rb").read()
results = []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


def route_streams(ctx):
    ctx.route("https://stream.example.com/**",
              lambda r: r.fulfill(status=200, body=TONE_BYTES, headers={"Content-Type": "audio/wav"}))


with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = b.new_context(viewport={"width": 1366, "height": 900}, timezone_id="Asia/Karachi",
                        user_agent=("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
                                    "Chrome/130.0 Mobile Safari/537.36"))
    route_streams(ctx)
    page = ctx.new_page()
    errors = []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))

    UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/130.0 Mobile Safari/537.36")
    page.goto(BASE + "/")
    page.screenshot(path=f"{OUT}/home-top.png")
    check("home lists stations", page.locator("li.st").count() >= 10)
    check("no sign-in box by default (free listening)", page.locator("#login-gate").count() == 0)

    # guest favourite (allowed without an account)
    page.goto(BASE + "/hollywood")
    page.locator("li.st .st-fav").first.click()
    fav_name = page.locator("li.st .st-name").first.inner_text()
    check("guest favourite saved in browser", page.evaluate("JSON.parse(localStorage.getItem('sm-favs')).length") == 1)

    # a visitor WITHOUT an account presses play → music starts straight away
    page.goto(BASE + "/lollywood")
    want = page.locator("li.st .st-name").first.inner_text()
    page.locator("li.st .st-play").first.click()
    expect(page.locator("#player")).to_have_attribute("data-state", "playing", timeout=10000)
    check("guest plays without signing in", page.inner_text("#pl-name") == want)
    first_name = want
    # clicking a station also opens its own page (with its own ads and SEO), music keeps playing
    page.wait_for_url("**/station/**")
    page.wait_for_selector(f"h1:has-text({want!r})")
    check("station's own page opened", "/station/" in page.url and want in page.title())
    check("music keeps playing on the station page", page.evaluate("!document.getElementById('pl-audio').paused"))
    check("station page shows similar stations", page.locator("li.st").count() > 2)
    page.screenshot(path=f"{OUT}/station-page.png", full_page=True)

    # in-site navigation keeps playing
    page.click("#menu a[href='/bollywood']")
    page.wait_for_selector("h1:has-text('Bollywood Radio')")
    playing = page.evaluate("!document.getElementById('pl-audio').paused")
    check("music keeps playing after changing page", playing and page.inner_text("#pl-name") == first_name)
    check("URL and title updated", page.url.endswith("/bollywood") and "Bollywood" in page.title())
    page.go_back()
    page.wait_for_selector(f"h1:has-text({want!r})")
    check("back button works without stopping music", page.evaluate("!document.getElementById('pl-audio').paused"))

    # owner sees the guest listening live, with country (from the visitor's time zone here) and device
    adm_ctx = b.new_context(viewport={"width": 1366, "height": 900})
    a = adm_ctx.new_page()
    a.goto(BASE + "/login")
    a.fill("#email", "admin@example.com")
    a.fill("#password", "demo-password-123")
    a.click("button:has-text('Sign in')")
    a.wait_for_url("**/admin/")
    a.wait_for_timeout(500)
    a.goto(BASE + "/admin/live")
    live_text = a.inner_text("#live-rows")
    check("admin Live shows the guest listener and station", "Guest" in live_text and first_name in live_text)
    check("admin Live shows country and device", "Pakistan" in live_text and "Mobile" in live_text)
    a.screenshot(path=f"{OUT}/admin-live.png", full_page=True)

    page.click("#pl-next")
    expect(page.locator("#player")).to_have_attribute("data-state", "playing", timeout=10000)
    check("next station", page.inner_text("#pl-name") != first_name)
    page.wait_for_timeout(500)
    a.wait_for_timeout(16000)  # auto-refresh every 15 s
    check("admin Live updates by itself", page.inner_text("#pl-name") in a.inner_text("#live-rows"))
    page.click("#pl-play")
    check("pause", page.locator("#player").get_attribute("data-state") == "paused")

    # optional free account
    page.goto(BASE + "/signup")
    page.fill("#display_name", "Test Listener")
    page.fill("#email", f"listener{os.getpid()}@example.com")
    page.fill("#password", "listen-to-ghazals-42")
    page.fill("#password2", "listen-to-ghazals-42")
    page.check("input[name=agree]")
    page.screenshot(path=f"{OUT}/signup.png")
    page.click("button:has-text('Create account')")
    page.wait_for_load_state()
    check("optional sign-up works", "Test Listener" in page.inner_text("#menu"))
    for _ in range(20):          # browser favourites are moved into the new account in the background
        if not page.evaluate("JSON.parse(localStorage.getItem('sm-favs') || '[]').length"):
            break
        page.wait_for_timeout(250)
    page.goto(BASE + "/favorites")
    check("browser favourite moved into account", fav_name in page.inner_text("main"))
    page.goto(BASE + "/account")
    check("account page with recent sign-ins", "Recent sign-ins" in page.inner_text("main"))
    page.screenshot(path=f"{OUT}/account.png", full_page=True)

    a.goto(BASE + "/admin/activity")
    act = a.inner_text("main")
    check("activity log: guest play and sign-up recorded", "Signed up" in act and "Played a station" in act)
    check("activity log shows the visitor's country", "Pakistan" in act)
    a.screenshot(path=f"{OUT}/admin-activity.png", full_page=True)
    a.goto(BASE + "/admin/")
    check("admin dashboard", "Who is listening now" in a.inner_text("main"))
    a.screenshot(path=f"{OUT}/admin-dashboard.png", full_page=True)
    a.goto(BASE + "/admin/analytics?days=7")
    check("analytics page shows countries", "Countries" in a.inner_text("main") and "Pakistan" in a.inner_text("main"))
    a.screenshot(path=f"{OUT}/admin-analytics.png", full_page=True)

    # owner can still switch "sign in to listen" on (and off again)
    a.goto(BASE + "/admin/settings?section=accounts")
    a.check("input[name=play_requires_login]")
    a.click("button:has-text('Save settings')")
    a.wait_for_load_state()
    g = b.new_context(viewport={"width": 1366, "height": 900})
    route_streams(g)
    gp = g.new_page()
    gp.goto(BASE + "/hollywood")
    gp.locator("li.st .st-play").first.click()
    check("when switched on: sign-in box for guests", gp.locator("#login-gate").is_visible())
    check("when switched on: no stream links for guests", "stream.example.com" not in gp.content())
    a.goto(BASE + "/admin/settings?section=accounts")
    a.uncheck("input[name=play_requires_login]")
    a.click("button:has-text('Save settings')")
    a.wait_for_load_state()
    gp.goto(BASE + "/hollywood")
    gp.locator("li.st .st-play").first.click()
    expect(gp.locator("#player")).to_have_attribute("data-state", "playing", timeout=10000)
    check("switched off again: guest plays", True)
    g.close()

    page.goto(BASE + "/genre/qawwali")
    check("genre page (qawwali) lists stations", page.locator("li.st").count() > 0)

    # search via nav box (in-site navigation)
    page.goto(BASE + "/")
    page.fill("#nav-q", "hits")
    page.press("#nav-q", "Enter")
    page.wait_for_selector("h1:has-text('Results')")
    check("search works", page.locator("li.st").count() > 0)

    # mobile
    m = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    route_streams(m)
    mp = m.new_page()
    mp.on("pageerror", lambda e: errors.append(str(e)))
    for path in ["/", "/lollywood", "/download", "/donate", "/login", "/signup", "/privacy"]:
        mp.goto(BASE + path)
        w = mp.evaluate("document.documentElement.scrollWidth")
        check(f"mobile {path}: no horizontal scroll ({w}px)", w <= 390)
    mp.goto(BASE + "/")
    mp.click("#cookie-ok")
    mp.screenshot(path=f"{OUT}/home-mobile-top.png")
    mp.locator("li.st .st-play").nth(1).click()
    expect(mp.locator("#player")).to_have_attribute("data-state", "playing", timeout=10000)
    check("mobile: guest plays without signing in", True)
    mp.screenshot(path=f"{OUT}/playing-mobile.png")
    mp.click(".nav-toggle")
    check("mobile menu opens", mp.locator("#menu").is_visible())
    mp.screenshot(path=f"{OUT}/menu-mobile.png")

    # light theme screenshot
    page.goto(BASE + "/lollywood")
    page.click("#menu .theme-toggle")
    page.screenshot(path=f"{OUT}/lollywood-light.png")

    check("no browser console / CSP errors", not errors)
    for e in errors[:10]:
        print("  ", e)
    b.close()

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} browser checks passed · screenshots in {OUT}")
sys.exit(1 if failed else 0)
