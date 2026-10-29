"""Thin database layer supporting SQLite (default) and PostgreSQL.

All queries in the app use '?' placeholders and portable SQL. For PostgreSQL the
placeholders are converted to '%s' and psycopg (v3) is used.
"""
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app, g

SCHEMA_VERSION = 1
_PLACEHOLDER = re.compile(r"\?")
_SQL_LOG = os.environ.get("MISH_SQL_LOG", "")


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _is_pg(url):
    return url.startswith("postgres://") or url.startswith("postgresql://")


class Database:
    def __init__(self, url):
        self.url = url
        self.pg = _is_pg(url)
        if self.pg:
            import psycopg  # noqa: provided via requirements.txt in production
            from psycopg.rows import dict_row
            self.conn = psycopg.connect(url, row_factory=dict_row, autocommit=False)
        else:
            path = url.replace("sqlite:///", "", 1)
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(path, timeout=15, detect_types=0)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA busy_timeout = 15000")

    def _sql(self, sql):
        return _PLACEHOLDER.sub("%s", sql) if self.pg else sql

    def execute(self, sql, params=()):
        if _SQL_LOG:  # development aid used by tests/pg_check.py
            with open(_SQL_LOG, "a", encoding="utf-8") as f:
                f.write(sql + "\n<<END>>\n")
        cur = self.conn.cursor()
        cur.execute(self._sql(sql), tuple(params))
        return cur

    def all(self, sql, params=()):
        return [dict(r) for r in self.execute(sql, params).fetchall()]

    def one(self, sql, params=()):
        row = self.execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def scalar(self, sql, params=()):
        row = self.execute(sql, params).fetchone()
        if row is None:
            return None
        return list(dict(row).values())[0]

    def insert(self, table, data):
        cols = list(data.keys())
        sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)}) "
               f"RETURNING id")
        return self.scalar(sql, [data[c] for c in cols])

    def update(self, table, row_id, data):
        if not data:
            return
        sets = ", ".join(f"{c} = ?" for c in data)
        self.execute(f"UPDATE {table} SET {sets} WHERE id = ?", list(data.values()) + [row_id])

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        try:
            self.conn.close()
        except Exception:  # pragma: no cover
            pass

    def executescript(self, script):
        if self.pg:
            with self.conn.cursor() as cur:
                cur.execute(script)
        else:
            self.conn.executescript(script)


def get_db():
    if "db" not in g:
        g.db = Database(current_app.config["DATABASE_URL"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        if _exc is not None:
            db.rollback()
        db.close()


def migrate(url):
    """Create tables if needed. Safe to run on every start."""
    db = Database(url)
    try:
        schema_file = "schema_postgres.sql" if db.pg else "schema_sqlite.sql"
        script = (Path(__file__).parent / schema_file).read_text(encoding="utf-8")
        db.executescript(script)
        done = db.scalar("SELECT COUNT(*) FROM schema_migrations WHERE version = ?", (SCHEMA_VERSION,))
        if not done:
            db.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                       (SCHEMA_VERSION, utcnow()))
        db.commit()
    finally:
        db.close()


def ensure_dirs(app):
    os.makedirs(app.config["STORAGE_DIR"], exist_ok=True)
    for sub in ("files", "media"):
        os.makedirs(os.path.join(app.config["STORAGE_DIR"], sub), exist_ok=True)
