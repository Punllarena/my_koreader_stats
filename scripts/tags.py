"""What I read, by RanobeDB genre / tag / demographic, with every tag linked to its series.

Writes stats/tags.md. Also exposes my_series(), which recommend.py reuses.
Needs the RanobeDB cache from updates.py, or fetches (and caches) what it is missing.
"""
import sqlite3
from collections import defaultdict
from datetime import datetime

from paths import DB_PATH, STATS
from toc import add_toc
from titles import split_volume
from pace import hm
from updates import API, SERIES_URL, find_series_id, get

OUTPUT = STATS / "tags.md"
TAG_URL = "https://ranobedb.org/series?tagsInclude={}"
STAFF_URL = "https://ranobedb.org/staff/{}"
GROUPS = [("genre", "Genres"), ("tag", "Tags"), ("demographic", "Demographics")]


def read_seconds():
    """KOReader series name -> (seconds read, books opened)."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT b.title, SUM(ps.duration) FROM page_stat_data ps JOIN book b ON b.id = ps.id_book
        WHERE ps.duration > 0 GROUP BY b.id
    """).fetchall()
    conn.close()
    out = defaultdict(lambda: [0, 0])
    for title, secs in rows:
        name = split_volume(title)[0]
        out[name][0] += secs
        out[name][1] += 1
    return out


def people(series, role):
    """staff id -> display name for one role, once per person."""
    return {s["staff_id"]: s.get("romaji") or s["name"] for s in series.get("staff", []) if s["role_type"] == role}


def my_series():
    """RanobeDB series id -> what I read of it: seconds, books, tags, authors, artists. Unmatched names are skipped."""
    mine, skipped = {}, []
    for name, (secs, books) in sorted(read_seconds().items()):
        sid = find_series_id(name)
        if sid is None:
            skipped.append(name)
            continue
        if sid not in mine:
            s = get(f"{API}/series/{sid}")["series"]
            mine[sid] = {"title": s["title"], "url": SERIES_URL.format(sid), "secs": 0, "books": 0,
                         "tags": [(t["id"], t["name"], t["ttype"]) for t in s.get("tags", [])],
                         "authors": people(s, "author"), "artists": people(s, "artist")}
        mine[sid]["secs"] += secs
        mine[sid]["books"] += books
    return mine, skipped


def tag_stats(mine):
    """tag id -> (name, ttype, [series records], total seconds)."""
    stats = {}
    for rec in mine.values():
        for tid, name, ttype in rec["tags"]:
            entry = stats.setdefault(tid, [name, ttype, [], 0])
            entry[2].append(rec)
            entry[3] += rec["secs"]
    return stats


def main():
    mine, skipped = my_series()
    stats = tag_stats(mine)
    total = sum(r["secs"] for r in mine.values())
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(f"# Tags Read ({datetime.now():%Y-%m-%d})\n\n")
        f.write(f"{len(mine)} series matched on RanobeDB, {hm(total)} read in total. "
                f"A series counts toward every tag it has, so the hours overlap between tags. "
                f"Each tag links to RanobeDB's list of series with it.\n")
        if skipped:
            f.write(f"\nNot on RanobeDB, left out: {', '.join(skipped)}.\n")
        for ttype, heading in GROUPS:
            ranked = sorted(((t, e) for t, e in stats.items() if e[1] == ttype), key=lambda te: (-len(te[1][2]), -te[1][3], te[1][0]))
            if not ranked:
                continue
            f.write(f"\n## {heading}\n\n")
            for tid, (name, _, recs, secs) in ranked:
                f.write(f"- [{name}]({TAG_URL.format(tid)}) - {len(recs)} series, {hm(secs)}\n")
        f.write("\n## Series by tag\n\nTags with at least two series, most-read first.\n")
        for tid, (name, ttype, recs, secs) in sorted(stats.items(), key=lambda te: (-len(te[1][2]), -te[1][3], te[1][0])):
            if len(recs) < 2:
                continue
            f.write(f"\n### [{name}]({TAG_URL.format(tid)}) ({ttype}) - {len(recs)} series, {hm(secs)}\n\n")
            for rec in sorted(recs, key=lambda r: -r["secs"]):
                f.write(f"- [{rec['title']}]({rec['url']}) - {hm(rec['secs'])}\n")
    add_toc(OUTPUT)
    print(f"{len(stats)} tags across {len(mine)} series -> {OUTPUT}")


if __name__ == "__main__":
    main()
