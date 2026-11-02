"""Phone check of every page (360 px and 412 px): no sideways scrolling; saves screenshots.
Usage: start the site with RADIO_DEMO=1 and admin admin@example.com / demo-password-123, then
    python tests/mobile_check.py OUTPUT_FOLDER
"""
import math, struct, wave, io, os, sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8100"
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
PUBLIC = ["/", "/bollywood", "/lollywood", "/hollywood", "/search?q=hits", "/favorites", "/download", "/donate",
          "/about", "/faq", "/contact", "/privacy", "/terms", "/disclaimer", "/donation-disclaimer", "/cookies",
          "/login", "/signup", "/forgot-password", "/nope-404", "/genre/naat", "/genre/qawwali", "/deals", "/radio-stations", "/country/pakistan", "/genre/pashto", "/continent/europe", "/country/japan",
          "/station/demo-lollywood-2/qawwali-live-24-7"]
ACCOUNT = ["/account"]
ADMIN = ["/admin/", "/admin/analytics", "/admin/live", "/admin/activity", "/admin/users", "/admin/messages",
         "/admin/settings", "/admin/ads", "/admin/donations", "/admin/apps", "/admin/stations", "/admin/audit",
         "/admin/backup", "/admin/offers"]

buf = io.BytesIO()
with wave.open(buf, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
    w.writeframes(b"".join(struct.pack("<h", int(2500 * math.sin(i / 3))) for i in range(8000 * 30)))
TONE = buf.getvalue()

PROBE = """() => {
  const W = document.documentElement.clientWidth;
  const over = document.documentElement.scrollWidth - W;
  const wide = [];
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width && r.right > W + 1 && getComputedStyle(el).position !== 'fixed') {
      let p = el.parentElement, clipped = false;
      while (p) { const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden') { clipped = true; break; } p = p.parentElement; }
      if (!clipped) wide.push(el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : '') + ' ' + Math.round(r.right));
    }
  }
  const small = [];
  for (const el of document.querySelectorAll('a, button, input:not([type=hidden]), select, summary')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden') continue;
    const inline = el.tagName === 'A' && el.closest('p, li.small, .small, footer p, td, .prose');
    if (!inline && (r.height < 32 || r.width < 32)) small.push((el.textContent || el.getAttribute('aria-label') || el.name || el.tagName).trim().slice(0, 25) + ` ${Math.round(r.width)}x${Math.round(r.height)}`);
  }
  let tiny = 0;
  for (const el of document.querySelectorAll('p, li, td, label, a, span')) {
    if (el.children.length === 0 && el.textContent.trim() && parseFloat(getComputedStyle(el).fontSize) < 12) tiny++;
  }
  return {over, wide: wide.slice(0, 4), small: small.slice(0, 6), nsmall: small.length, tiny};
}"""

problems = 0
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    for dev, (w, h) in {"360": (360, 740), "412": (412, 915)}.items():
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True)
        ctx.route("https://stream.example.com/**", lambda r: r.fulfill(status=200, body=TONE, headers={"Content-Type": "audio/wav"}))
        p = ctx.new_page()

        def run(paths, tag):
            global problems
            for path in paths:
                p.goto(BASE + path)
                res = p.evaluate(PROBE)
                bad = res["over"] > 0 or res["wide"]
                problems += bool(bad)
                flag = "FAIL" if bad else "ok  "
                note = f"overflow {res['over']}px {res['wide']}" if bad else ""
                small = f" small-taps={res['nsmall']} {res['small'][:3]}" if res["nsmall"] else ""
                tiny = f" tiny-text={res['tiny']}" if res["tiny"] else ""
                print(f"{flag} {dev}px {tag:7} {path:22} {note}{small}{tiny}")
                if dev == "360" and path in ("/", "/login", "/admin/", "/admin/live", "/admin/users", "/account", "/donate"):
                    p.screenshot(path=f"{OUT}/{dev}_{tag}_{path.strip('/').replace('/', '_') or 'home'}.png")

        run(PUBLIC, "guest")
        # guest pressing play → sign-in box
        p.goto(BASE + "/"); p.locator("li.st .st-play").first.click(); p.wait_for_timeout(600)
        if dev == "360": p.screenshot(path=f"{OUT}/{dev}_guest_signin_box.png")
        # admin sign in
        p.goto(BASE + "/login")
        p.fill("input[name=email]", "admin@example.com"); p.fill("input[name=password]", "demo-password-123")
        p.locator("form button[type=submit], form .btn-primary").first.click(); p.wait_for_load_state()
        p.goto(BASE + "/"); p.locator("li.st .st-play").first.click(); p.wait_for_timeout(1500)
        if dev == "360": p.screenshot(path=f"{OUT}/{dev}_member_playing.png")
        playing = p.evaluate("(() => { const a = document.getElementById('pl-audio'); return !!a.currentSrc && !a.paused; })()")
        print(f"{'ok  ' if playing else 'FAIL'} {dev}px member plays on phone")
        problems += not playing
        run(ACCOUNT, "member")
        run(ADMIN, "admin")
        ctx.close()
    # Computer screens: admin menu must sit BESIDE the page (≥960 px), above it on smaller screens
    for w, side in ((1366, True), (1024, True), (960, True), (800, False)):
        ctx = b.new_context(viewport={"width": w, "height": 800}); p = ctx.new_page()
        p.goto(BASE + "/login"); p.fill("input[name=email]", "admin@example.com")
        p.fill("input[name=password]", "demo-password-123"); p.locator("form .btn-primary").first.click()
        p.wait_for_load_state(); p.goto(BASE + "/admin/")
        n, m = p.evaluate("""(() => [document.querySelector('.admin-nav').getBoundingClientRect().toJSON(),
                                     document.querySelector('.admin-main').getBoundingClientRect().toJSON()])()""")
        ok = (n["width"] == 240 and m["top"] == 0 and m["left"] == 240) if side else (m["top"] > 0 and n["height"] < 200)
        problems += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {w}px admin layout: menu {'beside' if side else 'above'} the page "
              f"(menu {round(n['width'])}x{round(n['height'])}, page at {round(m['left'])},{round(m['top'])})")
        if w == 1366: p.screenshot(path=f"{OUT}/1366_admin_desktop.png")
        ctx.close()
    b.close()
print("\nPROBLEMS:", problems)
