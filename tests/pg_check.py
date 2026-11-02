"""PostgreSQL compatibility check (run manually; needs psql and a reachable PostgreSQL).

1. Applies app/schema_postgres.sql twice (must be idempotent).
2. Runs the whole pytest suite on SQLite while recording every distinct SQL statement.
3. PREPAREs each statement on PostgreSQL, which validates syntax, table/column names and
   types without executing anything.

Usage:  PGCHECK_DSN="host=/var/run/postgresql port=5432 user=mish dbname=mishtest" python tests/pg_check.py
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DSN = os.environ.get("PGCHECK_DSN", "")


def psql(sql):
    return subprocess.run(["psql", DSN, "-v", "ON_ERROR_STOP=1", "-q", "-c", sql],
                          capture_output=True, text=True)


def main():
    schema = open(os.path.join(ROOT, "app", "schema_postgres.sql")).read()
    for i in (1, 2):
        r = subprocess.run(["psql", DSN, "-v", "ON_ERROR_STOP=1", "-q"], input=schema, capture_output=True, text=True)
        if r.returncode:
            print(f"schema apply #{i} FAILED:\n{r.stderr}")
            return 1
    print("schema applies cleanly (twice)")

    log = os.path.join(ROOT, ".sql-log.txt")
    if os.path.exists(log):
        os.remove(log)
    env = dict(os.environ, MISH_SQL_LOG=log)
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    print("pytest:", r.stdout.strip().splitlines()[-1])
    statements = sorted(set(open(log).read().split("\n<<END>>\n")) - {""})
    os.remove(log)

    skip = re.compile(r"^\s*(PRAGMA|CREATE|INSERT INTO schema_migrations)", re.I)
    failures, checked = [], 0
    for n, sql in enumerate(statements):
        if skip.match(sql) or "information_schema" in sql:
            continue
        counter = iter(range(1, 1000))
        pg_sql = re.sub(r"\?", lambda _m: f"${next(counter)}", sql)
        r = psql(f"BEGIN; PREPARE q{n} AS {pg_sql}; ROLLBACK;")
        checked += 1
        if r.returncode:
            failures.append((sql, r.stderr.strip()))
    print(f"{checked - len(failures)}/{checked} distinct SQL statements prepared successfully on PostgreSQL")
    for sql, err in failures:
        print("\nFAILED:", sql, "\n ", err)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
