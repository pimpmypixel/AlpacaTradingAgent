#!/bin/bash
# Wrapper for cron: activates the venv, runs the daily analysis, logs output.
# Installed via crontab -e; see README section "Cron automation" or ask
# Claude to (re)install it.
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_DIR/logs"
mkdir -p "$LOG_DIR"

cd "$REPO_DIR"
source .venv/bin/activate

LOG_FILE="$LOG_DIR/cron_$(date +\%Y-\%m-\%d).log"
python scripts/cron_daily_analysis.py "$@" >> "$LOG_FILE" 2>&1
STATUS=$?
echo "exit code: $STATUS" >> "$LOG_FILE"
exit "$STATUS"
