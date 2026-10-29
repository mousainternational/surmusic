"""SEO helpers: page metadata, canonical URLs and JSON-LD."""
from flask import current_app, request, url_for

from .settings import get_settings, page_seo
from .util import plain_text


def absolute(path):
    return current_app.config["SITE_URL"] + path


def media_url(name, absolute_url=False):
    if not name:
        return None
    path = url_for("public.media", name=name)
    return absolute(path) if absolute_url else path


def build_meta(title=None, description=None, page=None, noindex=False, canonical_path=None):
    s = get_settings()
    override = page_seo(page) if page else {}
    title = override.get("title") or title or s["seo_default_title"]
    description = override.get("description") or description or s["seo_default_description"]
    if title != s["seo_default_title"] and s["site_name"] not in title:
        title = f"{title} | {s['site_name']}"
    path = canonical_path if canonical_path is not None else request.path
    img = media_url(s["seo_og_image"], True) if s.get("seo_og_image") else \
        absolute(url_for("static", filename="img/og-default.png"))
    return {
        "title": title,
        "description": plain_text(description, 160),
        "canonical": absolute(path),
        "image": img,
        "noindex": noindex,
        "site_name": s["site_full_name"],
        "google_verification": s.get("google_site_verification", ""),
    }


def organization_ld():
    s = get_settings()
    data = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": s["owner_name"],
        "alternateName": s["owner_brand"],
        "logo": absolute(url_for("static", filename="img/mish-logo-512.png")),
    }
    if s.get("owner_url"):
        data["url"] = s["owner_url"]
    same_as = [s[k] for k in ("social_facebook", "social_youtube", "social_x", "social_instagram", "social_tiktok")
               if s.get(k)]
    if same_as:
        data["sameAs"] = same_as
    if s.get("contact_email"):
        data["email"] = s["contact_email"]
    return data


def website_ld():
    s = get_settings()
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": s["site_full_name"],
        "alternateName": s["site_name"],
        "url": absolute("/"),
        "publisher": {"@type": "Organization", "name": s["owner_name"]},
        "potentialAction": {
            "@type": "SearchAction",
            "target": absolute("/search") + "?q={search_term_string}",
            "query-input": "required name=search_term_string",
        },
    }


def webapp_ld():
    s = get_settings()
    return {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": s["site_full_name"],
        "url": absolute("/"),
        "applicationCategory": "MultimediaApplication",
        "operatingSystem": "Any (web browser), Android, Chrome",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "author": {"@type": "Organization", "name": s["owner_name"]},
    }


def breadcrumb_ld(items):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": absolute(p)}
                            for i, (n, p) in enumerate(items)],
    }


def faq_ld(markdown_text):
    """Build FAQPage data from '### Question' blocks."""
    items, q, answer = [], None, []
    for line in (markdown_text or "").splitlines():
        if line.startswith("### "):
            if q:
                items.append((q, " ".join(answer).strip()))
            q, answer = line[4:].strip(), []
        elif q and line.strip():
            answer.append(line.strip())
    if q:
        items.append((q, " ".join(answer).strip()))
    if not items:
        return None
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": qq,
                        "acceptedAnswer": {"@type": "Answer", "text": plain_text(a, 500)}} for qq, a in items],
    }


def station_ld(st, path):
    """schema.org RadioStation for a station page."""
    data = {"@context": "https://schema.org", "@type": "RadioStation", "name": st.get("name", ""),
            "url": absolute(path)}
    if st.get("favicon"):
        data["logo"] = st["favicon"]
    if st.get("country"):
        data["areaServed"] = st["country"]
    if st.get("tags"):
        data["keywords"] = st["tags"]
    return data

