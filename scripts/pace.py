"""Reading pace from statistics.sqlite3: speed, record days, per-book velocity."""
import sqlite3
from datetime import datetime

from paths import DB_PATH, STATS
from toc import add_toc


OUTPUT = STATS / "pace.md"
TOP = 15
MIN_SECS = 1800  # books barely touched say nothing about pace
MIN_PAGES = 50
SESSION_GAP = 600  # idle seconds that end a sitting


def hm(secs):
    return f"{secs // 3600}h {secs % 3600 // 60}m"


def span_days(first, last):
    """Calendar days a book was open, both ends counted."""
    fmt = "%Y-%m-%d"
    return (datetime.strptime(last, fmt) - datetime.strptime(first, fmt)).days + 1


def speed(pages, secs):
    return pages * 3600 / secs


def sessions(rows, gap=SESSION_GAP):
    """[(start, duration, title)] sorted by start -> [(start, end, seconds, pages, {titles})]."""
    out = []
    for start, duration, title in rows:
        if out and start - out[-1][1] <= gap:
            s = out[-1]
            out[-1] = (s[0], max(s[1], start + duration), s[2] + duration, s[3] + 1, s[4] | {title})
        else:
            out.append((start, start + duration, duration, 1, {title}))
    return out


def books(cur):
    """One row per title: pages read, seconds, first and last day, days actually read on."""
    return cur.execute("""
        SELECT b.title, COUNT(DISTINCT ps.page), SUM(ps.duration),
               date(MIN(ps.start_time), 'unixepoch', 'localtime'),
               date(MAX(ps.start_time), 'unixepoch', 'localtime'),
               COUNT(DISTINCT date(ps.start_time, 'unixepoch', 'localtime'))
        FROM page_stat_data ps JOIN book b ON b.id = ps.id_book
        WHERE ps.duration > 0
        GROUP BY b.title
    """).fetchall()


def table(f, header, rows):
    f.write("| " + " | ".join(header) + " |\n")
    f.write("|" + "|".join(" --- " for _ in header) + "|\n")
    for row in rows:
        f.write("| " + " | ".join(str(c) for c in row) + " |\n")
    f.write("\n")


def write_speed(f, cur, paced):
    f.write("## Reading Speed\n\n")
    pages, secs = (sum(x) for x in zip(*((p, s) for _, p, s, *_ in paced)))
    f.write(f"{speed(pages, secs):.0f} pages/hour across {len(paced)} books"
            f" ({pages:,} pages, {hm(secs)}).\n\n")

    f.write("### By year\n\n")
    years = cur.execute("""
        SELECT strftime('%Y', ps.start_time, 'unixepoch', 'localtime'),
               COUNT(DISTINCT ps.id_book || '-' || ps.page), SUM(ps.duration)
        FROM page_stat_data ps WHERE ps.duration > 0 GROUP BY 1 ORDER BY 1
    """).fetchall()
    table(f, ["Year", "Pages/hour", "Pages", "Read time"],
          [(y, f"{speed(p, s):.0f}", f"{p:,}", hm(s)) for y, p, s in years])

    ranked = sorted(paced, key=lambda b: speed(b[1], b[2]), reverse=True)
    for heading, rows in (("Fastest", ranked[:TOP]), ("Slowest", ranked[-TOP:][::-1])):
        f.write(f"### {heading}\n\n")
        table(f, ["Title", "Pages/hour", "Pages", "Read time"],
              [(t, f"{speed(p, s):.0f}", p, hm(s)) for t, p, s, *_ in rows])


def write_records(f, cur):
    f.write("## Record Days\n\n")
    days = cur.execute("""
        SELECT date(ps.start_time, 'unixepoch', 'localtime'),
               SUM(ps.duration), COUNT(DISTINCT ps.id_book || '-' || ps.page),
               COUNT(DISTINCT ps.id_book)
        FROM page_stat_data ps WHERE ps.duration > 0
        GROUP BY 1 ORDER BY 2 DESC LIMIT ?
    """, (TOP,)).fetchall()
    table(f, ["Date", "Read time", "Pages", "Books"],
          [(d, hm(s), f"{p:,}", b) for d, s, p, b in days])

    f.write("### Longest sittings\n\n")
    rows = cur.execute("""
        SELECT ps.start_time, ps.duration, b.title
        FROM page_stat_data ps JOIN book b ON b.id = ps.id_book
        WHERE ps.duration > 0 ORDER BY ps.start_time
    """).fetchall()
    longest = sorted(sessions(rows), key=lambda s: s[2], reverse=True)[:TOP]
    f.write(f"Runs of reading with no gap longer than {SESSION_GAP // 60} minutes.\n\n")
    table(f, ["Started", "Read time", "Pages", "Books"],
          [(datetime.fromtimestamp(st).strftime("%Y-%m-%d %H:%M"), hm(secs), pages,
            " / ".join(sorted(titles))) for st, _end, secs, pages, titles in longest])


def write_velocity(f, paced):
    f.write("## Per-Book Velocity\n\n")
    f.write("How long a book took start to finish, against the time actually spent in it.\n\n")

    header = ["Title", "First read", "Last read", "Days", "Days read", "Read time"]
    row = lambda b: (b[0], b[3], b[4], span_days(b[3], b[4]), b[5], hm(b[2]))
    # binged: shortest calendar span, the heaviest of them first
    by_span = sorted(paced, key=lambda b: (span_days(b[3], b[4]), -b[2]))
    f.write("### Binged\n\n")
    table(f, header, [row(b) for b in by_span[:TOP]])
    f.write("### Slow burns\n\n")
    table(f, header, [row(b) for b in by_span[-TOP:][::-1]])


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    paced = [b for b in books(cur) if b[2] >= MIN_SECS and b[1] >= MIN_PAGES]

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(f"# Reading Pace ({datetime.now():%Y-%m-%d})\n\n")
        f.write(f"Books under {MIN_SECS // 60} minutes or {MIN_PAGES} pages read are left out"
                " of the per-book sections.\n\n")
        write_speed(f, cur, paced)
        write_records(f, cur)
        write_velocity(f, paced)
    conn.close()
    add_toc(OUTPUT)
    print(f"{len(paced)} books -> {OUTPUT}")


if __name__ == "__main__":
    main()
