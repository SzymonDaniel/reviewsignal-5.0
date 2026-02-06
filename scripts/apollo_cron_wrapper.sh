#!/bin/bash
#
# Apollo Cron Wrapper v2.0 - INTENT-POWERED AUTO PAGINATION
# ============================================================
# Runs Apollo lead search with automatic page tracking and intent filtering.
#
# Features:
# - Auto-pagination (cycles through pages 1-50)
# - Intent data detection (uses intent search when available)
# - Automatic script selection (intent vs standard)
# - Comprehensive logging
#
# Usage: Called by cron 2x daily (09:00 and 21:00 UTC)
#
# Schedule: 0 9,21 * * * /home/info_betsim/reviewsignal-5.0/scripts/apollo_cron_wrapper.sh
#
# Last Updated: 2026-02-05
# Author: ReviewSignal.ai
#

set -e

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR="/home/info_betsim/reviewsignal-5.0/scripts"
LOG_DIR="/home/info_betsim/reviewsignal-5.0/logs"
DATE_STAMP=$(date +%Y%m%d)
LOG_FILE="$LOG_DIR/apollo_intent_${DATE_STAMP}.log"
PAGE_FILE="$SCRIPT_DIR/.apollo_current_page"
INTENT_FLAG_FILE="$SCRIPT_DIR/.apollo_intent_enabled"
INTENT_ENABLED_DATE="2026-02-06"  # 24h after intent topics configured

# Intent search settings
INTENT_MIN_SCORE=50              # Minimum intent score to prioritize
BATCH_SIZE=63                    # Leads per page
MAX_PAGE=50                      # Reset to page 1 after this

# Scripts
INTENT_SCRIPT="apollo_intent_search.py"
STANDARD_SCRIPT="apollo_bulk_search.py"

# =============================================================================
# FUNCTIONS
# =============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log_separator() {
    echo "" >> "$LOG_FILE"
    echo "════════════════════════════════════════════════════════════════════" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
}

check_intent_available() {
    # Check if we're past the 24h waiting period for intent data
    TODAY=$(date +%Y-%m-%d)
    if [[ "$TODAY" > "$INTENT_ENABLED_DATE" ]] || [[ "$TODAY" == "$INTENT_ENABLED_DATE" ]]; then
        return 0  # Intent data should be available
    else
        return 1  # Still waiting for intent data
    fi
}

select_script() {
    # Determine which script to use
    if check_intent_available && [ -f "$SCRIPT_DIR/$INTENT_SCRIPT" ]; then
        echo "$INTENT_SCRIPT"
    else
        echo "$STANDARD_SCRIPT"
    fi
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

# Create directories
mkdir -p "$LOG_DIR"

# Log header
log_separator
log "🚀 APOLLO CRON WRAPPER v2.0 - INTENT POWERED"
log_separator

# Load environment variables
if [ -f /home/info_betsim/reviewsignal-5.0/.env ]; then
    export $(grep -v '^#' /home/info_betsim/reviewsignal-5.0/.env | xargs 2>/dev/null)
    log "✅ Environment loaded from .env"
fi

# Get current page
if [ -f "$PAGE_FILE" ]; then
    CURRENT_PAGE=$(cat "$PAGE_FILE")
else
    CURRENT_PAGE=1
    echo $CURRENT_PAGE > "$PAGE_FILE"
fi
log "📄 Current page: $CURRENT_PAGE"

# Select script based on intent availability
SELECTED_SCRIPT=$(select_script)
log "📜 Selected script: $SELECTED_SCRIPT"

if [ "$SELECTED_SCRIPT" == "$INTENT_SCRIPT" ]; then
    log "🔥 INTENT MODE ACTIVE - Prioritizing high-intent leads!"
    SCRIPT_ARGS="--batch-size $BATCH_SIZE --page $CURRENT_PAGE --analyze-intent"
else
    log "📊 Standard mode - Intent data not yet available"
    log "   (Intent topics configured, waiting until $INTENT_ENABLED_DATE)"
    SCRIPT_ARGS="--batch-size $BATCH_SIZE --page $CURRENT_PAGE"
fi

log_separator
log "🏃 Starting lead search..."
log_separator

# Change to script directory and run
cd "$SCRIPT_DIR"

# Run the selected script
if python3 "$SELECTED_SCRIPT" $SCRIPT_ARGS >> "$LOG_FILE" 2>&1; then
    EXIT_CODE=0
    log_separator
    log "✅ Script completed successfully"

    # Increment page for next run
    NEXT_PAGE=$((CURRENT_PAGE + 1))

    # Reset to page 1 after MAX_PAGE
    if [ $NEXT_PAGE -gt $MAX_PAGE ]; then
        NEXT_PAGE=1
        log "🔄 Completed full cycle - resetting to page 1"
    fi

    echo $NEXT_PAGE > "$PAGE_FILE"
    log "➡️  Next page: $NEXT_PAGE"
else
    EXIT_CODE=$?
    log_separator
    log "❌ Script failed with exit code: $EXIT_CODE"
    log "⚠️  Keeping current page: $CURRENT_PAGE for retry"
fi

# Log completion
log_separator
log "🏁 Cron job completed at $(date)"
log_separator

# Cleanup old logs (keep 30 days)
find "$LOG_DIR" -name "apollo_*.log" -mtime +30 -delete 2>/dev/null || true

# Return exit code
exit $EXIT_CODE
