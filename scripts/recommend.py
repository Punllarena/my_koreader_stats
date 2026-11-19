"""Recommend series I haven't read, from the tags, authors and artists of the ones I have.

Writes stats/recommendations.md. Candidates come from RanobeDB (English releases only): the best-rated
series for my top tags and tag pairs, plus everything by my most-read authors and artists. Each is scored
by tag similarity (rare tags count more), a bonus for shared author / artist, and a small shrunk-rating bonus.
Nothing is sent to RanobeDB except searches; responses are cached like updates.py does.
"""
import itertools
import math
import urllib.parse
from collections import defaultdict
from datetime import date, datetime, timedelta

from paths import STATS
from toc import add_toc
from tags import STAFF_URL, TAG_URL, my_series
from updates import API, SERIES_URL, get, vol_label

OUTPUT = STATS / "recommendations.md"
TOP = 30
SINGLE_TAGS, PAIR_TAGS, AUTHORS, ARTISTS = 8, 6, 6, 4  # how many of my favourites seed the search
PRIOR_VOTES, PRIOR_SCORE = 10, 7.5  # shrink ratings with few votes toward an average
AUTHOR_BONUS, ARTIST_BONUS, RATING_BONUS = 0.25, 0.12, 0.2
# RanobeDB reader counts per list status. The ids aren't documented; read off the data (a finished series
# has many 2s, an ongoing one almost none). Stalled or dropped is how readers say "not worth finishing".
READING, FINISHED, STALLED, DROPPED = 1, 2, 4, 5
BASE_ABANDON, ABANDON_VOTES, ABANDON_BONUS = 0.125, 20, 0.15  # typical share, shrink strength, max +/-
NEW_TOP, RECENT_DAYS, UPCOMING_DAYS = 15, 120, 90  # the "new and upcoming" section


def tag_idf():
    """tag id -> how rare the tag is on RanobeDB (common tags like 'fantasy' say little)."""
    counts, page, pages = {}, 1, 1
    while page <= pages:
        r = get(f"{API}/tags?page={page}")
        pages = r["totalPages"]
        counts.update({t["id"]: int(t["count"]) for t in r["tags"]})
        page += 1
    biggest = max(counts.values())
    return {t: math.log(1 + biggest / max(c, 1)) for t, c in counts.items()}


def weigh(mine):
    """What I like: sqrt(hours read) summed per tag / author / artist, so one huge series can't dominate."""
    tags, authors, artists = defaultdict(float), defaultdict(float), defaultdict(float)
    count, names = defaultdict(int), {}
    for rec in mine.values():
        w = math.sqrt(rec["secs"] / 3600)
        for tid, *_ in rec["tags"]:
            tags[tid] += w
        for kind, bucket in (("authors", authors), ("artists", artists)):
            for pid, name in rec[kind].items():
                bucket[pid] += w
                names[pid] = name
                count[pid] += 1
    return tags, authors, artists, count, names


def similarity(cand_tags, my_tags, idf):
    """Cosine of my tag weights and the candidate's, both scaled by tag rarity. 0..1."""
    mine = {t: w * idf.get(t, 1) for t, w in my_tags.items()}
    theirs = {t: idf.get(t, 1) for t in cand_tags}
    dot = sum(w * theirs[t] for t, w in mine.items() if t in theirs)
    norm = math.sqrt(sum(w * w for w in mine.values())) * math.sqrt(sum(w * w for w in theirs.values()))
    return dot / norm if norm else 0.0


def rating_bonus(rating):
    score, votes = (rating or {}).get("score") or 0, (rating or {}).get("count") or 0
    shrunk = (votes * score + PRIOR_VOTES * PRIOR_SCORE) / (votes + PRIOR_VOTES)
    return RATING_BONUS * max(-1.0, min(1.0, (shrunk - PRIOR_SCORE) / 1.5)), shrunk


