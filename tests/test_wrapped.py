"""Run: python3 tests/test_wrapped.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from datetime import date, datetime

from wrapped import longest_streak, period_names, periods, summarize

assert longest_streak([date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 4)]) == 2
assert longest_streak([date(2026, 1, 1)]) == 1
assert longest_streak([]) == 0
assert longest_streak([date(2026, 1, 2), date(2026, 1, 1)]) == 2  # order must not matter

assert period_names(datetime(2026, 1, 31)) == ("2026", "2026 Q1")
assert period_names(datetime(2026, 7, 1)) == ("2026", "2026 Q3")
assert period_names(datetime(2026, 12, 31)) == ("2026", "2026 Q4")

# one row lands in both its year and its quarter
rows = [("X Vol. 1", 1767225600, 60, 1, 5), ("X Vol. 2", 1767225600, 30, 2, 5)]
assert set(periods(rows)) == {"2026", "2026 Q1"}

s = summarize(periods(rows)["2026"])
assert s["total"] == 90 and s["books"] == 2
assert s["pages"] == 2  # same page number, different books
assert s["series"] == [("X", 90)] and s["volumes"]["X"] == 2
assert s["streak"] == 1 and s["days_read"] == 1
print("ok")
