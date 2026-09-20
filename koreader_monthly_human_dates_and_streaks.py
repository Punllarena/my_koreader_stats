import sqlite3
from datetime import datetime, date, timedelta
from collections import defaultdict
from pathlib import Path
from toc import add_toc

DB_PATH = "statistics.sqlite3"
OUTPUT_DIR = "koreader_monthly_stats"

# Volume pattern configurations
# Format: 'pattern': 'display_name'
# Patterns are regex that capture the volume number
VOLUME_PATTERNS = {
    r': Volume (\d+)$': 'Volume',
    r': Vol\.? (\d+)$': 'Vol',
    r': V(\d+)$': 'V',
    r': Part (\d+)$': 'Part',
    r': Pt\.? (\d+)$': 'Pt',
    r': Book (\d+)$': 'Book',
    r': Bk\.? (\d+)$': 'Bk',
    r', Volume (\d+)$': 'Volume',
    r', Vol\.? (\d+)$': 'Vol',
    r', V(\d+)$': 'V',
    r', Part (\d+)$': 'Part',
    r', Pt\.? (\d+)$': 'Pt',
    r', Book (\d+)$': 'Book',
    r', Bk\.? (\d+)$': 'Bk',
    r' - Volume (\d+)$': 'Volume',
    r' - Vol\.? (\d+)$': 'Vol',
    r' - V(\d+)$': 'V',
    r' - Part (\d+)$': 'Part',
    r' - Pt\.? (\d+)$': 'Pt',
    r' - Book (\d+)$': 'Book',
    r' - Bk\.? (\d+)$': 'Bk',
    r' \(Volume (\d+)\)$': 'Volume',
    r' \(Vol\.? (\d+)\)$': 'Vol',
    r' \(V(\d+)\)$': 'V',
    r' \(Part (\d+)\)$': 'Part',
    r' \(Pt\.? (\d+)\)$': 'Pt',
    r' \(Book (\d+)\)$': 'Book',
    r' \(Bk\.? (\d+)\)$': 'Bk',
    r' \[(\d+)\]$': '#',
    r' #(\d+)$': '#',
    r' Volume (\d+) ': 'Volume',  # Volume in middle of title
    r' Vol\.? (\d+) ': 'Vol',    # Vol in middle of title
    r' Volume (\d+)$': 'Volume',  # Volume at end without punctuation
    r' Vol\.? (\d+)$': 'Vol',    # Vol at end without punctuation
}

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

def extract_base_title_and_volume(title):
    """Extract base title and volume from a title string."""
    import re
    
    for pattern, display_name in VOLUME_PATTERNS.items():
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            volume = match.group(1)
            base_title = title[:match.start()].strip()
            return base_title, int(volume), display_name
    
    # No volume found, return title as is with no volume
    return title, None, None

def group_titles_by_volume(titles_data):
    """Group titles by their base title, organizing volumes together."""
    grouped = defaultdict(lambda: defaultdict(list))
    
    # First pass: extract volumes using patterns
    for title, data in titles_data.items():
        base_title, volume, display_name = extract_base_title_and_volume(title)
        
        if volume is not None:
            # This is a volume, group under base title
            grouped[base_title][volume] = {
                'full_title': title,
                'data': data,
                'display_name': display_name
            }
        else:
            # This is not a volume, treat as standalone for now
            grouped[title][None] = {
                'full_title': title,
                'data': data,
                'display_name': None
            }
    
    # Second pass: try to group similar titles that weren't caught by patterns
    # This handles cases like "Title Part 1" and "Title Part 2" where patterns failed
    standalone_titles = [(k, v) for k, v in grouped.items() if None in v and len(v) == 1]
    
    # Create a list to track which titles to remove to avoid modifying dict during iteration
    titles_to_remove = []
    groups_to_add = {}
    
    for i, (title1, info1) in enumerate(standalone_titles):
        for title2, info2 in standalone_titles[i+1:]:
            if are_similar_titles(title1, title2):
                # Extract volume numbers from titles
                vol1 = extract_volume_from_title(title1)
                vol2 = extract_volume_from_title(title2)
                
                # Mark titles for removal
                titles_to_remove.extend([title1, title2])
                
                # Create a new group with a common base title
                base_title = find_common_base(title1, title2)
                groups_to_add[base_title] = {
                    vol1 if vol1 is not None else 1: {
                        'full_title': title1,
                        'data': info1[None]['data'],
                        'display_name': 'Volume'
                    },
                    vol2 if vol2 is not None else 2: {
                        'full_title': title2, 
                        'data': info2[None]['data'],
                        'display_name': 'Volume'
                    }
                }
                break
    
    # Remove the standalone entries
    for title in titles_to_remove:
        if title in grouped:
            del grouped[title]
    
    # Add the new groups
    for base_title, group_data in groups_to_add.items():
        grouped[base_title] = group_data
    
    return grouped

