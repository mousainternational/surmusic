"""Editable site settings (stored in the `settings` table) with safe defaults.

Policy texts are starting drafts. The owner must review them for Pakistani law, Google AdSense
policies and payment-provider rules before launch.
"""
import json
import re

from flask import g

from .db import get_db

ABOUT_MD = """\
**Sur Music Player & Radio** is a free live-radio player made by **Mousa International Software House (MISH)**.

Listen to Bollywood, Lollywood (Pakistani) and Hollywood music from radio stations around the world — in your browser, in our Chrome extension, or in our Android app.

We do not host or sell songs. Every station is a public live stream broadcast by its owner and listed in the open Radio Browser directory.
"""

PRIVACY_MD = """\
Sur Music is run by Mousa International Software House ("MISH", "we"). This policy explains what we collect and why.

### Accounts (optional)

If you sign up we store your email address, display name, a securely hashed password (we never see or store your actual password), your favourite stations and your recently played stations. You can delete your account and all of this data at any time from **My account**.

### Listening and activity

Listening is free and needs no account. To run, secure and improve Sur Music we record:

* **Sign-ins and account actions** — time, approximate location (city, region, country), device type, operating system and browser. This also helps us spot attempts to break into your account; you can see your own recent sign-ins under **My account**.
* **Listening** — which station was played, when, for how long, and the same approximate location and device details (for visitors without an account too, counted anonymously).
* **Page visits** — page address, approximate location and device type, counted anonymously.

Approximate location is worked out from your IP address using a database stored on our own server (IP geolocation by DB-IP, https://db-ip.com). **We do not store your IP address** — only a one-way keyed fingerprint used for security and to count unique visitors. This information is visible only to the Sur Music administrators.

We keep page visits for 180 days and account and listening activity for 365 days. When you delete your account, your activity is kept only as anonymous statistics with no link to you.

When you press play, your browser connects directly to the radio station's server, which can see your IP address like any website.

### Contact form

Your name, email address and message, so we can reply.

### Cookies

* **Essential cookie:** keeps you signed in and protects forms against attacks. It is always on.
* **Preferences:** your volume, theme and (when signed out) favourites are saved in your own browser's local storage.
* **Advertising:** when ads are switched on, Google AdSense and its partners may use cookies and similar technologies to show and measure ads, including personalised ads where you have agreed to them. Visitors in the EEA, UK and Switzerland are asked for consent through Google's consent message. Learn more at https://policies.google.com/technologies/ads and manage ad personalisation at https://adssettings.google.com.

### Security

Passwords are hashed with scrypt. Visitor IP addresses are stored only as one-way keyed hashes for spam and abuse protection.

### Sharing

We do not sell personal data. Advertising partners receive data only as described above. We share data with authorities only when the law requires it.

### Children

Sur Music is not directed at children under 13, and we do not knowingly collect their data.

### Your rights

You can view, correct, download or delete your data from **My account**, or ask us through the Contact page.
"""

TERMS_MD = """\
By using Sur Music you agree to these terms.

### The service

Sur Music plays public live radio streams listed in the open Radio Browser directory. We do not own, host, record or control the stations or their content, and stations may go offline at any time.

### Accounts

Keep your password secret. You are responsible for activity on your account. We may suspend accounts that abuse the service, attack the website or break the law.

### Acceptable use

Do not record, rebroadcast or resell streams, scrape the website aggressively, attempt to break its security, or interfere with ads (for example by clicking ads you are not interested in).

### Advertising

The website may show ads from Google AdSense and other partners. Ads are labelled "Advertisement" and are provided by third parties.

### No warranty

The service is provided "as is", without warranty of any kind. To the extent permitted by law, we are not liable for any loss arising from its use.

### Governing law

These terms are governed by the laws of Pakistan.
"""

