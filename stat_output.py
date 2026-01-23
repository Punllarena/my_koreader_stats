import sqlite3
from datetime import datetime
from collections import defaultdict
from pathlib import Path

DB_PATH = "statistics.sqlite3"
OUTPUT_DIR = "koreader_monthly_stats"

Path(OUTPUT_DIR).mkdir(exist_ok=True)

def seconds_to_hm(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h {minutes}m"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

query = """
SELECT
    b.title,
    ps.start_time,
    ps.duration
FROM page_stat_data ps
JOIN book b ON b.id = ps.id_book
WHERE ps.duration > 0
"""

cur.execute(query)

monthly_data = defaultdict(lambda: defaultdict(int))

for title, start_time, duration in cur.fetchall():
    dt = datetime.fromtimestamp(start_time)
    key = (dt.year, dt.month)
    monthly_data[key][title] += duration

for (year, month), titles in sorted(monthly_data.items()):
    month_name = datetime(year, month, 1).strftime("%B")
    total_time = sum(titles.values())

    filename = f"{year}-{month:02d}.md"
    output_path = Path(OUTPUT_DIR) / filename

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Titles Read for the Month of {month_name} {year}\n\n")

        for title, seconds in sorted(titles.items(), key=lambda x: x[1], reverse=True):
            f.write(f"- {title} : {seconds_to_hm(seconds)}\n")

        f.write("\n")
        f.write(f"## Total Read Time: {seconds_to_hm(total_time)}\n")
        f.write(f"## Total Titles: {len(titles)}\n")

conn.close()

print("Markdown files generated in:", OUTPUT_DIR)
