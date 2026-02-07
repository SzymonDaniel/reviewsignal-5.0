#!/usr/bin/env python3
"""
YELP REVIEW SCRAPER - Focused script for fetching Yelp reviews.

Queries locations that already have a yelp_business_id (matched) but fewer
than 3 Yelp reviews. Fetches reviews via the Yelp Fusion API, validates them,
scores sentiment, and saves to the reviews table with source='yelp'.

Designed to run daily via cron, processing up to 500 locations per run
(~500 API calls = well within the 5000/day limit).

Usage:
  python3 scripts/yelp_review_scraper.py                  # Default 500 locations
  python3 scripts/yelp_review_scraper.py --limit 200      # Custom limit
  python3 scripts/yelp_review_scraper.py --chain-name "Starbucks"
  python3 scripts/yelp_review_scraper.py --dry-run        # Preview only
"""

import sys
import os
import time
import hashlib
import argparse
from datetime import datetime
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from psycopg2.extras import RealDictCursor
from modules.db import get_connection, return_connection
from modules.data_validator import ReviewValidator
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
log = structlog.get_logger()

YELP_API_KEY = os.getenv("YELP_API_KEY", "")

# Minimum Yelp reviews before we skip a location
MIN_YELP_REVIEWS = 3
# Progress log interval
PROGRESS_INTERVAL = 25


def generate_review_hash(location_id: int, author_name: str, rating: int,
                         time_posted: str) -> str:
    """Generate a unique hash for Yelp review deduplication."""
    raw = "yelp:{}:{}:{}:{}".format(location_id, author_name, rating, time_posted)
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_locations_needing_reviews(
    conn,
    chain_name: Optional[str] = None,
    limit: int = 500,
) -> List[dict]:
    """
    Get locations that have a yelp_business_id but fewer than MIN_YELP_REVIEWS
    reviews from Yelp.
    """
    conditions = [
        "l.extra_data->>'yelp_business_id' IS NOT NULL",
        "length(l.extra_data->>'yelp_business_id') > 0",
    ]
    params: list = []

    if chain_name:
        conditions.append("c.name = %s")
        params.append(chain_name)

    where = " AND ".join(conditions)
    params.extend([MIN_YELP_REVIEWS, limit])

    query = (
        "SELECT l.id, l.name, l.city, l.chain_name, "
        "l.extra_data->>'yelp_business_id' AS yelp_business_id, "
        "(SELECT COUNT(*) FROM reviews r "
        "   WHERE r.location_id = l.id AND r.source = 'yelp') AS yelp_review_count "
        "FROM locations l "
        "LEFT JOIN chains c ON l.chain_id = c.id "
        "WHERE {} "
        "HAVING (SELECT COUNT(*) FROM reviews r "
        "   WHERE r.location_id = l.id AND r.source = 'yelp') < %s "
        "ORDER BY yelp_review_count ASC, l.id "
        "LIMIT %s".format(where)
    )
    # The HAVING on a non-grouped query may need a subquery approach; use a
    # wrapping subquery instead for clarity and portability.
    # Re-write with a cleaner approach:
    subquery = (
        "SELECT l.id, l.name, l.city, l.chain_name, "
        "l.extra_data->>'yelp_business_id' AS yelp_business_id "
        "FROM locations l "
        "LEFT JOIN chains c ON l.chain_id = c.id "
        "WHERE {}".format(where)
    )

    full_query = (
        "SELECT sub.id, sub.name, sub.city, sub.chain_name, "
        "sub.yelp_business_id, "
        "(SELECT COUNT(*) FROM reviews r "
        "   WHERE r.location_id = sub.id AND r.source = 'yelp') AS yelp_review_count "
        "FROM ({}) sub "
        "WHERE (SELECT COUNT(*) FROM reviews r "
        "   WHERE r.location_id = sub.id AND r.source = 'yelp') < %s "
        "ORDER BY yelp_review_count ASC, sub.id "
        "LIMIT %s".format(subquery)
    )

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(full_query, params)
        return cur.fetchall()