DISCLAIMER_MD = """\
Sur Music Player & Radio is an independent radio player developed and published by **Mousa International Software House**. It does not host, upload, download, record or store any songs, music or audio files. All audio is streamed live and directly from third-party radio stations that are publicly listed in the open Radio Browser directory (radio-browser.info).

All songs, music, station names and logos belong to their respective owners, broadcasters and record labels. We are not affiliated with, endorsed by, or sponsored by any radio station, film industry, music label or artist. The words "Bollywood", "Lollywood" and "Hollywood" are used only to describe music genres.

The "Sur Music Player & Radio" name, logo, design and source code are the property of Mousa International Software House.

Stations marked **Sponsored** are paid placements. Advertisements are provided by third parties and are not endorsements.

**Station owners:** if you own or manage a station and do not want it on Sur Music, send a removal request through the contact page (link “Station owners: remove a station” at the bottom of every page). We remove it, usually within 48 hours.
"""

DONATION_DISCLAIMER_MD = """\
- **Donations are voluntary.** They support development, hosting and maintenance of Sur Music and other MISH software.
- **A donation is not a purchase.** It does not buy a subscription, ad-free access or any specific service.
- **Verify before you send.** Check the account holder name in your payment app before confirming a transfer.
- **Fees and delays.** JazzCash, NayaPay, Wise and banks may charge fees, apply exchange rates or delay transfers.
- **Confirmation is manual.** Scanning a QR code or clicking a button here does not confirm a payment. We confirm donations from our own account records.
- **Not a charity.** Donations are not tax-deductible.
"""

COOKIES_MD = """\
| Name | Type | Purpose | Duration |
| --- | --- | --- | --- |
| surmusic_session | Essential | Keeps you signed in and protects forms (CSRF) | Browser session, or 30 days with "Remember me" |
| Local storage: volume, theme, favourites | Preference | Remembers your settings in this browser | Until you clear it |
| Google AdSense cookies (when ads are on) | Advertising | Show, limit and measure ads; personalised ads only with consent | Set by Google — see Google's policy |

You can delete cookies in your browser settings at any time. Blocking the essential cookie stops sign-in from working.
"""

FAQ_MD = """\
### Is Sur Music free?

Yes. The website, Chrome extension and Android app are free. Ads and voluntary donations keep it running.

### Why does a station not play?

Stations are run by their owners and sometimes go offline. Press **Next** to try another. In the browser we only list stations that stream over secure HTTPS; the Android app and Chrome extension can play more stations.

### Do I need an account?

No — listening is free, no account needed. A free account is optional: it keeps your favourite stations and recently played list on every device.

### Can I download songs?

No. Sur Music plays live radio only. We do not host, record or provide song downloads.

### Who makes Sur Music?

Mousa International Software House (MISH).
"""

REFUND_POLICY_MD = """\
Donations are voluntary and are generally not refundable. If you sent money by mistake (wrong amount or duplicate payment), contact us within 7 days with the transaction ID, and we will review the request according to applicable law and the payment provider's rules.
"""