def reader_counts(series):
    """(readers who stalled or dropped, readers counted) from RanobeDB's per-status reader counts."""
    labels = {x["label_id"]: x["count"] for x in series.get("user_stats_label") or []}
    gone = labels.get(STALLED, 0) + labels.get(DROPPED, 0)
    return gone, gone + labels.get(READING, 0) + labels.get(FINISHED, 0)


def abandon_bonus(series, base=BASE_ABANDON):
    """(bonus, shrunk share who stalled or dropped, readers counted). Few readers stay near `base`."""
    gone, readers = reader_counts(series)
    share = (gone + ABANDON_VOTES * base) / (readers + ABANDON_VOTES)
    return ABANDON_BONUS * max(-1.0, min(1.0, (base - share) / 0.10)), share, readers


def release_date(n):
    """RanobeDB yyyymmdd int -> date, or None when unknown or only partly known (TBA, 2026-99-99)."""
    try:
        return datetime.strptime(str(n), "%Y%m%d").date()
    except (TypeError, ValueError):
        return None


def recent_volumes(series, today, recent=RECENT_DAYS, upcoming=UPCOMING_DAYS):
    """English main volumes released in the last `recent` days or due in the next `upcoming`: [(date, label)]."""
    start, end = today - timedelta(days=recent), today + timedelta(days=upcoming)
    found = []
    for book in series.get("books", []):
        when = release_date((book.get("c_release_dates") or {}).get("en"))
        if book.get("book_type") == "main" and when and start <= when <= end:
            found.append((when, vol_label(series["title"], book["title"])))
    return sorted(found)


def score(series, tags, authors, artists, idf, base=BASE_ABANDON):
    """(total, parts) for one RanobeDB series record. authors / artists are my person weights."""
    cand_tags = {t["id"] for t in series.get("tags", [])}
    sim = similarity(cand_tags, tags, idf)
    top_author, top_artist = max(authors.values(), default=1), max(artists.values(), default=1)
    by_author = {p["staff_id"]: authors[p["staff_id"]] / top_author for p in series.get("staff", [])
                 if p["role_type"] == "author" and p["staff_id"] in authors}
    by_artist = {p["staff_id"]: artists[p["staff_id"]] / top_artist for p in series.get("staff", [])
                 if p["role_type"] == "artist" and p["staff_id"] in artists}
    rating, shrunk = rating_bonus(series.get("rating"))
    abandon, share, readers = abandon_bonus(series, base)
    total = (sim + AUTHOR_BONUS * max(by_author.values(), default=0) + ARTIST_BONUS * max(by_artist.values(), default=0)
             + rating + abandon)
    return total, {"sim": sim, "by_author": by_author, "by_artist": by_artist, "rating": shrunk,
                   "abandon": share, "readers": readers}


def search(params, sort="Rating desc"):
    """Series ids from a RanobeDB series search (English releases; best rated first unless told otherwise)."""
    query = urllib.parse.urlencode(params + [("rl", "en"), ("sort", sort)])
    try:
        return [s["id"] for s in get(f"{API}/series?{query}").get("series", []) if not s.get("hidden")]
    except Exception as e:  # one failed search shouldn't lose the rest
        print(f"search failed ({e}): {query}")
        return []


def candidates(tags, authors, artists, idf):
    ranked = sorted(tags, key=lambda t: -tags[t] * idf.get(t, 1))
    found = set()
    for t in ranked[:SINGLE_TAGS]:
        found.update(search([("tagsInclude", t), ("limit", 20)]))
        found.update(search([("tagsInclude", t), ("limit", 10)], sort="Start date desc"))  # the newest series too
    for a, b in itertools.combinations(ranked[:PAIR_TAGS], 2):
        found.update(search([("tagsInclude", a), ("tagsInclude", b), ("limit", 12)]))
    for people, n in ((authors, AUTHORS), (artists, ARTISTS)):
        for pid in sorted(people, key=lambda p: -people[p])[:n]:
            found.update(search([("staff", pid), ("limit", 20)]))
    return found


