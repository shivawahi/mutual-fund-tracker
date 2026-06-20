#!/bin/bash
# ============================================================
# run_tracker.sh  (Mac / Linux version)
# Schedule THIS file instead of tracker.py directly.
# ============================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
FLAG="$DIR/new_sheet_created.flag"

# Step 1: Run tracker.py
echo "[$(date '+%H:%M:%S')] Running tracker.py..."
"$DIR/venv/bin/python" "$DIR/tracker.py" "$@"
if [ $? -ne 0 ]; then
    echo "[$(date '+%H:%M:%S')] tracker.py failed. Exiting."
    exit 1
fi
echo "[$(date '+%H:%M:%S')] tracker.py completed."

# Step 2: Check for new sheet flag
if [ ! -f "$FLAG" ]; then
    echo "[$(date '+%H:%M:%S')] No new sheet created. Skipping fix_chart_color.py."
    exit 0
fi

MONTH_NAME=$(cat "$FLAG")
echo "[$(date '+%H:%M:%S')] New sheet detected: $MONTH_NAME"
echo "[$(date '+%H:%M:%S')] Running fix_chart_color.py..."

# Step 3: Run fix_chart_color.py
"$DIR/venv/bin/python" "$DIR/fix_chart_color.py" "$MONTH_NAME"
if [ $? -eq 0 ]; then
    echo "[$(date '+%H:%M:%S')] fix_chart_color.py completed successfully."
else
    echo "[$(date '+%H:%M:%S')] fix_chart_color.py failed."
fi

# Step 4: Clear the flag
rm "$FLAG"
echo "[$(date '+%H:%M:%S')] Flag cleared."
exit 0
