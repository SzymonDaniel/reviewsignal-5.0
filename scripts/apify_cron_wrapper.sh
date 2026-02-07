#!/usr/bin/env bash
# ============================================================================
# Apify Google Reviews - Daily Cron Wrapper
# ============================================================================
#
# Runs a daily incremental fetch of Google Maps reviews via Apify.
# Targets locations with the oldest review data first.
# Enforces a configurable daily spend limit (default $1.00/day).
#
# Installation (crontab -e):
#   # Run daily at 04:00 UTC
#   0 4 * * * /home/info_betsim/reviewsignal-5.0/scripts/apify_cron_wrapper.sh >> /var/log/reviewsignal/apify_cron.log 2>&1
#
# Manual run:
#   APIFY_DAILY_BUDGET=2.00 APIFY_MAX_REVIEWS=200 ./scripts/apify_cron_wrapper.sh
#
# ============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration (override via env vars)
# ---------------------------------------------------------------------------
PROJECT_DIR="/home/info_betsim/reviewsignal-5.0"
VENV_PYTHON="${PROJECT_DIR}/venv/bin/python3"
SCRIPT="${PROJECT_DIR}/scripts/apify_google_reviews.py"
LOG_DIR="/var/log/reviewsignal"
STATE_FILE="${PROJECT_DIR}/scripts/.apify_cron_state"

# Tunables
DAILY_BUDGET="${APIFY_DAILY_BUDGET:-1.00}"       # Max USD per day
MAX_REVIEWS="${APIFY_MAX_REVIEWS:-100}"           # Reviews per location (lower = cheaper)
BATCH_LIMIT="${APIFY_BATCH_LIMIT:-20}"            # Locations per run
LOCK_FILE="/tmp/apify_cron.lock"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log_msg() {
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"
}

