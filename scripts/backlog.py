"""List volumes that are already released but not read yet, from updates_by_series.md.

Run after updates.py (regen.sh does). Usage: python3 scripts/backlog.py [--until YYYY-MM-DD]
The cutoff defaults to today; volumes dated later, or with no full release date, are left out.
"""
import argparse
import re
from datetime import date

from paths import STATS
from toc import add_toc

SOURCE = STATS / "updates_by_series.md"
OUTPUT = STATS / "backlog.md"
SERIES_RE = re.compile(r"## (\[.+\]\(.+\))$")
VOLUME_RE = re.compile(r"- (.+) - (\d{4}-\d{2}-\d{2}|TBA|\d{4}(?:-\d{2})?)$")
FULL_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}$")


def parse(text, cutoff):
    """(series link -> [(date, label)] released on or before cutoff, volumes after it, volumes undated)."""
    series, released, later, undated = None, {}, 0, 0
    for line in text.splitlines():
        m = SERIES_RE.match(line)
        if m:
            series = m[1]
            continue
        if line.startswith("## "):
            series = None  # Contents, Not found on RanobeDB
            continue
        m = VOLUME_RE.match(line)
        if not (series and m):
            continue
        label, when = m.groups()
        if not FULL_DATE_RE.match(when):
            undated += 1
        elif when > cutoff:
            later += 1
        else:
            released.setdefault(series, []).append((when, label))
    return {s: sorted(v) for s, v in released.items()}, later, undated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", default=date.today().isoformat(), help="cutoff date, YYYY-MM-DD (default today)")
    cutoff = ap.parse_args().until
    if not SOURCE.exists():
        raise SystemExit(f"{SOURCE} not found - run scripts/updates.py first")
    released, later, undated = parse(SOURCE.read_text(encoding="utf-8"), cutoff)
    total = sum(len(v) for v in released.values())

    out = [f"# Backlog: Released, Not Yet Read (through {cutoff})", "",
           f"Volumes newer than what you've read that RanobeDB lists as released on or before {cutoff} "
           "(English releases). Built from `updates_by_series.md`.", "",
           f"**{len(released)} titles, {total} volumes.** Left out: {later} volumes dated after {cutoff} "
           f"and {undated} with no release date.", ""]
    # series whose oldest unread volume came out first go first
    for series, vols in sorted(released.items(), key=lambda kv: (kv[1][0][0], kv[0].lower())):
        out += [f"## {series}", ""] + [f"- {label} - {when}" for when, label in vols] + [""]
    OUTPUT.write_text("\n".join(out), encoding="utf-8")
    add_toc(OUTPUT)
    print(f"{len(released)} titles, {total} volumes -> {OUTPUT}")


if __name__ == "__main__":
    main()
