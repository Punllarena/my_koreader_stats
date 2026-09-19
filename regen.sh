#!/usr/bin/env bash
# Regenerate every stats file from statistics.sqlite3.
# ponytail: stat_output.py is skipped - koreader_monthly_human_dates_and_streaks.py
# writes the same koreader_monthly_stats/*.md files with more detail.
set -euo pipefail
cd "$(dirname "$0")"

for script in \
    koreader_monthly_human_dates_and_streaks.py \
    stat_output_yearly.py \
    book_dates.py \
    updates.py
do
    echo "== $script"
    python3 "$script"
done
