"""Push my reading log to my RanobeDB list. Dry run unless --apply.

Needs a personal access token (RanobeDB settings) as RANOBEDB_TOKEN in .env (see .env.example).
"""
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

import env
from paths import DB_PATH, ROOT
from titles import EXPORT_RE, split_volume


API = "https://ranobedb.org/api/v0"
UA = "my_koreader_stats/1.0"  # ranobedb 403s the default urllib agent
STATE_PATH = ROOT / ".ranobedb_sync.json"

FINISHED_AT = 0.90  # furthest page / total pages; the last pages are often an afterword or ads
MIN_COVERAGE = 0.50  # share of distinct pages viewed; below it the end was skipped to, not read
DELAY = 1.0  # seconds between requests, ranobedb allows 60 per minute
RETRIES = 3


def status(furthest, coverage):
    return "Finished" if furthest >= FINISHED_AT and coverage >= MIN_COVERAGE else "Reading"


def day(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def read_volumes():
    """key -> {title, first, last, furthest, coverage}, merging KOReader entries of the same volume."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT b.title, MIN(ps.start_time), MAX(ps.start_time),
               MAX(1.0 * ps.page / ps.total_pages),
               1.0 * COUNT(DISTINCT ps.page) / MAX(ps.total_pages)
        FROM page_stat_data ps JOIN book b ON b.id = ps.id_book
        WHERE ps.duration > 0 AND ps.total_pages > 0
        GROUP BY b.id
        ORDER BY MIN(ps.start_time)
    """).fetchall()
    conn.close()

    volumes = {}
    for title, first, last, furthest, coverage in rows:
        series, vol = split_volume(title)
        key = f"{series}|{vol}" if vol is not None else f"{series}|"
        v = volumes.setdefault(key, {"title": EXPORT_RE.sub("", title).rstrip("_").strip(), "series": series,
                                     "vol": vol, "first": first, "last": last, "furthest": 0, "coverage": 0})
        v["first"], v["last"] = min(v["first"], first), max(v["last"], last)
        v["furthest"], v["coverage"] = max(v["furthest"], furthest), max(v["coverage"], coverage)
    return volumes


def build_payload(volume, extras):
    done = status(volume["furthest"], volume["coverage"]) == "Finished"
    payload = {
        "readingStatus": "Finished" if done else "Reading",
        "selectedCustLabels": extras.get("selectedCustLabels", []),
        "started": day(volume["first"]),
        "finished": day(volume["last"]) if done else None,
    }
    for field in ("score", "notes"):  # a PUT replaces the entry, so anything stored is sent every time
        if extras.get(field) is not None:
            payload[field] = extras[field]
    return payload


def request(method, path, token, body=None):
    """(status code, parsed body). Retries network errors and 5xx; everything else is the caller's."""
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {token}", "User-Agent": UA, "Content-Type": "application/json"}
    for attempt in range(RETRIES + 1):
        try:
            req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            text = e.read().decode(errors="replace")
            if e.code < 500:
                return e.code, text
            err = f"{e.code}"
        except (urllib.error.URLError, TimeoutError) as e:
            err = str(e)
        if attempt == RETRIES:
            raise SystemExit(f"giving up on {method} {path}: {err}")
        time.sleep(2 ** (attempt + 1))


def search(query):
    url = f"{API}/books?q={urllib.parse.quote(query)}&limit=5"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    time.sleep(DELAY)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode()).get("books") or []


def pick_book(volume):
    """RanobeDB id, None to skip for good, or False to leave undecided this run."""
    if not sys.stdin.isatty():
        return False
    queries = [f"{volume['series']} {volume['vol']}"] if volume["vol"] is not None else []
    queries.append(volume["series"])
    hits = []
    for q in queries:
        hits = search(q)
        if hits:
            break
    print(f"\n{volume['title']}")
    for i, hit in enumerate(hits, 1):
        print(f"  {i}. {hit['title']}  (id {hit['id']})")
    while True:
        try:
            answer = input("  number, RanobeDB id, s = skip for good, enter = decide later, q = quit: ").strip().lower()
        except EOFError:
            return False
        if answer == "q":
            raise SystemExit(0)
        if answer == "s":
            return None
        if answer == "":
            return False
        if answer.isdigit():
            n = int(answer)
            if 1 <= n <= len(hits):
                return hits[n - 1]["id"]
            if n > 5:
                return n


def load_state():
    return json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}


def save_state(state):
    tmp = STATE_PATH.with_suffix(".tmp")  # a crash mid-write must not leave a truncated state file
    tmp.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_PATH)


def load_token():
    token = env.get("RANOBEDB_TOKEN")
    if not token:
        raise SystemExit("no token: set RANOBEDB_TOKEN in .env (copy .env.example)")
    return token


def run(apply, pick):
    """pick(volume) -> id, None (skip for good) or False (decide later)."""
    sys.stdout.reconfigure(errors="replace")  # Windows consoles can't print Japanese titles
    token = load_token() if apply else None
    if apply:
        code, body = request("GET", "/user/me", token)
        if code != 200:
            raise SystemExit(f"token rejected ({code}): {body}")
        print(f"syncing as {body['username']}")

    state = load_state()
    volumes = read_volumes()
    sent = unchanged = unmatched = failed = 0

    for key, volume in volumes.items():
        entry = state.setdefault(key, {})
        if "id" not in entry:
            choice = pick(volume)
            if choice is False:
                unmatched += 1
                del state[key]
                continue
            entry["id"] = choice
            save_state(state)
        if entry["id"] is None:
            continue

        payload = build_payload(volume, entry)
        if payload == entry.get("sent"):
            unchanged += 1
            continue
        if not apply:
            print(f"would send {entry['id']} {volume['title']}: {json.dumps(payload)}")
            sent += 1
            continue

        time.sleep(DELAY)
        code, body = request("PUT", f"/user/book/{entry['id']}", token, payload)
        if code == 401:
            raise SystemExit("401: token rejected, stopping")
        if code != 200:
            print(f"{code} for {volume['title']} (id {entry['id']}): {body}")
            failed += 1
            continue
        entry["sent"] = payload
        save_state(state)
        print(f"{body['action']} {entry['id']} {volume['title']} -> {payload['readingStatus']}")
        sent += 1

    verb = "sent" if apply else "would send"
    print(f"{verb} {sent}, unchanged {unchanged}, unmatched {unmatched}, failed {failed}"
          + ("" if apply else " (dry run, pass --apply to send)"))


if __name__ == "__main__":
    run("--apply" in sys.argv, pick_book)
