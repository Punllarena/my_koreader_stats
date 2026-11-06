"""Run: python3 tests/test_sync.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from sync_ranobedb import build_payload, day, status

# read to the end
assert status(1.0, 0.9) == "Finished"
# the afterword/ads at the end go unread
assert status(0.90, 0.9) == "Finished"
assert status(0.89, 0.9) == "Reading"
# paged to the end without reading it (Nia Liston Vol. 8)
assert status(0.95, 0.03) == "Reading"
assert status(0.95, 0.5) == "Finished"

volume = {"first": 1_700_000_000, "last": 1_700_900_000, "furthest": 1.0, "coverage": 0.9}
p = build_payload(volume, {})
assert p == {"readingStatus": "Finished", "selectedCustLabels": [],
             "started": day(1_700_000_000), "finished": day(1_700_900_000)}, p

# not finished: no finish date; stored score/notes/labels are re-sent
volume["furthest"] = 0.4
p = build_payload(volume, {"score": 8.5, "notes": "good", "selectedCustLabels": [3]})
assert p["readingStatus"] == "Reading" and p["finished"] is None
assert p["score"] == 8.5 and p["notes"] == "good" and p["selectedCustLabels"] == [3]
assert "score" not in build_payload(volume, {})
print("ok")
