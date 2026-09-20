"""Run: python3 test_updates.py"""
from updates import VOL_RE, normalize_series, squash, fmt_date


def parse(title):
    m = VOL_RE.match(title)
    return (normalize_series(m.group(1)), int(m.group(2))) if m else (normalize_series(title), None)


assert parse("Bofuri: Max Out My Defense., Vol. 15") == ("Bofuri: Max Out My Defense.", 15)
assert parse("To Another World... with Land Mines! V09") == ("To Another World... with Land Mines", 9)
assert parse("Some Series Volume 3 (Light Novel)") == ("Some Series", 3)
assert parse("Deep Work") == ("Deep Work", None)
assert parse("2026-06-05-22-55-40 Aneko Yusagi; Ryo Ueda -  Dimension Wave_") == ("Dimension Wave", None)
assert parse("Long Story Short - I'm Living in the Mountains Vol. 2") == ("Long Story Short - I'm Living in the Mountains", 2)

# matching: subtitle differences and typography must match, unrelated titles must not
assert squash("Fluffy Cafe in Another World") == squash("Fluffy Café in Another World")
assert squash("Bofuri: I Don’t Want to Get Hurt").startswith(squash("Bofuri: I Don't Want"))
assert squash("Magical★Explorer: Reborn") == squash("Magical Explorer: Reborn")
assert not squash("The Tiny Witch from the Deep Woods").startswith(squash("Deep Work"))

assert fmt_date(20210406) == "2021-04-06"
assert fmt_date(99999999) == "TBA"
assert fmt_date(None) == "TBA"
assert fmt_date(20269999) == "2026"

# volume labels come from the book's own title, not its sort order
from updates import vol_label

assert vol_label("Angel Next Door", "Angel Next Door, Vol. 8.5") == "Vol. 8.5"
assert vol_label("Witch and Mercenary", "Witch and Mercenary Vol. 6: Part 2") == "Vol. 6: Part 2"
assert vol_label("Silent Witch", "サイレント・ウィッチ IX") == "サイレント・ウィッチ IX"

# grouping headings
from updates import month_of

assert month_of(("X", 1, "2026-10-13")) == "October 2026"
assert month_of(("X", 1, "TBA")) == "TBA"
assert month_of(("X", 1, "2026")) == "2026"

print("ok")
