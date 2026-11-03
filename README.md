# Sur Music — website

**Sur Music Player & Radio — a product of MISH (Mousa International Software House).**
Live Bollywood, Lollywood and Hollywood radio in the browser, with free accounts, favourites, Google AdSense ads, donations (same JazzCash / NayaPay / Wise setup as the MISH website), app downloads and a full admin panel.

> **Status:** complete source code, tested locally (see `docs/TEST_REPORT.md`). It is **not online yet** — it goes live when you deploy it on a server with your domain (section 4).

---

## Roman Urdu — jaldi shuru karein

### Apne computer par chalana
1. **python.org** se Python install karein (Windows par **"Add python.exe to PATH"** tick karein).
2. Zip extract karein → `surmusic-web` folder mein **`START-WINDOWS.bat`** par double-click (Mac/Linux: `sh START-MAC-LINUX.sh`).
3. Pehli baar yeh **admin email aur password** (12+ characters) poochega — yeh aap khud banate hain.
4. Browser `http://127.0.0.1:8100` par khulega. Admin panel ke liye **Sign in** karein → aap seedha admin dashboard par pohanchenge.

### Internet par live karna
* **Bilkul free:** `docs/FREE_HOSTING.md` — Render (free) + Neon (free database), qadam ba qadam.
* **Behtar (paid, ~$5/mahina):** domain + Docker wala VPS, phir section 4 ke 3 commands.

### Gaana sab ke liye free — account ki zaroorat nahi
Har visitor bina sign in ke foran gaana sun sakta hai. Account sirf optional hai (favourites har device par). Aap phir bhi har visitor ka **mulk, shehar, device, kaunsa station aur kitni der** admin mein dekhte hain — account ho ya na ho ("Guest" likha aata hai).
Kabhi sign-in zaroori karna ho: Admin → Settings → **Accounts** → "Visitors must sign in to play music" tick karein.

### Har station aur har qisam ka apna page
* Kisi station par click → gaana shuru **aur** us station ka apna page khulta hai (`/station/…`), gaana chalta rehta hai. Har page par Google ke liye apna title, tafseel, aur ads ki jagah.
* Qisam ke pages: **/genre/naat, /genre/qawwali, /genre/ghazal, /genre/sufi, /genre/punjabi, /genre/old-songs, /genre/quran, /genre/news**. "Listen by type" chips har list par.
* Sab pages khud `sitemap.xml` mein jate hain (Google ke liye).

### Affiliate / referral links (Amazon, Daraz, AliExpress…)
Admin → **🛍️ Partner offers** → product ka naam, **apna affiliate link** (https), tasveer ka link, qeemat → **Add offer**. Website par "Recommended for you" card "Affiliate" label ke saath dikhta hai (station pages, lists, home) aur **/deals** page par. Har click admin mein ginta hai. Koi khareede to store aap ko commission deta hai.
* Pehle programme mein shamil hon (Amazon Associates, Daraz Affiliate, AliExpress Portals), apna link wahan se banayein.
* "Affiliate" label aur Disclaimer mein likha disclosure na hatayein (Amazon ki shart).

### Free database ko bachana (kam-database mode)
Free hosting par (`EPHEMERAL_STORAGE=1`) website khud **kam-database mode** mein chalti hai: gaana sunte waqt, page dekhte waqt database **nahi jaagta**. "Live now", visitors ki ginti aur hifazati hadd website ki memory mein rehti hai; visitors ka data **15 minute mein ek dafa** ek saath database mein jata hai (admin panel ya My account kholne par foran). Is se Neon ke free ghante bahut der chalte hain.
* Render par `WEB_CONCURRENCY` = **1** rakhein (ek hi process, taa ke sab ki memory ek ho).
* Neon → project → **Settings / Compute** mein compute size **0.25** (max bhi 0.25) rakhein.
* Mahine mein ek dafa Neon dashboard mein **Usage** dekh lein.

