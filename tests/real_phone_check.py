"""Real phone profiles (Galaxy, Pixel, iPhone SE/13), normal and 130% font: no sideways scrolling,
menu reachable above the player, Back keeps the scroll position. Start the site with RADIO_DEMO=1, then
    python tests/real_phone_check.py
"""
import sys
from playwright.sync_api import sync_playwright
BASE = "http://127.0.0.1:8100"
DEVICES = ["Galaxy S9+", "Pixel 5", "iPhone SE", "iPhone 13", "Galaxy S5"]
PAGES = ["/", "/bollywood", "/search?q=hits", "/download", "/donate", "/about", "/faq", "/login", "/signup", "/privacy"]
bad = 0
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for name in DEVICES:
        d = dict(pw.devices[name]); d.pop("default_browser_type", None)
        for scale in (100, 130):
            ctx = b.new_context(**d, bypass_csp=(scale != 100)); p = ctx.new_page()
            def big():
                if scale != 100: p.add_style_tag(content=f"body {{ font-size: {16 * scale / 100}px !important; }} html {{ font-size: {scale}% !important; }}")
            vw = d["viewport"]["width"]; vh = d["viewport"]["height"]
            for path in PAGES:
                p.goto(BASE + path); big()
                over = p.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                if over > 0:
                    bad += 1; print(f"FAIL {name} {vw}x{vh} font{scale}% {path}: page {over}px wider than screen")
            # mobile menu
            p.goto(BASE + "/"); big()
            p.click(".nav-toggle")
            r = p.evaluate("""(() => { const m = document.getElementById('menu'); const r = m.getBoundingClientRect();
                const last = [...m.querySelectorAll('a, button')].pop().getBoundingClientRect();
                const pl = document.getElementById('player'); const pr = pl ? pl.getBoundingClientRect() : {top: innerHeight};
                return {bottom: Math.round(r.bottom), lastBottom: Math.round(last.bottom), playerTop: Math.round(pr.top), vh: innerHeight,
                        canScroll: m.scrollHeight > m.clientHeight && getComputedStyle(m).overflowY !== 'visible'}; })()""")
            # scroll the menu to its end: the last link must then be above the player
            p.evaluate("(() => { const m = document.getElementById('menu'); m.scrollTop = m.scrollHeight; })()")
            r2 = p.evaluate("(() => { const m = document.getElementById('menu'); return Math.round([...m.querySelectorAll('a, button')].pop().getBoundingClientRect().bottom); })()")
            locked = p.evaluate("getComputedStyle(document.documentElement).overflow === 'hidden'")
            reach = r2 <= r["playerTop"] and locked
            r["lastBottom"] = f"{r['lastBottom']}→{r2} after scrolling menu, page locked {locked}"
            if not reach: bad += 1
            print(f"{'ok  ' if reach else 'FAIL'} {name} {vw}x{vh} font{scale}% menu: last link bottom {r['lastBottom']} / player top {r['playerTop']} / scrollable {r['canScroll']}")
            # small input text → iOS zoom on focus
            if scale == 100:
                small = p.evaluate("""[...document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]), select, textarea')]
                    .filter(e => e.getBoundingClientRect().width && parseFloat(getComputedStyle(e).fontSize) < 16).map(e => e.name || e.type)""")
                if small: bad += 1; print(f"FAIL {name}: inputs under 16px (iPhone zooms in on tap): {small}")
            if scale == 100:
                # Back button returns to the same place in a long list
                p.goto(BASE + "/bollywood"); p.wait_for_timeout(300)
                p.evaluate("window.scrollTo({top: 900, behavior: 'instant'})"); p.wait_for_timeout(400)
                p.locator("a[href='/about']").first.evaluate("a => a.click()"); p.wait_for_url("**/about"); p.wait_for_timeout(300)
                p.go_back(); p.wait_for_url("**/bollywood"); p.wait_for_timeout(700)
                y = p.evaluate("window.scrollY")
                ok = abs(y - 900) < 60
                bad += not ok
                print(f"{'ok  ' if ok else 'FAIL'} {name}: Back returns to the same place (y={y})")
                tap = p.evaluate("getComputedStyle(document.querySelector('.site-header')).backdropFilter")
                print(f"     {name}: header blur on phone = {tap}")
            ctx.close()
    b.close()
print("PROBLEMS:", bad)
