#!/usr/bin/env bash
# Regenerate every stats file from statistics.sqlite3.
set -euo pipefail
cd "$(dirname "$0")"

for script in monthly yearly book_dates pace wrapped updates
do
    echo "== $script"
    python3 "scripts/$script.py"
done