### Station hataana (agar koi station maalik shikayat kare)
* Admin ke taur par sign in ho kar website par koi bhi station list kholein. Har station ke saath **🚫** button nazar aayega (sirf aap ko, visitors ko nahi). Dabayein, aur woh station sab ke liye foran hat jayega. Jin logon ne usay browser mein save kiya tha, un ke liye bhi nahi chalega.
* Wapas laana ho: Admin → **Stations (remove / sponsor)** → **Restore**.
* Station maalik har page ke neeche **"Station owners: remove a station"** se request bhejte hain. Request Admin → **Messages** mein aati hai.

### Admin panel ki hifazat — 2-step sign-in (zaroor on karein)
My account → **2-step sign-in** → phone par Google Authenticator se QR scan karein → 6 number ka code likhein → **10 recovery codes** kaghaz par likh lein. Is ke baad sign in ke liye password ke saath phone ka code bhi chahiye hoga.
Phone kho jaye: ek recovery code use karein. Woh bhi na hon: Render → Environment mein `ADMIN_EMAIL` (nayi email) + `ADMIN_PASSWORD` daal kar naya admin banayein, aur Admin → Users se purane account ka "Turn off 2-step" dabayein.

### Admin mein sab nazar aata hai
* **🔴 Live now** — kaun abhi sun raha hai, kaunsa station, kahan se (mulk / shehar), kis device se, kitni der se (har 15 second mein khud update).
* **Activity log** — har sign-up, sign-in, ghalat password, sign-out, station play, kitni der suna, download, favourite, page visit — waqt, jagah aur device ke saath.
* **Analytics** — aaj / 7 / 30 / 90 din / saal: visitors, plays, sign-ups, mulk, shehar, pages, kahan se aaye, devices, browsers.
* **Users** — har member ki "last seen from" jagah; member par click karke us ki poori activity aur kitne minute suna.

### Visitors ka shehar (city) — khud ba khud
Website pehli dafa chalte hi free **DB-IP City Lite** database (~120 MB) khud download karti hai aur har mahine khud naya le leti hai. Aap ko kuch nahi karna. Download hone tak (kuch minute) sirf mulk dikhta hai; Admin dashboard par us waqt note aata hai.
* **Cloudflare tunnel** (`cloudflared`) se aane wale visitors ka asli shehar bhi dikhta hai.
* Band karna ho: `.env` mein `GEOIP_AUTO=0`.
* Footer mein "IP Geolocation by DB-IP" license ki wajah se dikhta hai — isay na hatayein.
* Location andaza hai (aksar shehar sahi, kabhi kabhi qareebi bara shehar). IP address save nahi hota.

### Kamai (Google AdSense)
Website live hone ke baad **adsense.google.com** par apply karein. Approval ke baad Admin → **Ads (AdSense)** mein publisher ID (ca-pub-…) aur ad unit IDs daal kar "Show ads" tick karein. `ads.txt` khud ban jata hai.

---

## 1. Features

**Free listening (sign-in optional, switchable)**
* Everyone can listen without an account (default since v1.2). Optional "sign in to listen" in Admin → Settings → Accounts: pressing play then asks visitors to sign in or create a free account; stream URLs are then hidden from signed-out visitors (encrypted tokens, unlocked only for members via `/api/stream`).

**Owner analytics (privacy-friendly)**
* 🔴 **Live now**: who is listening at this moment — member or guest, station, approximate location, device, minutes — auto-refreshing.
* **Activity log**: sign-ups, sign-ins, failed sign-ins, sign-outs, plays, listening time, downloads, favourites, contact messages, page views — with time, location and device. Per-member page with total minutes listened.
* **Analytics**: visitors, page views, plays, listening minutes, sign-ups, countries, cities, pages, referrers, devices, browsers, systems; today / 7 / 30 / 90 / 365 days.
* Location: city + country from the free DB-IP City Lite database (.mmdb), **downloaded automatically every month** in the background (`GEOIP_AUTO=1`, read with the bundled MaxMind reader in `app/vendor`); until then country from Cloudflare headers or the browser's time zone. Visitors arriving through a Cloudflare Tunnel on the same computer are located by their real IP (`CF-Connecting-IP`, trusted only from 127.0.0.1); other Cloudflare headers only with `TRUST_CF_HEADERS=1`. **No IP addresses are stored**; unique visitors use a keyed hash that changes daily; bots are not counted; page views kept 180 days, other activity 365 days; members see their own recent sign-ins; deleting an account removes the link to its activity.

