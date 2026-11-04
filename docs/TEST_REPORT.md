# Sur Music website — test report

Date: 28 October 2026 · Linux, Python 3.13, SQLite 3.53, PostgreSQL 16 (local), headless Chromium (Playwright). Only tests that actually ran are marked passed.

| Suite | Result |
| --- | --- |
| `python -m pytest` | **82 / 82 passed** |
| Browser end-to-end (`tests/e2e_browser.py`; desktop 1366 px, mobile 390 px) | **37 / 37 passed** |
| PostgreSQL (`tests/pg_check.py`) | schema applied twice; **150 / 150** distinct SQL statements prepared on PostgreSQL 16 |
| One-click launcher (`run_local.py`) | created `.env` + admin, served pages, `/healthz` ok; refuses to start (with a clear message) when an old copy is still running on port 8100 |
| Signed-out visitor, every play path (v1.1.0) | **12 / 12 blocked**: station click, hero button, player Play/Next, old station saved in the browser by an earlier version, old browser favourite, Lollywood, Hollywood, search — no stream was ever requested |

## What was verified

| Area | Status | Evidence |
| --- | --- | --- |
| All 20 public pages, 404, branding | ✅ | every page 200 and shows “Mousa International Software House” |
| Free listening (v1.2) | ✅ | guests play straight away (browser test, desktop + phone); guest plays still counted with country and device; owners who had “sign in to listen” saved are switched to free listening once by the update and can switch it on again (sign-in box, no stream links for guests — browser test) |
| Sign in to listen (optional) | ✅ | guests see stations but no stream URLs (encrypted tokens); play → sign-in box naming the station; `/api/stream` and `/api/play` refuse guests; tampered token rejected; sign-up returns to the same page with the station ready; switching the setting off lets guests play |
| Owner analytics | ✅ | sign-up / sign-in / failed sign-in / sign-out recorded with device, browser, OS; page views with time-zone country (no invented city) and referrer; bots ignored; admin pages ignored; live listeners with station, place, device, minutes (auto-refresh verified in the browser); listening duration recorded on stop (capped at one minute past the last check-in); Analytics, Activity, Live, Users, member page render; recent sign-ins on My account; account deletion unlinks activity; retention purge |
| City locations — automatic (v1.2) | ✅ | official MaxMind test database read by the bundled reader (London / Linköping / Japan); monthly download simulated with a local server: falls back to last month on 404, rejects a non-database file, never leaves half files, runs once a month; through a simulated Cloudflare Tunnel two phone visitors appeared in Admin → Live as “London, United Kingdom” and “Linköping, Sweden”; a forged `CF-Connecting-IP` from the internet is ignored; the real DB-IP download (~120 MB) could not be fetched from this build environment |
| City locations (CSV import, older method) | ✅ | DB-IP City Lite CSV (with header, gzip, IPv4 + IPv6) imported and looked up; city shown in Live and Activity; DB-IP attribution shown in the footer; Cloudflare headers used only when `TRUST_CF_HEADERS=1` |
| Web player | ✅ | station plays, keeps playing across page changes and the browser Back button, next, pause (audio routed to a local test tone) |
| Station lists | ✅ | server-rendered; https-only, broken, HLS and duplicate stations filtered; cache reused; stale cache served when the directory is down; friendly error when nothing is cached |
| Accounts | ✅ | sign-up validation (weak/common/mismatch/terms), duplicate email, sign-in/out, lockout after 5 failures, login rate limit, remember-me cookie, reset by email (single use, 1-hour), honest message without SMTP, email confirmation mode, change password signs out other devices, export data, delete account |
| Favourites & history | ✅ | API requires sign-in + CSRF, rejects unsafe stations, add/list/delete/import; browser favourites moved into the account after sign-up (browser test) |
| Admin | ✅ | non-admin 403; all 11 admin pages; suspend signs the user out; admins cannot be deleted; sponsored stations; APK upload validation (extension, content, random file name) and download; Chrome store redirect; backup restore refuses backups without an admin |
| Ads | ✅ | off by default (strict CSP, no Google script); invalid publisher ID rejected; when on: AdSense script carries the CSP nonce, 4 placements render with “Advertisement” label, `ads.txt` line correct, never on admin/account pages |
| Donations | ✅ | hidden until holder + verified + enabled; QR shown afterwards |
| Security headers | ✅ | per-request nonce CSP on every script, no inline handlers or style attributes, X-Frame-Options, nosniff, noindex + no-store on account/auth/admin, open-redirect blocked, Markdown XSS neutralised |
| SEO | ✅ | unique titles, canonical, OG/Twitter, JSON-LD (WebSite, WebApplication, Organization, FAQPage, BreadcrumbList), sitemap, robots |
| Mobile layout | ✅ | `tests/mobile_check.py`: all 20 public pages, My account and all 13 admin pages at **360 px and 412 px** — no sideways scrolling (admin menu becomes a swipeable bar); sign-in box and playing station checked on a phone; tap targets enlarged (breadcrumbs, “Show” password, file pickers, checkboxes); on computers (960–1366 px) the admin menu stays beside the page |
| Real phones | ✅ | `tests/real_phone_check.py`: Galaxy S9+, Galaxy S5, Pixel 5, iPhone SE, iPhone 13, normal and 130 % text size — no sideways scrolling on 10 pages; the open menu scrolls on its own, stops above the player and keeps the page still; tapping outside closes it; Back returns to the same place in a list; no blur effects on phones (smoother scrolling); text boxes 16 px so iPhones don't zoom in |
| Station & genre pages (v1.5) | ✅ | 8 genre pages (naat, qawwali, ghazal, sufi, punjabi, old songs, quran, news); every listed station has its own page (title, description, canonical, RadioStation schema, similar stations, removal link); short/wrong links redirect to the full address; unknown 404, removed 410; sitemap lists genres and station pages; browser: clicking a station plays it **and** opens its page while the music keeps playing, Back returns; phones 360/412 px and 5 phone profiles without sideways scrolling |
| Partner (affiliate) offers (v1.5) | ✅ | owner-only admin page; https links only (http/javascript refused); shown with “Affiliate” label and `rel="sponsored nofollow"`; per-page placement; hide/show/remove; master switch; `/go/<id>` redirects only to stored links and counts clicks (shown in admin); Amazon disclosure in the Disclaimer; /deals page |
| Low-database mode (v1.4) | ✅ | database connections counted: a visitor opening 4 pages, sending a page view, starting a station and 3 minutes of listening opened the database **0** times; queued rows written when the admin opens Live now (listener shown from memory with country); listening time recorded on stop; queue kept and retried when the database is unreachable; memory rate limits; on automatically with EPHEMERAL_STORAGE=1; running server: 5 page views stayed in memory, then written together at the batch time; all browser suites pass in this mode (33/33, 16/16, phones 0 problems) |
| Remove a station (v1.3) | ✅ | `tests/e2e_admin_tools.py` (16/16): 🚫 shown only to admins; one click hides the station everywhere (lists, search, API); a copy saved in a visitor's browser is refused and forgotten; same stream under another id refused; restore from Admin → Stations; removal by stream address; owner removal-request page |
| 2-step sign-in (v1.3) | ✅ | RFC 6238 reference codes; QR code drawn in the browser and decoded back to a valid `otpauth://` link; wrong code rejected; codes never reused; recovery code works once; secret stored encrypted; admin can switch it off for a user; phone layout of the code step |
| Own domain redirect (v1.3) | ✅ | with SITE_URL = own domain, `*.onrender.com` answers 301 to the same path on the domain (`/ping` excluded); iPhone home-screen tags present |
| Updates reach browsers | ✅ | CSS/JS URLs carry a hash of the file contents, so a browser can never keep an old `player.js` after an update |
| Free hosting mode (Render free + Neon) | ✅ | QR image still served after the disk copy is deleted (database copy); app-file uploads refused with a GitHub Releases hint when `EPHEMERAL_STORAGE=1`; admin created once from `ADMIN_EMAIL`/`ADMIN_PASSWORD` (weak password ignored, existing account never changed); `/ping` answers without the database; `$PORT`/`$WEB_CONCURRENCY` expand in the start command |
| Browser console | ✅ | no JavaScript or CSP errors during the browser run |

## Not tested here (needs your server, accounts or internet)

* **Real Radio Browser data and real station streams** — this build environment has no internet access, so tests used built-in demo stations and a local test tone. On a normal internet connection the site fetches the real directory.
* Real Google AdSense ads (needs an approved AdSense account and a live domain).
* Real SMTP delivery (tests capture the email instead of sending it).
* Docker image, Caddy HTTPS and Render deployment (no Docker daemon here; `docker compose config` validated).
* The gunicorn `worker_exit` hook (`gunicorn.conf.py`) that saves the queue on shutdown (gunicorn could not be installed here; the idle-flush before the free server sleeps was tested instead)
* Gunicorn and PostgreSQL at runtime through psycopg (packages could not be installed in this build environment; the start command was checked with Flask's server) (queries were validated with `PREPARE`; runtime tests used SQLite).
* Windows `START-WINDOWS.bat` on a real Windows PC (the Python launcher it calls was tested on Linux).
* Lighthouse scores (tool not available here) — run `npx lighthouse https://your-domain` after launch.
