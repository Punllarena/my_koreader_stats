import sqlite3
from datetime import datetime
from collections import defaultdict

from paths import DB_PATH, STATS
from titles import split_volume


conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
SELECT b.title, MIN(ps.start_time), MAX(ps.start_time)
FROM page_stat_data ps
JOIN book b ON b.id = ps.id_book
WHERE ps.duration > 0
GROUP BY b.title
ORDER BY MIN(ps.start_time)
""")

# series_title -> {vol_num (or None) -> (start, last)}
series = defaultdict(dict)

for title, start, last in cur.fetchall():
    s = datetime.fromtimestamp(start).strftime("%Y-%m-%d")
    l = datetime.fromtimestamp(last).strftime("%Y-%m-%d")
    series_title, vol = split_volume(title)
    # two KOReader entries can be the same volume (a re-import, an export filename): keep the outer dates
    prev = series[series_title].get(vol)
    series[series_title][vol] = (min(s, prev[0]), max(l, prev[1])) if prev else (s, l)

conn.close()

OUTPUT = STATS / "book_dates.md"

with open(OUTPUT, "w", encoding="utf-8") as f:
    for series_title, volumes in series.items():
        f.write(f"{series_title}:\n")
        for vol, (s, l) in sorted(volumes.items(), key=lambda x: (x[0] is None, x[0])):
            if vol is None:
                f.write(f"  - {s}\n")
                f.write(f"  - {l}\n")
            else:
                f.write(f"  {vol}:\n")
                f.write(f"    - {s}\n")
                f.write(f"    - {l}\n")

print(f"Written to {OUTPUT}")
