"""Secure storage for software files and images.

* Files are stored outside the web root under random names, so nothing uploaded can run as code.
* Software files: extension allowlist + magic-byte check + size limit + SHA-256 + optional ClamAV scan.
* Images: decoded and re-encoded with Pillow (strips metadata, defeats polyglot files).
"""
import hashlib
import os
import re
import socket
import struct
import uuid

from flask import current_app
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename

Image.MAX_IMAGE_PIXELS = 40_000_000

NAME_RE = re.compile(r"^[a-f0-9]{32}\.[a-z0-9.]{1,12}$")


class UploadError(ValueError):
    pass


def _magic_zip(h, _t):
    return h.startswith(b"PK\x03\x04") or h.startswith(b"PK\x05\x06")


def _starts(sig):
    return lambda h, _t: h.startswith(sig)


def _tar(h, _t):
    return len(h) > 262 and h[257:262] == b"ustar"


def _dmg(_h, tail):
    return b"koly" in tail


# extension -> (check function, download MIME type)
SOFTWARE_TYPES = {
    ".zip": (_magic_zip, "application/zip"),
    ".exe": (_starts(b"MZ"), "application/vnd.microsoft.portable-executable"),
    ".msi": (_starts(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"), "application/x-msi"),
    ".msix": (_magic_zip, "application/msix"),
    ".apk": (_magic_zip, "application/vnd.android.package-archive"),
    ".aab": (_magic_zip, "application/octet-stream"),
    ".jar": (_magic_zip, "application/java-archive"),
    ".7z": (_starts(b"7z\xbc\xaf\x27\x1c"), "application/x-7z-compressed"),
    ".rar": (_starts(b"Rar!\x1a\x07"), "application/vnd.rar"),
    ".gz": (_starts(b"\x1f\x8b"), "application/gzip"),
    ".tgz": (_starts(b"\x1f\x8b"), "application/gzip"),
    ".tar": (_tar, "application/x-tar"),
    ".deb": (_starts(b"!<arch>\n"), "application/vnd.debian.binary-package"),
    ".rpm": (_starts(b"\xed\xab\xee\xdb"), "application/x-rpm"),
    ".appimage": (_starts(b"\x7fELF"), "application/octet-stream"),
    ".dmg": (_dmg, "application/x-apple-diskimage"),
    ".pkg": (_starts(b"xar!"), "application/octet-stream"),
    ".crx": (_starts(b"Cr24"), "application/x-chrome-extension"),
    ".pdf": (_starts(b"%PDF-"), "application/pdf"),
}

IMAGE_KINDS = {
    # kind: (max box, output format)
    "icon": ((512, 512), "PNG"),
    "screenshot": ((1920, 1920), "WEBP"),
    "qr": ((1400, 1400), "PNG"),   # lossless so QR codes stay scannable
    "og": ((1200, 1200), "PNG"),
    "logo": ((800, 800), "PNG"),
}


def storage_path(*parts):
    return os.path.join(current_app.config["STORAGE_DIR"], *parts)


def software_ext(filename):
    name = (filename or "").lower()
    if name.endswith(".tar.gz"):
        return ".tgz"
    return os.path.splitext(name)[1]


def allowed_extensions():
    return sorted(SOFTWARE_TYPES)


# ---------------------------------------------------------------- ClamAV

def clamav_scan(path):
    """Return 'clean', 'infected', 'error' or 'none' (scanner not configured)."""
    host = current_app.config.get("CLAMAV_HOST")
    if not host:
        return "none"
    try:
        with socket.create_connection((host, current_app.config["CLAMAV_PORT"]), timeout=60) as s:
            s.sendall(b"zINSTREAM\0")
            with open(path, "rb") as f:
                while chunk := f.read(64 * 1024):
                    s.sendall(struct.pack("!L", len(chunk)) + chunk)
            s.sendall(struct.pack("!L", 0))
            reply = s.recv(4096).decode(errors="replace")
        if "FOUND" in reply:
            return "infected"
        if reply.strip().rstrip("\0").endswith("OK"):
            return "clean"
        return "error"
    except OSError:
        return "error"


# ---------------------------------------------------------------- software files

def save_software(file_storage):
    original = secure_filename(file_storage.filename or "")
    ext = software_ext(file_storage.filename)
    if not original or ext not in SOFTWARE_TYPES:
        raise UploadError("This file type is not allowed. Allowed: " + ", ".join(allowed_extensions()))

    limit = current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024
    tmp = storage_path("files", f".upload-{uuid.uuid4().hex}")
    sha, size = hashlib.sha256(), 0
    try:
        with open(tmp, "wb") as out:
            while chunk := file_storage.stream.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise UploadError(f"File is larger than {current_app.config['MAX_UPLOAD_MB']} MB.")
                sha.update(chunk)
                out.write(chunk)
        if size == 0:
            raise UploadError("The file is empty.")
        with open(tmp, "rb") as f:
            head = f.read(4096)
            f.seek(max(0, size - 4096))
            tail = f.read(4096)
        check, mime = SOFTWARE_TYPES[ext]
        if not check(head, tail):
            raise UploadError("The file content does not match its extension.")

        scan = clamav_scan(tmp)
        if scan == "infected":
            raise UploadError("Malware scanner flagged this file. Upload rejected.")
        if scan == "error" and current_app.config.get("CLAMAV_REQUIRED"):
            raise UploadError("Malware scanner is unavailable, and scanning is required. Try again later.")

        stored = f"{uuid.uuid4().hex}{ext}"
        os.replace(tmp, storage_path("files", stored))
        os.chmod(storage_path("files", stored), 0o640)
        return {"file_name": stored, "file_original_name": original, "file_size": size,
                "file_sha256": sha.hexdigest(), "scan_status": scan}
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def software_mime(stored_name):
    return SOFTWARE_TYPES.get(software_ext(stored_name), (None, "application/octet-stream"))[1]


# ---------------------------------------------------------------- images

def save_image(file_storage, kind):
    if kind not in IMAGE_KINDS:
        raise UploadError("Unknown image type.")
    data = file_storage.read(current_app.config["MAX_IMAGE_MB"] * 1024 * 1024 + 1)
    if len(data) > current_app.config["MAX_IMAGE_MB"] * 1024 * 1024:
        raise UploadError(f"Image is larger than {current_app.config['MAX_IMAGE_MB']} MB.")
    if not data:
        raise UploadError("The image is empty.")
    import io
    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()
        img = Image.open(io.BytesIO(data))
        if img.format not in ("PNG", "JPEG", "WEBP", "GIF"):
            raise UploadError("Please upload a PNG, JPG, WebP or GIF image.")
        img = ImageOps.exif_transpose(img)
    except UploadError:
        raise
    except Exception as exc:  # Pillow raises many types for broken images
        raise UploadError("This is not a valid image file.") from exc

    box, fmt = IMAGE_KINDS[kind]
    img.thumbnail(box)
    if fmt == "PNG" and img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
        img = img.convert("RGBA")
    if fmt == "WEBP" and img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    name = f"{uuid.uuid4().hex}.{fmt.lower()}"
    import base64
    out = io.BytesIO()
    img.save(out, fmt, **({"quality": 85} if fmt == "WEBP" else {"optimize": True}))
    raw = out.getvalue()
    with open(storage_path("media", name), "wb") as fh:
        fh.write(raw)
    from .db import get_db, utcnow
    get_db().execute("INSERT INTO media_blobs (name, mime, data, created_at) VALUES (?, ?, ?, ?)",
                     (name, IMAGE_MIME[fmt], base64.b64encode(raw).decode("ascii"), utcnow()))
    return name


IMAGE_MIME = {"PNG": "image/png", "WEBP": "image/webp", "JPEG": "image/jpeg", "GIF": "image/gif"}


def media_bytes(name):
    """(bytes, mime) of an uploaded image from the database copy, or None."""
    if not name or not NAME_RE.match(name):
        return None
    import base64
    from .db import get_db
    row = get_db().one("SELECT mime, data FROM media_blobs WHERE name = ?", (name,))
    return (base64.b64decode(row["data"]), row["mime"]) if row else None


def media_path(name):
    if not name or not NAME_RE.match(name):
        return None
    path = storage_path("media", name)
    return path if os.path.isfile(path) else None


def file_path(name):
    if not name or not NAME_RE.match(name):
        return None
    path = storage_path("files", name)
    return path if os.path.isfile(path) else None


def delete_media(name):
    p = media_path(name)
    if p:
        os.remove(p)
    if name and NAME_RE.match(name):
        from .db import get_db
        get_db().execute("DELETE FROM media_blobs WHERE name = ?", (name,))


def delete_file(name):
    p = file_path(name)
    if p:
        os.remove(p)