def save_reviews(conn, location_id: int, reviews: List[dict]) -> int:
    """Save Yelp reviews to the reviews table. Returns count of new inserts."""
    if not reviews:
        return 0

    saved = 0
    with conn.cursor() as cur:
        for review in reviews:
            author = review.get("author_name", "Anonymous")
            rating = review.get("rating", 0)
            text = review.get("text", "")
            time_posted = review.get("time_posted", "")
            language = review.get("language", "en")

            # Validate
            rev_dict = {"text": text, "rating": rating, "author_name": author}
            rev_valid, _issues = ReviewValidator.validate(rev_dict)
            if not rev_valid:
                continue

            review_hash = generate_review_hash(location_id, author, rating, time_posted)

            try:
                cur.execute(
                    "INSERT INTO reviews "
                    "(location_id, author_name, rating, text, time_posted, "
                    "language, source, review_hash, sentiment_score, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, 'yelp', %s, %s, NOW()) "
                    "ON CONFLICT (review_hash) DO NOTHING",
                    (
                        location_id,
                        author,
                        rating,
                        text,
                        time_posted,
                        language,
                        review_hash,
                        rev_dict.get("sentiment_score"),
                    ),
                )
                if cur.rowcount > 0:
                    saved += 1
            except Exception as e:
                log.warning("review_insert_error", location_id=location_id, error=str(e))
                continue

    if saved > 0:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE locations SET review_count = "
                "(SELECT COUNT(*) FROM reviews WHERE location_id = %s) "
                "WHERE id = %s",
                (location_id, location_id),
            )
    conn.commit()
    return saved


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fetch Yelp reviews for matched locations"
    )
    parser.add_argument("--chain-name", type=str, default=None,
                        help="Target a specific chain")
    parser.add_argument("--limit", type=int, default=500,
                        help="Max locations to process (default: 500)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview locations without API calls")
    args = parser.parse_args()

    # --- Pre-flight ---
    scraper = None
    if not args.dry_run:
        if not YELP_API_KEY:
            log.error("YELP_API_KEY not set in environment")
            sys.exit(1)
        try:
            from modules.yelp_scraper import YelpScraper
        except ImportError as e:
            log.error(
                "yelp_scraper_import_failed",
                error=str(e),
                hint="modules/yelp_scraper.py is not available yet.",
            )
            sys.exit(1)
        scraper = YelpScraper(api_key=YELP_API_KEY)

    conn = get_connection()

    # --- Get locations needing reviews ---
    locations = get_locations_needing_reviews(
        conn, chain_name=args.chain_name, limit=args.limit,
    )

    log.info("=" * 70)
    log.info(
        "YELP REVIEW SCRAPER START",
        locations_found=len(locations),
        chain_filter=args.chain_name or "ALL",
        limit=args.limit,
        dry_run=args.dry_run,
    )

    if not locations:
        log.info("No locations need Yelp reviews. Nothing to do.")
        return_connection(conn)
        return

    # Chain breakdown
    chain_counts: dict = {}
    for loc in locations:
        c = loc.get("chain_name") or "Unknown"
        chain_counts[c] = chain_counts.get(c, 0) + 1
    log.info("Chain breakdown:")
    for c, cnt in sorted(chain_counts.items(), key=lambda x: -x[1]):
        log.info("  {}: {} locations".format(c, cnt))

    if args.dry_run:
        log.info("DRY RUN - no API calls made.")
        return_connection(conn)
        return

    # --- Process ---
    total_reviews_saved = 0
    locations_with_new_reviews = 0
    locations_no_reviews = 0
    errors = 0
    api_calls = 0
    start_time = time.time()

    for i, loc in enumerate(locations):
        loc_id = loc["id"]
        yelp_id = loc["yelp_business_id"]

        try:
            raw_reviews = scraper.get_business_reviews(yelp_id)
            api_calls += 1

            if raw_reviews:
                saved = save_reviews(conn, loc_id, raw_reviews)
                total_reviews_saved += saved
                if saved > 0:
                    locations_with_new_reviews += 1
                else:
                    locations_no_reviews += 1
            else:
                locations_no_reviews += 1

        except Exception as e:
            errors += 1
            log.warning(
                "review_fetch_error",
                location_id=loc_id,
                yelp_id=yelp_id,
                error=str(e),
            )

        # Progress
        processed = i + 1
        if processed % PROGRESS_INTERVAL == 0:
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            log.info(
                "Progress: {}/{} | {} reviews saved | {} with data | "
                "{} errors | {:.1f} loc/s | {:.0f}s".format(
                    processed, len(locations), total_reviews_saved,
                    locations_with_new_reviews, errors, rate, elapsed,
                )
            )

        # Rate limit: ~2 req/s
        time.sleep(0.5)

    elapsed = time.time() - start_time
    total_processed = locations_with_new_reviews + locations_no_reviews + errors

    # --- Summary ---
    log.info("=" * 70)
    log.info("YELP REVIEW SCRAPER DONE")
    log.info("Locations processed:     {}".format(total_processed))
    log.info("Locations with reviews:  {}".format(locations_with_new_reviews))
    log.info("Locations no reviews:    {}".format(locations_no_reviews))
    log.info("Total reviews saved:     {}".format(total_reviews_saved))
    log.info("API calls:               {}".format(api_calls))
    log.info("Errors:                  {}".format(errors))
    log.info("Duration:                {:.0f}s ({:.1f}min)".format(elapsed, elapsed / 60))
    if elapsed > 0:
        log.info("Rate:                    {:.1f} locations/sec".format(
            total_processed / elapsed))
    log.info("=" * 70)

    return_connection(conn)


if __name__ == "__main__":
    main()