**Listeners**
* Web radio player in a fixed bar — keeps playing while moving between pages (in-site navigation), next/previous, volume, lock-screen / keyboard media keys (Media Session API).
* Bollywood, Lollywood (Pakistani) and Hollywood pages with server-rendered station lists (fast and indexable), search, popular stations.
* Free accounts: sign up, sign in (“remember me”), forgot/reset password by email, optional email confirmation, favourites and recently played synced to the account, browser favourites moved into the account at sign-in, change password, sign out all devices, download my data, delete account.
* Download page for the Android APK and Chrome extension, Donate page (JazzCash, NayaPay, international), About (with MISH branding), Contact, FAQ, Privacy, Terms, Cookie Policy, Disclaimer, Donation Disclaimer.
* Dark and light themes, mobile-first, installable web-app manifest.

**Owner / admin**
* Low-database mode for free hosting (`app/lowdb.py`): listening, browsing and page views never touch the database; live listeners, visitor counts and rate limits in memory; analytics, plays and history written in one batch every 15 minutes (immediately when the admin panel or My account opens, before the free server sleeps, and on worker exit via `gunicorn.conf.py`); settings, station lists and popular lists cached in memory. On automatically with `EPHEMERAL_STORAGE=1` (or `LOW_DB_MODE=1`); run one process (`WEB_CONCURRENCY=1`, `WEB_THREADS=8`).
* 🚫 Remove any station for everyone with one click (admin-only button on station rows), restore later; station owners' removal-request page.
* Optional 2-step sign-in (authenticator app, QR code, 10 recovery codes; secret stored encrypted); admins can switch it off for a user who lost their phone.
* Own domain: once SITE_URL is your domain, the old *.onrender.com address redirects to it permanently (one site for Google).
* Dashboard with launch checklist, members, plays per day, top stations.
* Users: search, confirm email, sign out, suspend / activate, delete.
* Ads: AdSense publisher ID, four ad placements, automatic `ads.txt`, on/off switch.
* Sponsored stations (paid placements, labelled “Sponsored”).
* App downloads: upload the APK / extension zip (checked and checksummed) or link to a store page.
* Donations (JazzCash / NayaPay QR upload, Wise), messages inbox, site text, SEO per page, policies, social links, Search Console, optional cookie-free analytics, backup & restore, audit log.

## 2. Architecture

Python 3.12+ / Flask, server-rendered Jinja templates with small vanilla-JS enhancements; PostgreSQL in production (SQLite for development); Gunicorn behind Caddy (automatic HTTPS) via Docker Compose; or Render. Station data comes from the open **Radio Browser** directory, fetched by the server and cached in the database. Only HTTPS streams are listed on the website because browsers block insecure audio on secure pages.

```
app/
  __init__.py   app factory, error pages, CLI (create-admin)
  config.py     configuration from environment variables
  db.py         SQLite / PostgreSQL layer + migrations (schema_*.sql)
  security.py   CSRF, rate limits, sessions, roles, audit log, nonce-based CSP
  auth.py       sign up / in / out, email confirmation, password reset, my account
  public.py     pages, station JSON API, favourites, plays, downloads, ads.txt, sitemap, robots, healthz
  admin.py      admin panel
  radio.py      Radio Browser client + cache
  settings.py   editable texts, policies, donation and ad settings
  seo.py        meta tags, canonical URLs, JSON-LD (WebSite, WebApplication, Organization, FAQPage, BreadcrumbList)
  storage.py    upload checks (allowlist, magic bytes, size, SHA-256, optional ClamAV), image re-encoding
  templates/, static/ (css, js/player.js, js/site.js, js/ads.js, logos)
tests/          pytest suite, browser end-to-end test, PostgreSQL check
```

