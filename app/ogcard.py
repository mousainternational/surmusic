"""A small share picture for each station (what WhatsApp, Facebook and others show next to the link)."""
import io
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

STATIC = Path(__file__).parent / "static"
W, H = 1200, 630
_cache = {}


def _font(name, size):
    return ImageFont.truetype(str(STATIC / "fonts" / name), size)


def _plain(text):
    """Only letters the card font can draw (Latin); anything else would show empty boxes."""
    return bool(text) and all(ord(c) < 0x250 for c in text)


def _wrap(draw, text, font, width, lines=9):
    words, out, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= width or not cur:
            cur = t
        else:
            out.append(cur)
            cur = w
    out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1].rstrip(" .,-") + "…"
    return out


def render(name, place=""):
    key = (name, place)
    if key in _cache:
        return _cache[key]
    img = Image.new("RGB", (W, H), (13, 11, 22))
    d = ImageDraw.Draw(img)
    for y in range(H):                                   # soft dark gradient
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(30 - 17 * t), int(14 + -3 * t), int(44 - 22 * t)))
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse([-260, -320, 560, 330], fill=(110, 34, 72))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    img = ImageChops.add(img, glow)
    d = ImageDraw.Draw(img)
    logo = Image.open(STATIC / "img" / "logo-512.png").convert("RGBA").resize((150, 150))
    img.paste(logo, (80, 70), logo)
    d.text((255, 92), "Sur Music", font=_font("Poppins-Bold.woff", 52), fill=(245, 242, 255))
    d.text((257, 156), "Free live radio", font=_font("Poppins-Medium.woff", 30), fill=(255, 150, 90))
    title = name if _plain(name) else "Live radio"
    size = 92
    while size > 44:
        f = _font("Poppins-Bold.woff", size)
        lines = _wrap(d, title, f, W - 160)
        if len(lines) <= 2 and all(d.textlength(x, font=f) <= W - 160 for x in lines):
            break
        size -= 6
    f = _font("Poppins-Bold.woff", size)
    lines = _wrap(d, title, f, W - 160, 2)
    y = 250
    for line in lines:
        d.text((80, y), line, font=f, fill=(255, 255, 255))
        y += int(size * 1.2)
    sub = ("▶  Listening live now" + (f"  ·  {place}" if _plain(place) else ""))
    d.text((80, y + 14), sub.replace("▶", ">"), font=_font("Poppins-Medium.woff", 34), fill=(53, 232, 168))
    d.text((80, H - 76), "surmusicradio.com", font=_font("Poppins-Medium.woff", 32), fill=(200, 194, 224))
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    data = buf.getvalue()
    if len(_cache) > 300:
        _cache.pop(next(iter(_cache)))
    _cache[key] = data
    return data


UUID_RE = re.compile(r"^[0-9a-fA-F-]{8,64}$")
