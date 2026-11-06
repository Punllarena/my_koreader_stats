"""Like sync_ranobedb.py, but never asks: sends straight away and only matches books it is sure of.

A volume is matched when exactly one search hit has the same series and the same volume number.
Anything else is left unmatched (listed in the summary); run sync_ranobedb.py to settle those.
Pass --dry-run to see what would be sent.
"""
import sys

from sync_ranobedb import run, search
from titles import split_volume
from updates import squash


def pick_confident(volume):
    if volume["vol"] is None:
        return False
    mine = squash(volume["series"])
    hits = []
    for hit in search(f"{volume['series']} {volume['vol']}"):
        series, vol = split_volume(hit["title"])
        theirs = squash(series)
        if vol == volume["vol"] and (mine.startswith(theirs) or theirs.startswith(mine)):
            hits.append(hit)
    return hits[0]["id"] if len(hits) == 1 else False


if __name__ == "__main__":
    run("--dry-run" not in sys.argv, pick_confident)
