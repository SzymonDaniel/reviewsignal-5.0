#!/bin/bash
# Monthly Reports Cron Wrapper
# Runs on 1st day of each month at 9:00 UTC
# Crontab: 0 9 1 * * /home/info_betsim/reviewsignal-5.0/scripts/monthly_reports_cron.sh

set -e

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/monthly_reports.log"

# Create log directory
mkdir -p "$LOG_DIR"

# Load environment variables
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
fi

# Timestamp
echo "==================================" >> "$LOG_FILE"
echo "Monthly Reports Started: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "==================================" >> "$LOG_FILE"

# Run report generator
cd "$PROJECT_DIR"
/usr/bin/python3 "$PROJECT_DIR/scripts/monthly_report_generator.py" >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

# Log completion
echo "Monthly Reports Completed: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "Exit Code: $EXIT_CODE" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

exit $EXIT_CODE
