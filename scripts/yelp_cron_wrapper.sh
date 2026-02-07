#!/bin/bash
#
# Yelp Cron Wrapper - Daily Yelp review fetching
# ================================================
# Runs daily at 04:00 UTC via cron.
# Processes up to 500 locations per run (~500 API calls, well within 5000/day).
#
# Cron schedule:
#   0 4 * * * /home/info_betsim/reviewsignal-5.0/scripts/yelp_cron_wrapper.sh
#
# API budget: 5000 calls/day. With ~1 call per location (reviews endpoint),
# we can process ~1,600 locations/day. Conservative 500/run leaves room for
# the match script and manual usage.
#
# Last Updated: 2026-02-07
# Author: ReviewSignal.ai
#

set -e

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_DIR="/home/info_betsim/reviewsignal-5.0"
SCRIPT_DIR="${PROJECT_DIR}/scripts"
LOG_DIR="${PROJECT_DIR}/logs"
DATE_STAMP=$(date +%Y%m%d)
LOG_FILE="${LOG_DIR}/yelp_scraper_${DATE_STAMP}.log"

REVIEW_LIMIT=500
MATCH_LIMIT=200

# =============================================================================
# FUNCTIONS
# =============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log_separator() {
    echo "" >> "$LOG_FILE"
    echo "====================================================================" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

# Create log directory if missing
mkdir -p "$LOG_DIR"

# Log header
log_separator
log "YELP CRON WRAPPER - Daily Run"
log_separator

# Load environment variables
if [ -f "${PROJECT_DIR}/.env" ]; then
    export $(grep -v '^#' "${PROJECT_DIR}/.env" | xargs 2>/dev/null)
    log "Environment loaded from .env"
fi

# Check YELP_API_KEY
if [ -z "$YELP_API_KEY" ]; then
    log "ERROR: YELP_API_KEY not set in .env - skipping"
    exit 1
fi

# --- Phase 1: Match unmatched locations ---
log_separator
log "Phase 1: Matching unmatched locations (limit ${MATCH_LIMIT})..."
log_separator

cd "$PROJECT_DIR"
if python3 "${SCRIPT_DIR}/yelp_match_locations.py" --limit "$MATCH_LIMIT" >> "$LOG_FILE" 2>&1; then
    log "Phase 1 DONE: Location matching completed"
else
    EXIT_CODE=$?
    log "Phase 1 WARNING: Location matching exited with code ${EXIT_CODE}"
    # Continue to phase 2 even if matching had issues
fi

# --- Phase 2: Fetch reviews for matched locations ---
log_separator
log "Phase 2: Fetching Yelp reviews (limit ${REVIEW_LIMIT})..."
log_separator

if python3 "${SCRIPT_DIR}/yelp_review_scraper.py" --limit "$REVIEW_LIMIT" >> "$LOG_FILE" 2>&1; then
    log "Phase 2 DONE: Review fetching completed"
else
    EXIT_CODE=$?
    log "Phase 2 ERROR: Review fetching exited with code ${EXIT_CODE}"
fi

# --- Done ---
log_separator
log "Yelp cron job completed at $(date)"
log_separator

# Cleanup old logs (keep 30 days)
find "$LOG_DIR" -name "yelp_scraper_*.log" -mtime +30 -delete 2>/dev/null || true

exit 0
