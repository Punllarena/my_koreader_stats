"""Run: python3 tests/test_pace.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from pace import sessions, speed, hm, span_days

# a gap longer than the cutoff starts a new sitting, shorter merges
rows = [(0, 60, "A"), (100, 60, "A"), (10_000, 60, "B")]
merged = sessions(rows, gap=600)
assert len(merged) == 2, merged
assert merged[0][2:4] == (120, 2) and merged[0][4] == {"A"}
assert merged[1][0] == 10_000 and merged[1][4] == {"B"}
assert len(sessions(rows, gap=10)) == 3  # every gap too long: three sittings
assert sessions([]) == []

assert round(speed(100, 3600)) == 100
assert hm(3661) == "1h 1m"

# a span counts both end days, even when it is under 24 hours of wall clock
assert span_days("2026-04-12", "2026-04-13") == 2
assert span_days("2026-04-12", "2026-04-12") == 1
print("ok")
