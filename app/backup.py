"""Database backup (JSON export) and restore.

User accounts ARE exported (with password hashes, never plain passwords) so a restore brings
members back; keep backup files private. Rate-limit counters and the station cache are skipped.
Activity/location records are included (they contain no IP addresses).
Uploaded files live in STORAGE_DIR and are backed up separately (see README).
"""
import json

from .db import get_db, utcnow

# Order matters for foreign keys (parents first).
BACKUP_TABLES = ["settings", "users", "favorites", "history", "apps", "plays", "events", "messages", "audit_log", "media_blobs"]
BACKUP_FORMAT = "surmusic-backup-v1"


def export_data():
    db = get_db()
    data = {"format": BACKUP_FORMAT, "created_at": utcnow(), "tables": {}}
    for t in BACKUP_TABLES:
        data["tables"][t] = db.all(f"SELECT * FROM {t}")
    return json.dumps(data, ensure_ascii=False, indent=1, default=str)


def _columns(db, table):
    if db.pg:
        rows = db.all("SELECT column_name FROM information_schema.columns WHERE table_name = ?", (table,))
        return {r["column_name"] for r in rows}
    return {r["name"] for r in db.all(f"PRAGMA table_info({table})")}


def restore_data(raw):
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ValueError("Backup file is not valid JSON.") from exc
    if not isinstance(data, dict) or data.get("format") != BACKUP_FORMAT or not isinstance(data.get("tables"), dict):
        raise ValueError("This is not a Sur Music backup file.")
    db = get_db()
    counts = {}
    try:
        for t in reversed(BACKUP_TABLES):
            db.execute(f"DELETE FROM {t}")
        for t in BACKUP_TABLES:
            rows = data["tables"].get(t, [])
            if not isinstance(rows, list):
                raise ValueError(f"Table {t} is malformed.")
            cols_allowed = _columns(db, t)
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError(f"Table {t} has a malformed row.")
                cols = [c for c in row if c in cols_allowed]
                if not cols:
                    continue
                db.execute(f"INSERT INTO {t} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                           [row[c] for c in cols])
            counts[t] = len(rows)
            if db.pg and "id" in cols_allowed:
                db.execute(f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), "
                           f"COALESCE((SELECT MAX(id) FROM {t}), 0) + 1, false)")
        db.commit()
    except Exception:
        db.rollback()
        raise
    return counts
