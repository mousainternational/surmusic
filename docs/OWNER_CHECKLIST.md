# Sur Music — owner checklist before launch

Nothing below was invented. Each item has a setting; the related feature stays hidden or shows an honest message until you complete it.

| # | Item | Where | Why |
| --- | --- | --- | --- |
| 1 | **Domain** for Sur Music (check availability, e.g. a `.pk` or `.com` name) | DNS A record → server IP; `SITE_URL`, `DOMAIN` in `.env` | Address, HTTPS, canonical URLs |
| 2 | **Hosting**: VPS with Docker, or Render paid plan with disk | — | Where the site runs |
| 3 | **Complete contact email** — `mousainternational.gami.com` has no `@`, so it was not published | Admin → Settings → General | Contact, footer, schema |
| 4 | **SMTP account** (Brevo / Zoho / Gmail app password) | `.env` `SMTP_*` | Password reset, email confirmation, contact emails |
| 5 | **Admin account** (12+ character password) | `START-WINDOWS.bat` / `flask --app wsgi create-admin` | Admin panel |
| 6 | **MISH website address** (after you deploy it) | Admin → Settings → General → Company website | “A product of MISH” links |
| 7 | **JazzCash**: holder name + official QR from the app; number `03217913507` is pre-filled — confirm; tick verified + enabled | Admin → Donations | Donate page |
| 8 | **NayaPay**: same as above | Admin → Donations | Donate page |
| 9 | **International**: Wise link/details after confirming Wise allows donations for your account | Admin → Donations | Donate page |
| 10 | **Google AdSense**: apply after launch; then publisher ID + 4 ad unit IDs; enable the consent message in AdSense → Privacy & messaging | Admin → Ads | Earnings |
| 11 | **Android APK** (signed `SurMusic-1.0.0.apk` from GitHub Actions) and **Chrome extension** zip or Chrome Web Store link | Admin → App downloads | Download page |
| 12 | **Patreon / support link** (optional) | Admin → Settings → General | Support link |
| 13 | **Legal review** of Privacy, Terms, Cookie Policy, Disclaimer, Donation Disclaimer, Refund policy (Pakistani law, AdSense policies, payment providers) | Admin → Settings → Policies; Admin → Donations | Compliance |
| 14 | **Google Search Console**: verification code, then submit `/sitemap.xml` | Admin → Settings → SEO | Indexing |
| 15 | **Social links** (optional) | Admin → Settings → Social | Footer, schema |
| 16 | **Backups** schedule | README §8 | Recovery |
| 17 | **City-level visitor locations**: automatic — the free DB-IP City Lite database downloads itself monthly; keep the “IP Geolocation by DB-IP” footer credit (licence) | nothing to do (`GEOIP_AUTO=0` turns it off) | Admin shows cities |
| 18 | **Listening is free for everyone** (default). Switch on “sign in to listen” only if you want accounts | Admin → Settings → Accounts | More listeners / promotion vs. more sign-ups |
| 20 | **Turn on 2-step sign-in** for your admin account and keep the 10 recovery codes on paper | My account → 2-step sign-in | Admin panel safe even if your password leaks |
| 21 | **Station removal requests**: answer within 48 hours, remove with 🚫 | Admin → Messages, station lists | Avoid complaints / strikes |
| 19 | **Privacy policy** now describes sign-in/listening/location tracking — review it before launch | Admin → Settings → Policies | Legal transparency |

## Notes
* Sponsored stations: agree terms in writing and keep the “Sponsored” label (required for honesty and ad policies).
* Never click your own ads or ask others to — Google closes accounts for invalid clicks.
* Keep the Android signing key safe (see the Android project README).
