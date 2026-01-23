import sqlite3
from datetime import datetime, date, timedelta
from collections import defaultdict
from pathlib import Path

DB_PATH = "statistics.sqlite3"
OUTPUT_DIR = "koreader_monthly_stats"

Path(OUTPUT_DIR).mkdir(exist_ok=True)

def seconds_to_hm(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h {minutes}m"

def human_date(ts):
    return datetime.fromtimestamp(ts).strftime("%b %d, %Y")

def longest_streak(dates):
    if not dates:
        return 0

    sorted_days = sorted(dates)
    longest = 1
    current = 1

    for i in range(1, len(sorted_days)):
        if sorted_days[i] == sorted_days[i - 1] + timedelta(days=1):
            current += 1
            longest = max(longest, current)
        else:
            current = 1

    return longest

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

# (year, month) -> title -> data
monthly_titles = defaultdict(lambda: defaultdict(lambda: {
    "time": 0,
    "last_ts": 0
}))

# (year, month) -> set of reading days
monthly_days = defaultdict(set)

for title, start_time, duration in cur.fetchall():
    dt = datetime.fromtimestamp(start_time)
    key = (dt.year, dt.month)

    monthly_titles[key][title]["time"] += duration
    monthly_titles[key][title]["last_ts"] = max(
        monthly_titles[key][title]["last_ts"],
        start_time
    )

    monthly_days[key].add(dt.date())

for (year, month), titles in sorted(monthly_titles.items()):
    month_name = datetime(year, month, 1).strftime("%B")
    total_time = sum(t["time"] for t in titles.values())
    reading_days = monthly_days[(year, month)]

    output_path = Path(OUTPUT_DIR) / f"{year}-{month:02d}.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Titles Read for the Month of {month_name} {year}\n\n")

        for title, data in sorted(
            titles.items(),
            key=lambda x: x[1]["time"],
            reverse=True
        ):
            f.write(f"- 📖 {title} \n")
            f.write(f"  - ⌛ Read Time: {seconds_to_hm(data['time'])}\n")
            f.write(f"  - 📅 Last Read: {human_date(data['last_ts'])}\n\n")

        f.write("\n---\n\n")
        f.write(f"📅 Reading Stats for {month_name} {year}\n")
        f.write(f"- ⏱️ Total Read Time: {seconds_to_hm(total_time)}\n")
        f.write(f"- 📚 Total Titles: {len(titles)}\n")
        f.write(f"- Total Reading Days: {len(reading_days)}\n")
        f.write(f"- Longest Reading Streak: {longest_streak(reading_days)} days\n")

        

conn.close()

print("Monthly Markdown files with human dates and streaks generated in:", OUTPUT_DIR)
