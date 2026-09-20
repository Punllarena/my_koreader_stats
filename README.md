# my_koreader_stats

Turns a KOReader `statistics.sqlite3` into readable markdown: what I read per month and
per year, when I read each book, and which volumes of my series have come out since.

## Usage

Copy `statistics.sqlite3` out of your KOReader device (`koreader/settings/statistics.sqlite3`)
into this directory, then:

```sh
./regen.sh          # rebuild every file below
python3 updates.py  # or run a single generator
```

Python 3 only, no dependencies. `updates.py` queries [RanobeDB](https://ranobedb.org) over
HTTP and caches every response in `.ranobedb_cache.json`; delete that file to refresh.

## What gets generated

| Script | Output |
| --- | --- |
| `koreader_monthly_human_dates_and_streaks.py` | `koreader_monthly_stats/YYYY-MM.md` — titles read that month, read time, last read date, reading days and longest streak |
| `stat_output_yearly.py` | `koreader_yearly_stats/YYYY.md` — titles read that year with read time and totals |
| `book_dates.py` | `book_dates.md` — first and last read date per volume, grouped by series |
| `updates.py` | `updates_by_series.md`, `updates_by_month.md` — volumes newer than the ones read, per RanobeDB (English releases) |

`toc.py` adds a table of contents to each generated file; `test_updates.py` and
`python3 toc.py` are the self-checks.

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
