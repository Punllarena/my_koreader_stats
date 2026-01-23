import sqlite3
from datetime import datetime
from collections import defaultdict
from pathlib import Path

DB_PATH = "statistics.sqlite3"
OUTPUT_DIR = "koreader_yearly_stats"

Path(OUTPUT_DIR).mkdir(exist_ok=True)

def seconds_to_hm(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h {minutes}m"

# def human_date(ts):
#     return datetime.fromtimestamp(ts).strftime("%b %d, %Y")

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

yearly_titles = defaultdict(lambda: defaultdict(int))

for title, start_time, duration in cur.fetchall():
    year = datetime.fromtimestamp(start_time).year
    yearly_titles[year][title] += duration

for year, titles in sorted(yearly_titles.items()):
    total_time = sum(titles.values())
    total_titles = len(titles)

    output_path = Path(OUTPUT_DIR) / f"{year}.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Reading Year in Review — {year}\n\n")

        f.write("## 📚 Titles Read\n")
        for title, seconds in sorted(titles.items(), key=lambda x: x[0], reverse=False):
            f.write(f"- 📖 {title} \n")
            f.write(f"  - ⌛ Read Time: {seconds_to_hm(seconds)}\n")
            # f.write(f"  - 📅 Last Read: {human_date(seconds)}\n\n")
            f.write(f"\n")

        f.write(f"\n## 📚 Total Titles: {total_titles}\n\n")
        f.write("## ⌛ Total Reading Time: ")
        f.write(seconds_to_hm(total_time))

conn.close()

print("Yearly review Markdown files generated in:", OUTPUT_DIR)
