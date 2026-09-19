"""Compare volumes read (statistics.sqlite3) against RanobeDB and list newer volumes."""
import json
import re
import unicodedata
import sqlite3
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DB_PATH = "statistics.sqlite3"
OUTPUT = "updates.md"
CACHE_PATH = Path(".ranobedb_cache.json")
API = "https://ranobedb.org/api/v0"
LANG = "en"  # release language to report
UA = "my_koreader_stats/1.0"  # ranobedb 403s the default urllib agent

VOL_RE = re.compile(r'^(.*?)\s+(?:Vol\.|Volume|V)\s*(\d+)', re.IGNORECASE)
PAREN_RE = re.compile(r'\s*\([^)]*\)\s*$')

cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}


def normalize_series(title):
    return PAREN_RE.sub('', title).rstrip(' ,:!').strip()


def get(url):
    """GET json, cached by url. ponytail: cache never expires, delete the file to refresh."""
    if url not in cache:
        time.sleep(0.3)  # be polite to ranobedb
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            cache[url] = json.loads(r.read().decode())
        CACHE_PATH.write_text(json.dumps(cache))
    return cache[url]


def squash(s):
    """Lowercase, strip accents and punctuation, collapse spaces - for title comparison."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^0-9a-z ]+", " ", s.lower()).split())


def find_series_id(name):
    """First hit whose title is a prefix of ours or vice versa (subtitles differ a lot)."""
    q = urllib.parse.quote(name)
    hits = get(f"{API}/series?q={q}&limit=5").get("series") or []
    mine = squash(name)
    for hit in hits:
        for theirs in {squash(hit["title"]), squash(hit.get("romaji") or "")} - {""}:
            if mine.startswith(theirs) or theirs.startswith(mine):
                return hit["id"]
    return None


def fmt_date(n):
    if not n or n >= 99999999:
        return "TBA"
    s = str(n)
    try:
        return datetime.strptime(s, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return f"{s[:4]}-{s[4:6]}" if s[4:6] != "99" else s[:4]  # partially known dates


def read_volumes():
    """series title -> highest volume number read (0 if unnumbered)."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT DISTINCT b.title
        FROM page_stat_data ps JOIN book b ON b.id = ps.id_book
        WHERE ps.duration > 0
    """).fetchall()
    conn.close()

    highest = defaultdict(int)
    for (title,) in rows:
        m = VOL_RE.match(title)
        if m:
            highest[normalize_series(m.group(1))] = max(
                highest[normalize_series(m.group(1))], int(m.group(2)))
        else:
            highest[normalize_series(title)] = max(highest[normalize_series(title)], 0)
    return highest


def main():
    updates, unmatched = [], []

    # several KOReader titles can resolve to one series ("X" and "X: Subtitle") - keep the furthest read
    furthest = {}
    for name, last_read in sorted(read_volumes().items()):
        sid = find_series_id(name)
        if sid is None:
            unmatched.append(name)
            continue
        furthest[sid] = max(furthest.get(sid, 0), last_read)

    for sid, last_read in furthest.items():
        series = get(f"{API}/series/{sid}")["series"]
        for book in series.get("books", []):
            if book.get("book_type") != "main":
                continue
            vol = book.get("sort_order")
            if vol is None or vol <= last_read:
                continue
            date = (book.get("c_release_dates") or {}).get(LANG)
            updates.append((series["title"], vol, fmt_date(date)))

    updates.sort()

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(f"# Volume Updates ({datetime.now():%Y-%m-%d})\n\n")
        f.write(f"Volumes newer than what you've read, per RanobeDB ({LANG} releases).\n\n")
        for title, vol, date in updates:
            f.write(f"- {title} - Volume {vol} - {date}\n")
        if unmatched:
            f.write("\n## Not found on RanobeDB\n\n")
            for name in unmatched:
                f.write(f"- {name}\n")

    print(f"{len(updates)} newer volumes across {len(set(u[0] for u in updates))} series"
          f" -> {OUTPUT} ({len(unmatched)} series unmatched)")


if __name__ == "__main__":
    main()