DEFAULTS = {
    # identity
    "site_name": "Sur Music",
    "site_full_name": "Sur Music Player & Radio",
    "owner_name": "Mousa International Software House",
    "owner_brand": "MISH",
    "owner_url": "",
    "tagline": "Live Bollywood, Lollywood & Hollywood radio — free.",
    "hero_title": "Live desi & English radio, free in your browser",
    "hero_subtitle": "Bollywood hits, Pakistani songs, ghazals, qawwali and Hollywood top 40 — thousands of live stations. No download needed.",
    "about_md": ABOUT_MD,
    "contact_email": "",
    "contact_email_unverified": "mousainternational.gami.com",
    "support_url": "",
    "social_facebook": "", "social_youtube": "", "social_x": "", "social_instagram": "", "social_tiktok": "",
    # accounts
    "signup_enabled": "1",
    "play_requires_login": "0",
    "require_email_verification": "0",
    # SEO / analytics
    "seo_default_title": "Sur Music — Live Bollywood, Lollywood & Hollywood Radio",
    "seo_default_description": "Listen free to live Bollywood, Lollywood (Pakistani) and Hollywood radio. Hindi, Urdu, Punjabi and English music stations — by Mousa International Software House.",
    "seo_og_image": "",
    "google_site_verification": "",
    "page_seo": "{}",
    "analytics_provider": "none",
    "analytics_domain": "",
    # ads
    "ads_enabled": "0",
    "adsense_client": "",
    "ad_slot_top": "",
    "ad_slot_list": "",
    "ad_slot_side": "",
    "ad_slot_footer": "",
    "ads_txt_extra": "",
    # stations
    "sponsored_stations": "[]",
    "blocked_stations": "[]",
    # policies
    "privacy_md": PRIVACY_MD,
    "terms_md": TERMS_MD,
    "disclaimer_md": DISCLAIMER_MD,
    "donation_disclaimer_md": DONATION_DISCLAIMER_MD,
    "cookies_md": COOKIES_MD,
    "faq_md": FAQ_MD,
    "policies_updated": "2026-10-28",
    # donations (same details as the MISH website)
    "donation_purpose_md": "Your support pays for servers, development and new features for Sur Music and other free software from Mousa International Software House.",
    "refund_policy_md": REFUND_POLICY_MD,
    "jazzcash_enabled": "0", "jazzcash_verified": "0",
    "jazzcash_holder": "", "jazzcash_number": "03217913507", "jazzcash_title": "", "jazzcash_qr": "",
    "jazzcash_instructions": "Open the JazzCash app → Send Money → Mobile Account, or scan the QR code. Check the account holder name before you confirm.",
    "nayapay_enabled": "0", "nayapay_verified": "0",
    "nayapay_holder": "", "nayapay_details": "03217913507", "nayapay_qr": "",
    "nayapay_instructions": "Open the NayaPay app → Send, enter the NayaPay ID or phone number, or scan the QR code. Check the account holder name before you confirm.",
    "wise_enabled": "0", "wise_verified": "0",
    "wise_holder": "", "wise_link": "", "wise_details": "", "wise_currencies": "",
    "wise_instructions": "Use the Wise payment link, or send a bank transfer to the details below.",
    "wise_fee_note": "Your bank, Wise or intermediary banks may charge transfer fees, and exchange rates may differ. International transfers can take 1–5 business days.",
}

BOOL_KEYS = {k for k in DEFAULTS if k.endswith(("_enabled", "_verified"))} | {"require_email_verification",
                                                                          "play_requires_login"}
PAGE_KEYS = ["home", "bollywood", "lollywood", "hollywood", "search", "favorites", "download", "donate",
             "about", "contact", "faq", "privacy", "terms", "disclaimer", "donation-disclaimer", "cookies"]
ADSENSE_CLIENT_RE = re.compile(r"^ca-pub-\d{10,20}$")
AD_SLOT_RE = re.compile(r"^\d{6,15}$")


def get_settings():
    if "settings" not in g:
        data = dict(DEFAULTS)
        for row in get_db().all("SELECT key, value FROM settings"):
            data[row["key"]] = row["value"]
        g.settings = data
    return g.settings


def save_settings(values):
    g.pop("blocked_sets", None)
    db = get_db()
    for key, value in values.items():
        if key not in DEFAULTS:
            continue
        db.execute("DELETE FROM settings WHERE key = ?", (key,))
        db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    db.commit()
    g.pop("settings", None)


def flag(key):
    return get_settings().get(key) == "1"


def ads_active():
    s = get_settings()
    return s.get("ads_enabled") == "1" and bool(ADSENSE_CLIENT_RE.match(s.get("adsense_client", "")))


def page_seo(page):
    try:
        data = json.loads(get_settings().get("page_seo") or "{}")
    except ValueError:
        data = {}
    return data.get(page, {}) if isinstance(data, dict) else {}


def sponsored_stations():
    try:
        rows = json.loads(get_settings().get("sponsored_stations") or "[]")
    except ValueError:
        return []
    return rows if isinstance(rows, list) else []


def blocked_stations():
    """Stations the owner removed (for example after a station owner's request)."""
    try:
        rows = json.loads(get_settings().get("blocked_stations") or "[]")
    except ValueError:
        return []
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def stream_key(url):
    """Comparable form of a stream address: host + path, no scheme, no trailing slash, lower-case."""
    from urllib.parse import urlsplit
    try:
        u = urlsplit((url or "").strip())
    except ValueError:
        return ""
    if not u.netloc:
        return ""
    return (u.netloc.lower() + u.path.rstrip("/").lower() + (("?" + u.query) if u.query else ""))