cleanup() {
    rm -f "${LOCK_FILE}"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

# Ensure log directory exists
if [ ! -d "${LOG_DIR}" ]; then
    mkdir -p "${LOG_DIR}" 2>/dev/null || true
fi

# Prevent overlapping runs
if [ -f "${LOCK_FILE}" ]; then
    LOCK_PID=$(cat "${LOCK_FILE}" 2>/dev/null || echo "")
    if [ -n "${LOCK_PID}" ] && kill -0 "${LOCK_PID}" 2>/dev/null; then
        log_msg "ERROR: Another apify cron is already running (PID ${LOCK_PID}). Exiting."
        exit 0
    fi
    log_msg "WARN: Stale lock file found. Removing."
    rm -f "${LOCK_FILE}"
fi
echo $$ > "${LOCK_FILE}"

# Check python
if [ ! -x "${VENV_PYTHON}" ]; then
    log_msg "ERROR: Python not found at ${VENV_PYTHON}. Trying system python3."
    VENV_PYTHON="python3"
fi

# Check script exists
if [ ! -f "${SCRIPT}" ]; then
    log_msg "ERROR: Script not found: ${SCRIPT}"
    exit 1
fi

# Load .env for APIFY_API_KEY check
if [ -f "${PROJECT_DIR}/.env" ]; then
    # shellcheck disable=SC2046
    export $(grep -v '^#' "${PROJECT_DIR}/.env" | grep -v '^\s*$' | xargs)
fi

if [ -z "${APIFY_API_KEY:-}" ]; then
    log_msg "ERROR: APIFY_API_KEY is not set in .env. Skipping run."
    exit 1
fi

# ---------------------------------------------------------------------------
# Track daily spend
# ---------------------------------------------------------------------------
TODAY=$(date -u '+%Y-%m-%d')

# State file format: DATE SPENT_USD
LAST_DATE=""
SPENT_TODAY="0.00"

if [ -f "${STATE_FILE}" ]; then
    LAST_DATE=$(awk '{print $1}' "${STATE_FILE}" 2>/dev/null || echo "")
    SPENT_TODAY=$(awk '{print $2}' "${STATE_FILE}" 2>/dev/null || echo "0.00")
fi

# Reset counter if it is a new day
if [ "${LAST_DATE}" != "${TODAY}" ]; then
    SPENT_TODAY="0.00"
fi

# Check if we already exceeded the daily budget
OVER_BUDGET=$(awk "BEGIN {print (${SPENT_TODAY} >= ${DAILY_BUDGET}) ? 1 : 0}")
if [ "${OVER_BUDGET}" -eq 1 ]; then
    log_msg "Daily budget exhausted (\$${SPENT_TODAY} / \$${DAILY_BUDGET}). Skipping."
    exit 0
fi

REMAINING=$(awk "BEGIN {printf \"%.2f\", ${DAILY_BUDGET} - ${SPENT_TODAY}}")

log_msg "=== APIFY CRON START ==="
log_msg "Budget: \$${REMAINING} remaining of \$${DAILY_BUDGET}/day (spent \$${SPENT_TODAY})"
log_msg "Config: max_reviews=${MAX_REVIEWS}, batch_limit=${BATCH_LIMIT}"

# ---------------------------------------------------------------------------
# Run the scraper
# ---------------------------------------------------------------------------
# Use --backfill with --oldest-first to always target the stalest locations.
# The --budget flag ensures we never exceed the remaining daily budget.
START_TIME=$(date +%s)

set +e  # Allow non-zero exit (we still want to track spend)
OUTPUT=$("${VENV_PYTHON}" "${SCRIPT}" \
    --backfill \
    --oldest-first \
    --limit "${BATCH_LIMIT}" \
    --max-reviews "${MAX_REVIEWS}" \
    --budget "${REMAINING}" \
    2>&1)
EXIT_CODE=$?
set -e

END_TIME=$(date +%s)
ELAPSED=$(( END_TIME - START_TIME ))

# Log output
echo "${OUTPUT}"

if [ ${EXIT_CODE} -ne 0 ]; then
    log_msg "WARNING: Script exited with code ${EXIT_CODE}"
fi

# ---------------------------------------------------------------------------
# Parse cost from output and update state
# ---------------------------------------------------------------------------
# Try to extract cost from the "Estimated cost:" line in output
RUN_COST=$(echo "${OUTPUT}" | grep -oP 'Estimated cost:\s+\$\K[0-9.]+' || echo "0.00")
if [ -z "${RUN_COST}" ]; then
    RUN_COST="0.00"
fi

NEW_SPENT=$(awk "BEGIN {printf \"%.2f\", ${SPENT_TODAY} + ${RUN_COST}}")
echo "${TODAY} ${NEW_SPENT}" > "${STATE_FILE}"

# ---------------------------------------------------------------------------
# Parse stats from output
# ---------------------------------------------------------------------------
REVIEWS_SAVED=$(echo "${OUTPUT}" | grep -oP 'Reviews saved:\s+\K[0-9]+' || echo "0")
LOCATIONS_DONE=$(echo "${OUTPUT}" | grep -oP 'Locations processed:\s+\K[0-9]+' || echo "0")
ERRORS=$(echo "${OUTPUT}" | grep -oP 'Errors:\s+\K[0-9]+' || echo "0")

log_msg "=== APIFY CRON DONE ==="
log_msg "Locations: ${LOCATIONS_DONE}, Reviews: ${REVIEWS_SAVED}, Errors: ${ERRORS}"
log_msg "Run cost: \$${RUN_COST}, Daily total: \$${NEW_SPENT} / \$${DAILY_BUDGET}"
log_msg "Elapsed: ${ELAPSED}s"

# ---------------------------------------------------------------------------
# Alert on high error rate
# ---------------------------------------------------------------------------
if [ "${ERRORS:-0}" -gt 0 ] && [ "${LOCATIONS_DONE:-0}" -gt 0 ]; then
    ERROR_RATE=$(awk "BEGIN {printf \"%.0f\", (${ERRORS} / ${LOCATIONS_DONE}) * 100}")
    if [ "${ERROR_RATE}" -gt 50 ]; then
        log_msg "ALERT: High error rate (${ERROR_RATE}%). Check Apify API key and quotas."
    fi
fi

exit 0