def write_entry(f, rank, row, tags, idf, names, count, extra=""):
    total, sid, series, parts = row
    cand = {t["id"]: t["name"] for t in series["tags"]}
    shared = sorted((t for t in cand if t in tags), key=lambda t: -tags[t] * idf.get(t, 1) ** 2)[:6]  # rare ones first
    main_books = [b for b in series.get("books", []) if b.get("book_type") == "main"]
    raw = series.get("rating") or {}
    rated = f"{raw['score']:.1f} ({raw.get('count', 0)} votes)" if raw.get("score") else "not rated"
    f.write(f"\n{rank}. [{series['title']}]({SERIES_URL.format(sid)}) - score {total:.2f}\n")
    in_english = sum(1 for b in main_books if (b.get("c_release_dates") or {}).get("en"))
    f.write(f"   - Rating {rated}, {len(main_books)} volumes ({in_english} in English), "
            f"{series.get('publication_status', 'unknown')}\n")
    if parts["readers"] >= ABANDON_VOTES:
        f.write(f"   - Readers: {parts['readers']} reading or finished, {parts['abandon']:.0%} stalled or dropped\n")
    if extra:
        f.write(extra)
    f.write("   - Shared tags: " + ", ".join(f"[{cand[t]}]({TAG_URL.format(t)})" for t in shared) + "\n")
    for label, found in (("Author", parts["by_author"]), ("Artist", parts["by_artist"])):
        if found:
            f.write(f"   - {label}: " + ", ".join(
                f"[{names[p]}]({STAFF_URL.format(p)}) (you read {count[p]} of their series)" for p in found) + "\n")


def main():
    mine, _ = my_series()
    tags, authors, artists, count, names = weigh(mine)
    idf = tag_idf()
    pool = candidates(tags, authors, artists, idf) - set(mine)
    print(f"{len(pool)} candidates")

    fetched = {}
    for sid in pool:
        try:
            series = get(f"{API}/series/{sid}")["series"]
        except Exception as e:
            print(f"skipped {sid} ({e})")
            continue
        if not series.get("hidden") and series.get("tags"):
            fetched[sid] = series
    # the pool's own typical share of readers who quit, so the bonus rewards doing better than the others
    quit_, readers = (sum(x) for x in zip(*(reader_counts(s) for s in fetched.values()))) if fetched else (0, 0)
    base = quit_ / readers if readers else BASE_ABANDON
    scored = []
    for sid, series in fetched.items():
        total, parts = score(series, tags, authors, artists, idf, base)
        scored.append((total, sid, series, parts))
    scored.sort(key=lambda row: -row[0])

    today = date.today()
    fresh = [(row, recent_volumes(row[2], today)) for row in scored]
    fresh = [(row, vols) for row, vols in fresh if vols][:NEW_TOP]
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(f"# Recommendations ({datetime.now():%Y-%m-%d})\n\n")
        f.write(f"Series with English releases that you haven't read, ranked by how much their tags, authors and "
                f"artists match what you read (rare tags count more). Small bonuses for a good rating and for few "
                f"readers stalling or dropping it. Picked from {len(scored)} candidates on RanobeDB.\n\n"
                f"## New and upcoming\n\nBest matches with an English volume dated between "
                f"{today - timedelta(days=RECENT_DAYS)} and {today + timedelta(days=UPCOMING_DAYS)}.\n")
        for rank, (row, vols) in enumerate(fresh, 1):
            extra = "   - Volumes: " + ", ".join(f"{label} ({when})" for when, label in vols[:4]) + "\n"
            write_entry(f, rank, row, tags, idf, names, count, extra)
        f.write(f"\n## Top {TOP}\n")
        for rank, row in enumerate(scored[:TOP], 1):
            write_entry(f, rank, row, tags, idf, names, count)
    add_toc(OUTPUT)
    print(f"top {min(TOP, len(scored))} of {len(scored)}, {len(fresh)} new/upcoming -> {OUTPUT}")


if __name__ == "__main__":
    main()
