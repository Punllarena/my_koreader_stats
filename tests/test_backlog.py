"""Run: python3 tests/test_backlog.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from backlog import parse

text = """# Volume Updates by Series (2026-11-19)

## Contents

- [A](#a)

## [A](https://ranobedb.org/series/1)

- Vol. 2 - 2026-01-01
- Vol. 3 - 2026-11-19
- Vol. 4 - 2026-11-20
- Vol. 5 - TBA
- Vol. 6 - 2027-03

## [B: Sub](https://ranobedb.org/series/2)

- Vol. 9 - 2025-05-05

## Not found on RanobeDB

- Deep Work
"""
released, later, undated = parse(text, "2026-11-19")
assert list(released) == ["[A](https://ranobedb.org/series/1)", "[B: Sub](https://ranobedb.org/series/2)"], released
assert released["[A](https://ranobedb.org/series/1)"] == [("2026-01-01", "Vol. 2"), ("2026-11-19", "Vol. 3")]  # cutoff day counts
assert (later, undated) == (1, 2)  # after the cutoff; TBA and a year-month only
assert parse(text, "2025-01-01")[0] == {}
print("ok")