## 3. Run locally (developers)

```bash
pip install -r requirements-dev.txt
cp .env.example .env     # set SECRET_KEY, SITE_URL=http://127.0.0.1:8100, DATABASE_URL=sqlite:///data/surmusic.db,
                         # STORAGE_DIR=data/storage, SESSION_COOKIE_SECURE=0, TRUSTED_PROXIES=0
flask --app wsgi create-admin
flask --app wsgi run --port 8100
python -m pytest
```

## 4. Deploy (Linux VPS with Docker — recommended)

1. Point your domain's **A record** to the server IP.
2. Install Docker: `curl -fsSL https://get.docker.com | sh`
3. Copy this folder to the server, then:
   ```bash
   cp .env.example .env
   nano .env      # SECRET_KEY, SITE_URL=https://your-domain, DOMAIN=your-domain, POSTGRES_PASSWORD, SMTP_*
   docker compose up -d --build
   docker compose exec web flask --app wsgi create-admin
   ```
4. Open `https://your-domain/healthz` → `{"status": "ok"}`. Sign in at `/login` with the admin account.

**Render free + Neon free:** see `docs/FREE_HOSTING.md` (`render-free.yaml`; admin from `ADMIN_EMAIL`/`ADMIN_PASSWORD` because the free plan has no shell; images kept in the database; app files as links; `/ping` health check that does not wake the database).

**Render paid:** push to GitHub → Render → New + → Blueprint (uses `render.yaml`: web service, PostgreSQL, disk). Set `SITE_URL` and SMTP values; run `flask --app wsgi create-admin` in the Shell. Disks need a paid instance.

**Hosting the MISH website and Sur Music on one server:** give each its own folder and domain (for example `mish.pk` and `surmusic.pk`), and add both domains to one Caddyfile pointing at the two `web` containers.

## 5. Email

Password reset, email confirmation and contact-form notifications need SMTP (Brevo, Zoho, Mailgun or a Gmail app password). Without it the site still works; the reset page says email is not available yet, and contact messages are stored in Admin → Messages.

## 6. Google AdSense

1. Site online on your domain with HTTPS and real visitors. 2. Apply at adsense.google.com. 3. After approval enter the **publisher ID** and **ad unit slot IDs** in Admin → Ads, tick *Show ads*. 4. In AdSense → **Privacy & messaging**, enable the GDPR consent message (required for EEA/UK/Swiss visitors). `ads.txt` is generated automatically. Ads are never shown in the admin panel or account pages, and never inside the player bar. Do not click your own ads.

## 7. Security

Scrypt password hashing (10+ characters, common passwords rejected) · login rate limit + account lockout · sessions rotated on login, “sign out everywhere”, admin sessions expire after 8 hours · CSRF tokens on every form and API call + Origin check · per-request **nonce Content-Security-Policy** (stricter when ads are off), HSTS, X-Frame-Options, nosniff · parameterised SQL · Markdown rendered with HTML escaped · upload allowlist + magic-byte check + random names + private storage · rate limits on sign-up, login, reset, contact, search, plays, downloads · honeypot fields · open-redirect protection · single-use, time-limited reset links · visitor IPs stored only as keyed hashes · no secrets in source code.

## 8. Backups

Admin → Backup (JSON, includes members — keep it private), or `docker compose exec db pg_dump -U surmusic surmusic > backup.sql`; plus the `storage` volume (APK, images). See the MISH README for the volume command.

## 9. Testing

`python -m pytest` (82 tests). Browser test: start the server with `RADIO_DEMO=1` and an admin `admin@example.com` / `demo-password-123`, then `MISH_BASE=http://127.0.0.1:8100 python tests/e2e_browser.py`. PostgreSQL check: `PGCHECK_DSN="host=… user=… dbname=…" python tests/pg_check.py`.
