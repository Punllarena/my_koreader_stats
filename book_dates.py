import sqlite3
import re
from datetime import datetime
from collections import defaultdict

DB_PATH = "statistics.sqlite3"

VOL_RE = re.compile(r'^(.*?)\s+(?:Vol\.|Volume)\s*(\d+)', re.IGNORECASE)
PAREN_RE = re.compile(r'\s*\([^)]*\)\s*$')  # trailing parenthetical e.g. "(Light Novel)"


def normalize_series(title):
    title = PAREN_RE.sub('', title)
    return title.rstrip(' ,:!').strip()

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
    m = VOL_RE.match(title)
    if m:
        series_title = normalize_series(m.group(1))
        vol = int(m.group(2))
    else:
        series_title = title
        vol = None
    series[series_title][vol] = (s, l)

conn.close()

OUTPUT = "book_dates.md"

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
