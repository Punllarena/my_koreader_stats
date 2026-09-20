# my_koreader_stats

Turns a KOReader `statistics.sqlite3` into readable markdown: what I read per month and
per year, how fast I read it, a Wrapped-style recap, and which volumes of my series have
come out since.

## Usage

Copy `statistics.sqlite3` out of your KOReader device (`koreader/settings/statistics.sqlite3`)
into this directory, then:

```sh
./regen.sh                  # rebuild everything under stats/
python3 scripts/wrapped.py  # or run a single generator, from any directory
```

Python 3 only, no dependencies. `scripts/updates.py` queries [RanobeDB](https://ranobedb.org)
over HTTP and caches every response in `.ranobedb_cache.json`; delete that file to refresh.

## Layout

```
regen.sh              run every generator
statistics.sqlite3    the KOReader database, copied off the device
scripts/              the generators, plus paths.py, titles.py and toc.py
stats/                everything generated
tests/                self-checks
```

| Script | Output |
| --- | --- |
| `scripts/monthly.py` | `stats/monthly/YYYY-MM.md` — titles read that month, read time, last read date, reading days and longest streak |
| `scripts/yearly.py` | `stats/yearly/YYYY.md` — titles read that year with read time and totals |
| `scripts/book_dates.py` | `stats/book_dates.md` — first and last read date per volume, grouped by series |
| `scripts/pace.py` | `stats/pace.md` — pages/hour overall, per year and per book; heaviest days and longest sittings; how long each book took start to finish |
| `scripts/wrapped.py` | `stats/wrapped.md` — a Wrapped-style recap per year and quarter, each ending in a one-line caption to paste |
| `scripts/updates.py` | `stats/updates_by_series.md`, `stats/updates_by_month.md` — volumes newer than the ones read, per RanobeDB (English releases) |

`scripts/paths.py` holds every path, `scripts/titles.py` parses KOReader titles into a series
and volume number, and `scripts/toc.py` adds a table of contents to each generated file.

## Checks

```sh
for t in tests/test_*.py; do python3 "$t"; done
python3 scripts/toc.py   # the TOC self-check lives with the module
```

## How `updates.py` decides what is unread

KOReader titles are messy, so matching happens in a few steps:

1. Titles are normalized — trailing parentheticals, export filenames
   (`<timestamp> <authors> - Title_`) and volume suffixes are stripped.
2. The series is looked up on RanobeDB, accepting a hit whose title is a prefix of ours or
   vice versa, after lowercasing and dropping accents and punctuation.
3. A RanobeDB book counts as read when its number is not above the highest volume read **or**
   its title matches a book read. The title check matters because one number can cover several
   books (`Vol. 7 Exordium` / `Vol. 7 Finale`).
4. Everything after that point is reported, labelled with the book's own volume title — RanobeDB
   sort order counts side stories and untranslated volumes, so it is not the volume number.

Series that never matched are listed under "Not found on RanobeDB" at the end of both files.
