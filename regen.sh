#!/usr/bin/env bash
# Regenerate every stats file from statistics.sqlite3.
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
