"""Small helpers: slugs, validation and safe Markdown rendering."""
import re
import unicodedata
from urllib.parse import urlparse

import markdown as md
from markupsafe import Markup

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_HREF_RE = re.compile(r'(href|src)="([^"]*)"')


def slugify(text, max_len=80):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].strip("-") or "item"


def valid_email(value):
    return bool(value) and len(value) <= 254 and bool(EMAIL_RE.match(value))


def valid_url(value, https_only=False):
    if not value or len(value) > 2048:
        return False
    try:
        u = urlparse(value)
    except ValueError:
        return False
    schemes = ("https",) if https_only else ("http", "https")
    return u.scheme in schemes and bool(u.netloc)


def _safe_attr(match):
    attr, val = match.group(1), match.group(2)
    low = val.strip().lower()
    if low.startswith(("http://", "https://", "mailto:", "/", "#")):
        return f'{attr}="{val}"'
    return f'{attr}="#"'


def render_markdown(text):
    """Markdown → HTML with all raw HTML escaped and only safe link schemes allowed."""
    if not text:
        return Markup("")
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = md.markdown(escaped, extensions=["sane_lists", "tables"], output_format="html")
    html = _HREF_RE.sub(_safe_attr, html)
    html = html.replace("<a href=", '<a rel="nofollow noopener" href=')
    return Markup(html)


def plain_text(text, limit=160):
    text = re.sub(r"[#*_`>\[\]()!-]", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def human_size(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def clamp_int(value, lo, hi, default):
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))