def extract_volume_from_title(title):
    """Try to extract volume number from title using simple patterns."""
    import re
    
    # Look for simple volume patterns in the middle of titles
    patterns = [
        r'Volume (\d+)',
        r'Vol\.? (\d+)',
        r'V(\d+)',
        r'Part (\d+)',
        r'Pt\.? (\d+)',
        r'Book (\d+)',
        r'Bk\.? (\d+)',
        r'(\d+)$',  # Just a number at the end
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            return int(match.group(1))
    
    return None

def are_similar_titles(title1, title2):
    """Check if two titles are similar enough to be grouped together."""
    # Simple similarity check: if one title is a prefix of the other (minus trailing numbers/punctuation)
    import re
    
    # Remove trailing numbers, punctuation, and common volume indicators
    def normalize(title):
        # Remove trailing patterns like " 1", " Part 1", " (1)", etc.
        normalized = re.sub(r'[:\-,\s]*(?:Volume|Vol|V|Part|Pt|Book|Bk)?\.?\s*\d*\s*[\)\]]*$', '', title, flags=re.IGNORECASE)
        return normalized.strip()
    
    norm1 = normalize(title1)
    norm2 = normalize(title2)
    
    # If normalized titles are the same, they're probably related
    return norm1 == norm2 and len(norm1) > 10  # Avoid matching very short titles

def find_common_base(title1, title2):
    """Find a common base title between two similar titles."""
    # Use the shorter, more normalized version as the base
    import re
    
    def normalize(title):
        normalized = re.sub(r'[:\-,\s]*(?:Volume|Vol|V|Part|Pt|Book|Bk)?\.?\s*\d*\s*[\)\]]*$', '', title, flags=re.IGNORECASE)
        return normalized.strip()
    
    base1 = normalize(title1)
    base2 = normalize(title2)
    
    # Return the longer normalized title (it's likely more complete)
    return base1 if len(base1) >= len(base2) else base2

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

        # Group titles by base title
        grouped_titles = group_titles_by_volume(titles)
        
        for base_title, volumes in sorted(grouped_titles.items()):
            if len(volumes) == 1 and None in volumes:
                # Single title without volumes - give it the same treatment as grouped titles
                volume_info = volumes[None]
                data = volume_info['data']
                f.write(f"## {base_title}\n\n")
                f.write(f"- {volume_info['full_title']}\n")
                f.write(f"  - ⌛ Read Time: {seconds_to_hm(data['time'])}\n")
                f.write(f"  - 📅 Last Read: {human_date(data['last_ts'])}\n\n")
            else:
                # Multiple volumes or single volume
                f.write(f"## {base_title}\n\n")
                
                # Sort volumes by volume number, putting None (no volume) at the end
                sorted_volumes = sorted(
                    [(v, info) for v, info in volumes.items() if v is not None],
                    key=lambda x: x[0]
                )
                
                # Add any non-volume entries at the end
                non_volume_entries = [(v, info) for v, info in volumes.items() if v is None]
                sorted_volumes.extend(non_volume_entries)
                
                for volume, volume_info in sorted_volumes:
                    data = volume_info['data']
                    
                    if volume is not None:
                        display_name = volume_info.get('display_name', 'Volume')
                        f.write(f"- {display_name} {volume}\n")
                    else:
                        f.write(f"- {volume_info['full_title']}\n")
                    
                    f.write(f"  - ⌛ Read Time: {seconds_to_hm(data['time'])}\n")
                    f.write(f"  - 📅 Last Read: {human_date(data['last_ts'])}\n\n")

        f.write("\n---\n\n")
        f.write(f"📅 Reading Stats for {month_name} {year}\n")
        f.write(f"- ⏱️ Total Read Time: {seconds_to_hm(total_time)}\n")
        f.write(f"- 📚 Total Titles: {len(titles)}\n")
        f.write(f"- Total Reading Days: {len(reading_days)}\n")
        f.write(f"- Longest Reading Streak: {longest_streak(reading_days)} days\n")

    add_toc(output_path)

        

conn.close()

print("Monthly Markdown files with human dates and streaks generated in:", OUTPUT_DIR)
