"""Run: python3 tests/test_recommend.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from datetime import date
from recommend import abandon_bonus, recent_volumes, release_date, rating_bonus, reader_counts, score, similarity, weigh
from tags import tag_stats

# a rare shared tag counts for more than a common one
idf = {1: 0.1, 2: 3.0, 3: 3.0}  # 1 = common, 2 and 3 = rare
mine = {1: 1.0, 2: 1.0}
assert similarity({1, 2}, mine, idf) > similarity({1, 3}, mine, idf)
assert similarity({3}, mine, idf) == 0.0 and similarity(set(), mine, idf) == 0.0

# few votes shrink toward the prior, many votes don't
assert rating_bonus({"score": 10, "count": 1})[0] < rating_bonus({"score": 10, "count": 500})[0]
assert rating_bonus(None)[0] == 0
assert rating_bonus({"score": 3, "count": 500})[0] < 0

# staff match adds to the score; the author I read most gives the full bonus
rec = lambda sec, tags, authors: {"secs": sec, "tags": tags, "authors": authors, "artists": {}}
series = {
    "a": rec(36000, [(1, "fantasy", "genre"), (2, "isekai", "tag")], {10: "Ann"}),
    "b": rec(3600, [(1, "fantasy", "genre")], {11: "Bob"}),
}
tags, authors, artists, count, names = weigh(series)
assert authors[10] > authors[11] and count[10] == 1 and names[11] == "Bob"
cand = {"tags": [{"id": 2}], "staff": [{"role_type": "author", "staff_id": 10}]}
plain = {"tags": [{"id": 2}], "staff": []}
assert score(cand, tags, authors, artists, idf)[0] > score(plain, tags, authors, artists, idf)[0]
assert score(cand, tags, authors, artists, idf)[1]["by_author"] == {10: 1.0}

# tag stats group series by tag and add up read time
stats = tag_stats(series)
assert stats[1][2] and len(stats[1][2]) == 2 and stats[1][3] == 39600
assert len(stats[2][2]) == 1
# readers who stall or drop: many drops cost, few help, tiny samples barely move
labels = lambda **c: {"user_stats_label": [{"label_id": i, "count": n} for i, n in c.items()]}
liked = {"user_stats_label": [{"label_id": 1, "count": 200}, {"label_id": 2, "count": 100}, {"label_id": 5, "count": 3}]}
dropped = {"user_stats_label": [{"label_id": 1, "count": 50}, {"label_id": 4, "count": 20}, {"label_id": 5, "count": 20}]}
tiny = {"user_stats_label": [{"label_id": 5, "count": 2}]}
assert reader_counts(dropped) == (40, 90) and reader_counts({}) == (0, 0)
assert abandon_bonus(liked)[0] > 0 > abandon_bonus(dropped)[0]
assert abs(abandon_bonus(tiny)[0]) < abs(abandon_bonus(dropped)[0])
assert abandon_bonus({})[0] == 0

# new and upcoming: English main volumes inside the window only; unknown dates are skipped
assert release_date(20261101) == date(2026, 11, 1)
assert release_date(99999999) is None and release_date(20269999) is None and release_date(None) is None
book = lambda title, when, kind="main", lang="en": {"book_type": kind, "title": title, "c_release_dates": {lang: when}}
s = {"title": "Series", "books": [
    book("Series, Vol. 1", 20250101), book("Series, Vol. 2", 20260901), book("Series, Vol. 3", 20261201),
    book("Series, Vol. 4", 20270601), book("Series, Vol. 5", 99999999), book("Series Short Story", 20261001, "side"),
    book("Series, Vol. 6", 20261001, lang="ja")]}
assert recent_volumes(s, date(2026, 11, 19)) == [(date(2026, 9, 1), "Vol. 2"), (date(2026, 12, 1), "Vol. 3")]
assert recent_volumes({"title": "X", "books": []}, date(2026, 11, 19)) == []
print("ok")
