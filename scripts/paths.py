"""Where things live, so a script works from any working directory."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "statistics.sqlite3"
STATS = ROOT / "stats"
CACHE_PATH = ROOT / ".ranobedb_cache.json"

STATS.mkdir(exist_ok=True)
