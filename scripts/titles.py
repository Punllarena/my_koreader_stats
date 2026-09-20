"""Parsing KOReader book titles into a series name and a volume number."""
import re

VOL_RE = re.compile(r'^(.*?)\s+(?:Vol\.|Volume|V)\s*(\d+)', re.IGNORECASE)
PAREN_RE = re.compile(r'\s*\([^)]*\)\s*$')  # trailing parenthetical e.g. "(Light Novel)"
EXPORT_RE = re.compile(r'^\d{4}(?:-\d{2}){5}\s+.*?\s+-\s+')  # "<timestamp> <authors> - Title_" export filename


def normalize_series(title):
    title = EXPORT_RE.sub('', title).rstrip('_')
    return PAREN_RE.sub('', title).rstrip(' ,:!').strip()


def split_volume(title):
    """(series, volume number or None)."""
    m = VOL_RE.match(title)
    if m:
        return normalize_series(m.group(1)), int(m.group(2))
    return normalize_series(title), None
