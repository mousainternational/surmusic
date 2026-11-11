"""Build app/data/directory.jsonl.gz — the world station list shipped WITH the code.

Runs on GitHub's computers (see .github/workflows/station-directory.yml), never on the Sur Music server,
so the server's small memory and monthly bandwidth are not used for it. The old file is replaced only when
the new list is complete (at least MIN_STATIONS stations).

    python tools/build_directory.py            # writes app/data/directory.jsonl.gz
"""
import gzip
import json
import os
import random
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.radio import normalize  # noqa: E402  (pure function, no Flask app needed)

PAGES, PER_PAGE, MIN_STATIONS = 16, 2500, 5000
SERVERS = ["de1", "nl1", "at1", "fi1", "de2"]
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "data", "directory.jsonl.gz")


def fetch(path):
    servers = SERVERS[:]
    random.shuffle(servers)
    for s in servers:
        try:
            req = urllib.request.Request(f"https://{s}.api.radio-browser.info{path}",
                                         headers={"User-Agent": "SurMusicRadio/1.0 (+https://www.surmusicradio.com)"})
            with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
                return json.loads(r.read())
        except Exception as exc:  # try the next mirror
            print(f"  {s}: {exc.__class__.__name__}", file=sys.stderr)
    raise RuntimeError("all Radio Browser mirrors failed")


def main():
    seen, rows = set(), []
    for i in range(PAGES):
        raw = fetch(f"/json/stations/search?is_https=true&hidebroken=true&order=clickcount&reverse=true"
                    f"&limit={PER_PAGE}&offset={i * PER_PAGE}")
        if not raw:
            break
        for st in normalize(raw):
            if st["uuid"] not in seen:
                seen.add(st["uuid"])
                rows.append({"c": i, "s": st})
        print(f"page {i}: {len(rows)} stations so far")
        time.sleep(2)
    if len(rows) < MIN_STATIONS:
        print(f"Only {len(rows)} stations: keeping the old file.", file=sys.stderr)
        return 1
    tmp = OUT + ".tmp"
    with open(tmp, "wb") as raw_fh, gzip.GzipFile(fileobj=raw_fh, mode="wb", compresslevel=9, mtime=0) as gz:
        for row in rows:
            gz.write((json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))
    os.replace(tmp, OUT)
    print(f"Saved {len(rows)} stations, {os.path.getsize(OUT) / 1e6:.1f} MB -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
