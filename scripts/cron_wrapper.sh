#!/bin/bash
# Cron wrapper for daily scraper
# Ensures correct working directory and environment

cd /home/info_betsim/reviewsignal-5.0 || exit 1
export GOOGLE_MAPS_API_KEY="<REDACTED_SEE_ENV>"

/usr/bin/python3 scripts/daily_scraper.py
