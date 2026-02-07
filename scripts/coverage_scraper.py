#!/usr/bin/env python3
"""
COVERAGE SCRAPER - Aggressive review backfill for uncovered locations
Runs every 2 hours via cron. Processes 200 locations per run.

Target: 80%+ locations with reviews (currently ~42%)
At 200 locations/2h = 2,400/day -> full coverage in ~11 days

Usage:
  python3 scripts/coverage_scraper.py                  # Default 200 locations
  python3 scripts/coverage_scraper.py --batch 500      # Custom batch size
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from psycopg2.extras import RealDictCursor
from modules.db import get_connection, return_connection
from datetime import datetime
import time
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
log = structlog.get_logger()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")


def get_coverage_stats(conn):
    """Get current review coverage stats."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM locations")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT location_id) FROM reviews WHERE location_id IS NOT NULL")
        with_reviews = cur.fetchone()[0]
        return total, with_reviews


def get_uncovered_locations(conn, limit=200):
    """Get locations without any reviews, prioritizing those with chain_id."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT l.id, l.place_id, l.name, l.chain_name
            FROM locations l
            LEFT JOIN reviews r ON r.location_id = l.id
            WHERE r.id IS NULL
            AND l.place_id IS NOT NULL
            AND l.place_id LIKE 'ChIJ%%'
            ORDER BY
                CASE WHEN l.chain_id IS NOT NULL THEN 0 ELSE 1 END,
                l.id
            LIMIT %s
        """, (limit,))
        return cur.fetchall()


def scrape_and_save(conn, scraper, location):
    """Scrape reviews for one location and save to DB."""
    place_id = location['place_id']
    loc_id = location['id']

    try:
        details = scraper.get_place_details(place_id)
        if not details or not details.reviews:
            return 0

        saved = 0
        with conn.cursor() as cur:
            for review in details.reviews:
                try:
                    cur.execute("""
                        INSERT INTO reviews (location_id, author_name, rating, text, time_posted, language, source)
                        VALUES (%s, %s, %s, %s, to_timestamp(%s), %s, 'google_maps')
                        ON CONFLICT DO NOTHING
                    """, (
                        loc_id,
                        review.get('author_name', 'Anonymous'),
                        review.get('rating', 0),
                        review.get('text', ''),
                        review.get('time', 0),
                        review.get('language', 'en'),
                    ))
                    if cur.rowcount > 0:
                        saved += 1
                except Exception:
                    continue

            # Update location review_count
            cur.execute("""
                UPDATE locations SET review_count = (
                    SELECT COUNT(*) FROM reviews WHERE location_id = %s
                ) WHERE id = %s
            """, (loc_id, loc_id))

        conn.commit()
        return saved

    except Exception as e:
        log.error(f"Error scraping {place_id}: {e}")
        conn.rollback()
        return 0


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=int, default=200, help='Locations per run')
    args = parser.parse_args()

    if not GOOGLE_MAPS_API_KEY:
        log.error("GOOGLE_MAPS_API_KEY not set")
        sys.exit(1)

    from modules.real_scraper import GoogleMapsRealScraper
    scraper = GoogleMapsRealScraper(api_key=GOOGLE_MAPS_API_KEY)

    conn = get_connection()

    # Stats before
    total, with_reviews = get_coverage_stats(conn)
    coverage_before = round(with_reviews / total * 100, 1) if total > 0 else 0
    log.info(f"=== COVERAGE SCRAPER START === Coverage: {with_reviews}/{total} ({coverage_before}%)")

    # Get uncovered locations
    locations = get_uncovered_locations(conn, limit=args.batch)
    log.info(f"Found {len(locations)} uncovered locations to process")

    if not locations:
        log.info("All locations covered! Nothing to do.")
        return_connection(conn)
        return

    # Process
    total_reviews = 0
    locations_with_reviews = 0
    start_time = time.time()

    for i, loc in enumerate(locations):
        saved = scrape_and_save(conn, scraper, loc)
        total_reviews += saved
        if saved > 0:
            locations_with_reviews += 1

        if (i + 1) % 50 == 0:
            elapsed = time.time() - start_time
            log.info(f"Progress: {i+1}/{len(locations)} locations, {total_reviews} reviews saved ({elapsed:.0f}s)")

        # Rate limit: ~2 req/sec for Google Maps API
        time.sleep(0.5)

    elapsed = time.time() - start_time

    # Stats after
    total_after, with_reviews_after = get_coverage_stats(conn)
    coverage_after = round(with_reviews_after / total_after * 100, 1) if total_after > 0 else 0

    log.info(f"=== COVERAGE SCRAPER DONE ===")
    log.info(f"Processed: {len(locations)} locations in {elapsed:.0f}s")
    log.info(f"Reviews saved: {total_reviews}")
    log.info(f"Locations with new reviews: {locations_with_reviews}")
    log.info(f"Coverage: {coverage_before}% -> {coverage_after}% ({with_reviews_after}/{total_after})")

    return_connection(conn)


if __name__ == "__main__":
    main()