def _blocked_sets():
    if "blocked_sets" not in g:
        rows = blocked_stations()
        g.blocked_sets = ({r.get("uuid") for r in rows if r.get("uuid")},
                          {stream_key(r.get("url")) for r in rows if r.get("url")} - {""},
                          {(r.get("name") or "").strip().lower() for r in rows if r.get("match_name")} - {""})
    return g.blocked_sets


def is_blocked(st):
    if not isinstance(st, dict):
        return False
    uuids, urls, names = _blocked_sets()
    return (st.get("uuid") in uuids or (st.get("url") and stream_key(st.get("url")) in urls)
            or (st.get("name") or st.get("station_name") or "").strip().lower() in names)


def without_blocked(stations):
    if not blocked_stations():
        return stations
    return [s for s in stations if not is_blocked(s)]


def donation_method(name):
    """Public data for a donation method, or None if it is not ready to show."""
    s = get_settings()
    if s.get(f"{name}_enabled") != "1" or s.get(f"{name}_verified") != "1":
        return None
    if name == "jazzcash":
        if not (s["jazzcash_holder"] and (s["jazzcash_number"] or s["jazzcash_qr"])):
            return None
        return {"holder": s["jazzcash_holder"], "number": s["jazzcash_number"], "title": s["jazzcash_title"],
                "qr": s["jazzcash_qr"], "instructions": s["jazzcash_instructions"]}
    if name == "nayapay":
        if not (s["nayapay_holder"] and (s["nayapay_details"] or s["nayapay_qr"])):
            return None
        return {"holder": s["nayapay_holder"], "details": s["nayapay_details"], "qr": s["nayapay_qr"],
                "instructions": s["nayapay_instructions"]}
    if name == "wise":
        if not (s["wise_holder"] and (s["wise_link"] or s["wise_details"])):
            return None
        return {"holder": s["wise_holder"], "link": s["wise_link"], "details": s["wise_details"],
                "currencies": s["wise_currencies"], "instructions": s["wise_instructions"],
                "fee_note": s["wise_fee_note"]}
    return None


def setup_warnings(smtp_ready):
    s = get_settings()
    w = []
    if not s.get("contact_email"):
        w.append("Contact email is not set. The address you supplied (“%s”) has no @ sign — enter the complete, "
                 "verified address in Settings → General." % s.get("contact_email_unverified", ""))
    if not smtp_ready:
        w.append("Email (SMTP) is not configured, so password-reset and verification emails cannot be sent. "
                 "Set the SMTP_* values in .env.")
    if not ads_active():
        w.append("Ads are off. After Google AdSense approves the site, enter your publisher ID (ca-pub-…) and ad "
                 "unit IDs in Ads, then switch ads on.")
    for name, label in (("jazzcash", "JazzCash"), ("nayapay", "NayaPay"), ("wise", "Wise")):
        if donation_method(name) is None:
            w.append(f"{label} donations are hidden until you add the holder name, upload the official QR or "
                     f"details, tick “verified” and enable it.")
    from flask import current_app
    from . import geo, twofa
    from .security import current_user
    me = current_user()
    if me and me["role"] == "admin" and not twofa.is_enabled(me["id"]):
        w.append("Protect the admin panel: turn on 2-step sign-in (My account → 2-step sign-in). Then even a "
                 "stolen password is not enough to get in.")
    if not geo.available():
        cfg = current_app.config
        st = geo.read_status(cfg.get("GEOIP_MMDB", "")) if cfg.get("GEOIP_MMDB") else {}
        if not cfg.get("GEOIP_AUTO"):
            w.append("Visitor cities are off (GEOIP_AUTO=0): only countries are shown.")
        elif st.get("state") == "failed":
            w.append("The free visitor-city database (DB-IP) could not be downloaded yet — it is retried every "
                     "3 hours. Only countries are shown until then. Details: " + st.get("error", "")[:200])
        else:
            w.append("The free visitor-city database (DB-IP, about 120 MB) is downloading in the background. "
                     "Countries are shown now; cities appear when it is ready (a few minutes).")
    return w
