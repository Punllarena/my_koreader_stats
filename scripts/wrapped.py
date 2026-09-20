"""A Wrapped-style recap per year and quarter, short enough to paste as a caption."""
import sqlite3
from collections import defaultdict
from datetime import date, datetime

from paths import DB_PATH, STATS
from titles import split_volume
from toc import add_toc


OUTPUT = STATS / "wrapped.md"
TOP = 5


def hm(secs):
    return f"{secs // 3600}h {secs % 3600 // 60}m"


def longest_streak(days):
    """Most consecutive calendar days read."""
    best = run = 0
    prev = None
    for d in sorted(days):
        run = run + 1 if prev and (d - prev).days == 1 else 1
        best, prev = max(best, run), d
    return best


def rows():
    conn = sqlite3.connect(DB_PATH)
    out = conn.execute("""
        SELECT TRIM(b.title), ps.start_time, ps.duration, ps.id_book, ps.page
        FROM page_stat_data ps JOIN book b ON b.id = ps.id_book
        WHERE ps.duration > 0
    """).fetchall()
    conn.close()
    return out


def period_names(d):
    return f"{d.year}", f"{d.year} Q{(d.month - 1) // 3 + 1}"


def periods(rows):
    """{'2026': [...], '2026 Q3': [...]} - every row filed under its year and its quarter."""
    out = defaultdict(list)
    for title, start, duration, id_book, page in rows:
        d = datetime.fromtimestamp(start)
        for name in period_names(d):
            out[name].append((title, d, duration, id_book, page))
    return out


def summarize(entries):
    """Everything the recap of one period needs."""
    secs = defaultdict(int)          # title -> seconds
    series_secs = defaultdict(int)   # series -> seconds
    series_vols = defaultdict(set)
    days = defaultdict(int)          # date -> seconds
    hours = defaultdict(int)         # hour of day -> seconds
    pages = set()                    # a page reread later still counts once

    for title, d, duration, id_book, page in entries:
        series, vol = split_volume(title)
        secs[title] += duration
        series_secs[series] += duration
        series_vols[series].add(vol)
        days[d.date()] += duration
        hours[d.hour] += duration
        pages.add((id_book, page))

    total = sum(secs.values())
    best_day = max(days.items(), key=lambda kv: kv[1])
    return {
        "total": total,
        "pages": len(pages),
        "books": len(secs),
        "series": sorted(series_secs.items(), key=lambda kv: -kv[1]),
        "volumes": {s: len(v) for s, v in series_vols.items()},
        "top_books": sorted(secs.items(), key=lambda kv: -kv[1])[:TOP],
        "days_read": len(days),
        "streak": longest_streak(days),
        "best_day": best_day,
        "peak_hour": max(hours.items(), key=lambda kv: kv[1])[0],
    }


def delta(total, previous):
    if not previous:
        return ""
    pct = (total - previous) / previous * 100
    return f" ({pct:+.0f}% on the period before)"


def write_period(f, level, name, s, previous, in_progress):
    top_series, top_secs = s["series"][0]
    vols = s["volumes"][top_series]
    pages = s["pages"]
    f.write(f"{'#' * level} {name}{' (in progress)' if in_progress else ''}\n\n")
    f.write(f"- 📚 **{s['books']} books** · {pages:,} pages · **{hm(s['total'])}**"
            f"{delta(s['total'], previous)}\n")
    f.write(f"- 🏆 Most time with **{top_series}** — {hm(top_secs)} across"
            f" {vols} volume{'s' if vols != 1 else ''}\n")
    f.write(f"- 🔥 Longest streak **{s['streak']} days** · read on {s['days_read']} days\n")
    f.write(f"- 🥇 Biggest day **{s['best_day'][0]}** — {hm(s['best_day'][1])}\n")
    f.write(f"- 🕐 Peak reading hour **{s['peak_hour']:02d}:00**\n\n")
    f.write(f"{'#' * (level + 1)} Top {len(s['top_books'])}\n\n")
    for i, (title, secs) in enumerate(s["top_books"], 1):
        f.write(f"{i}. {title} — {hm(secs)}\n")
    f.write(f"\n> {name} wrapped: {s['books']} books, {s['total'] // 3600} hours,"
            f" {pages:,} pages. Most time with {top_series}."
            f" Longest streak {s['streak']} days. 📚\n\n")


def main():
    summaries = {name: summarize(entries) for name, entries in periods(rows()).items()}
    order = sorted(summaries, reverse=True)  # newest first, a year ahead of its own quarters
    current = period_names(datetime.now())

    def previous_of(name):
        """Total of the period before this one, for the trend line."""
        same_kind = sorted(n for n in summaries if (" Q" in n) == (" Q" in name) and n < name)
        return summaries[same_kind[-1]]["total"] if same_kind else 0

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(f"# Reading Wrapped ({date.today():%Y-%m-%d})\n\n")
        f.write("A recap per year and per quarter. The blockquote under each one is the caption.\n\n")
        for name in order:
            if " Q" in name:
                continue
            write_period(f, 2, name, summaries[name], previous_of(name), name in current)
            for q in [n for n in order if n.startswith(f"{name} Q")]:
                write_period(f, 3, q, summaries[q], previous_of(q), q in current)
    add_toc(OUTPUT)
    print(f"{len(summaries)} periods -> {OUTPUT}")


if __name__ == "__main__":
    main()
