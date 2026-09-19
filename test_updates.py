"""Run: python3 test_updates.py"""
from updates import VOL_RE, normalize_series, squash, fmt_date


def parse(title):
    m = VOL_RE.match(title)
    return (normalize_series(m.group(1)), int(m.group(2))) if m else (normalize_series(title), None)


assert parse("Bofuri: Max Out My Defense., Vol. 15") == ("Bofuri: Max Out My Defense.", 15)
assert parse("To Another World... with Land Mines! V09") == ("To Another World... with Land Mines", 9)
assert parse("Some Series Volume 3 (Light Novel)") == ("Some Series", 3)
assert parse("Deep Work") == ("Deep Work", None)

# matching: subtitle differences and typography must match, unrelated titles must not
assert squash("Fluffy Cafe in Another World") == squash("Fluffy Café in Another World")
assert squash("Bofuri: I Don’t Want to Get Hurt").startswith(squash("Bofuri: I Don't Want"))
assert squash("Magical★Explorer: Reborn") == squash("Magical Explorer: Reborn")
assert not squash("The Tiny Witch from the Deep Woods").startswith(squash("Deep Work"))

assert fmt_date(20210406) == "2021-04-06"
assert fmt_date(99999999) == "TBA"
assert fmt_date(None) == "TBA"
assert fmt_date(20269999) == "2026"

print("ok")
