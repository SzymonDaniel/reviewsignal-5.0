#!/usr/bin/env python3
"""
RESCRAPE REVIEWS - Re-fetch reviews for locations with <= 5 reviews using multi-sort.

The Google Places API returns at most 5 reviews per request. With the multi-sort
approach (requesting both most_relevant and newest sort orders), we can get up to
10 unique reviews per location. This script rescrapes locations that currently have
<= 5 reviews to take advantage of this improvement.

Usage:
    python3 scripts/rescrape_reviews.py --chain-name "Starbucks"
    python3 scripts/rescrape_reviews.py --chain-name "McDonald's" --limit 50
    python3 scripts/rescrape_reviews.py --chain-name "Starbucks" --dry-run
    python3 scripts/rescrape_reviews.py --all --limit 100

Author: ReviewSignal Team
Date: February 2026
"""

import sys
import os
import argparse
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
log = structlog.get_logger()


GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")


def get_locations_to_rescrape(conn, chain_name=None, limit=1000):
    """Get locations with <= 5 reviews that need rescraping.

    Only targets locations with valid Google Maps place_ids (ChIJ prefix)
    that already have some reviews but could benefit from multi-sort fetching.

    Args:
        conn: PostgreSQL connection
        chain_name: Optional chain name filter (e.g., "Starbucks")
        limit: Maximum number of locations to return

    Returns:
        List of dicts with id, place_id, name, chain_name, review_count
    """
    from psycopg2.extras import RealDictCursor

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if chain_name:
            cur.execute("""
                SELECT l.id, l.place_id, l.name, l.chain_name,
                       (SELECT COUNT(*) FROM reviews r WHERE r.location_id = l.id) as current_review_count
                FROM locations l
                WHERE l.place_id LIKE 'ChIJ%%'
                AND l.chain_name ILIKE %s
                AND (SELECT COUNT(*) FROM reviews r WHERE r.location_id = l.id) > 0
                AND (SELECT COUNT(*) FROM reviews r WHERE r.location_id = l.id) <= 5
                ORDER BY l.chain_name, l.city, l.id
                LIMIT %s
            """, (chain_name, limit))
        else:
            cur.execute("""
                SELECT l.id, l.place_id, l.name, l.chain_name,
                       (SELECT COUNT(*) FROM reviews r WHERE r.location_id = l.id) as current_review_count
                FROM locations l
                WHERE l.place_id LIKE 'ChIJ%%'
                AND (SELECT COUNT(*) FROM reviews r WHERE r.location_id = l.id) > 0
                AND (SELECT COUNT(*) FROM reviews r WHERE r.location_id = l.id) <= 5
                ORDER BY l.chain_name, l.city, l.id
                LIMIT %s
            """, (limit,))
        return cur.fetchall()


def save_new_reviews(conn, location_id, place_id, reviews):
    """Save new reviews to database, skipping duplicates.

    Uses review_hash (place_id + author_name + timestamp) for deduplication
    in production_scraper style, and falls back to ON CONFLICT DO NOTHING
    for mass_review_scraper style tables.

    Args:
        conn: PostgreSQL connection
        location_id: Database ID of the location
        place_id: Google Place ID
        reviews: List of review dicts from the scraper

    Returns:
        Number of new reviews saved
    """
    if not reviews:
        return 0

    saved = 0
    with conn.cursor() as cur:
        for review in reviews:
            try:
                author_name = review.get('author_name', 'Anonymous')
                rating = review.get('rating', 0)
                text = review.get('text', '')
                review_time = review.get('time', 0)
                language = review.get('language', 'en')

                # Build review_hash for dedup (same as production_scraper.py)
                review_hash = f"{place_id}_{author_name}_{review_time}"

                # Check if review already exists
                cur.execute(
                    "SELECT id FROM reviews WHERE review_hash = %s",
                    (review_hash,)
                )
                if cur.fetchone():
                    continue  # Already exists

                # Try inserting with review_hash
                cur.execute("""
                    INSERT INTO reviews (
                        location_id, place_id, author_name, rating,
                        text, time_posted, language, source,
                        review_hash, created_at
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, to_timestamp(%s), %s, %s,
                        %s, NOW()
                    )
                """, (
                    location_id, place_id, author_name, rating,
                    text, review_time, language, 'google_maps',
                    review_hash
                ))
                saved += 1

            except Exception as e:
                log.warning("review_save_skip", error=str(e), author=author_name)
                conn.rollback()
                continue

        # Update review_count in locations table
        if saved > 0:
            cur.execute("""
                UPDATE locations
                SET review_count = (
                    SELECT COUNT(*) FROM reviews WHERE location_id = %s
                ),
                updated_at = NOW()
                WHERE id = %s
            """, (location_id, location_id))

        conn.commit()

    return saved


def main():
    parser = argparse.ArgumentParser(
        description="Rescrape reviews for locations with <= 5 reviews using multi-sort."
    )
    parser.add_argument(
        '--chain-name',
        type=str,
        default=None,
        help='Chain name to filter (e.g., "Starbucks"). If not specified with --all, must provide one.'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Rescrape all chains (no chain name filter)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=1000,
        help='Maximum number of locations to rescrape (default: 1000)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be rescrapped without making API calls'
    )
    args = parser.parse_args()

    if not args.chain_name and not args.all:
        parser.error("Either --chain-name or --all is required")

    if not GOOGLE_MAPS_API_KEY and not args.dry_run:
        log.error("GOOGLE_MAPS_API_KEY not set in environment")
        sys.exit(1)

    # Import after path setup
    from modules.db import get_connection, return_connection

    conn = get_connection()

    # Get locations to rescrape
    chain_filter = args.chain_name if not args.all else None
    locations = get_locations_to_rescrape(conn, chain_name=chain_filter, limit=args.limit)

    if not locations:
        log.info("No locations found with <= 5 reviews matching criteria",
                 chain_name=chain_filter or "ALL")
        return_connection(conn)
        return

    # Summary
    chains_summary = {}
    for loc in locations:
        cn = loc['chain_name'] or 'Unknown'
        if cn not in chains_summary:
            chains_summary[cn] = 0
        chains_summary[cn] += 1

    print("=" * 70)
    print("RESCRAPE REVIEWS - Multi-Sort Review Fetching")
    print("=" * 70)
    print(f"Chain filter:     {chain_filter or 'ALL CHAINS'}")
    print(f"Locations found:  {len(locations)}")
    print(f"Limit:            {args.limit}")
    print(f"Dry run:          {args.dry_run}")
    print(f"API calls needed: ~{len(locations) * 2} (2 per location for multi-sort)")
    print()
    print("Chains breakdown:")
    for cn, count in sorted(chains_summary.items(), key=lambda x: -x[1]):
        print(f"  {cn}: {count} locations")
    print("=" * 70)

    if args.dry_run:
        print()
        print("DRY RUN - No API calls will be made.")
        print()
        print("Sample locations that would be rescrapped:")
        for loc in locations[:20]:
            print(f"  [{loc['id']}] {loc['name']} ({loc['chain_name']}) "
                  f"- currently {loc['current_review_count']} reviews")
        if len(locations) > 20:
            print(f"  ... and {len(locations) - 20} more")
        return_connection(conn)
        return

    # Initialize scraper
    from modules.real_scraper import GoogleMapsRealScraper

    scraper = GoogleMapsRealScraper(
        api_key=GOOGLE_MAPS_API_KEY,
        redis_url="redis://localhost:6379/0",
        rate_limit=10,  # Conservative rate limit for rescraping
        max_workers=1
    )

    # Process locations
    start_time = time.time()
    total_new_reviews = 0
    locations_improved = 0
    locations_processed = 0
    errors = 0

    for loc in locations:
        locations_processed += 1
        place_id = loc['place_id']
        loc_id = loc['id']
        old_count = loc['current_review_count']

        try:
            # Fetch with multi-sort (gets up to 10 reviews)
            place_data = scraper.get_place_details(place_id, multi_sort_reviews=True)

            if place_data and place_data.reviews:
                new_saved = save_new_reviews(conn, loc_id, place_id, place_data.reviews)

                if new_saved > 0:
                    total_new_reviews += new_saved
                    locations_improved += 1
                    log.info(
                        "reviews_improved",
                        name=loc['name'],
                        chain=loc['chain_name'],
                        old_count=old_count,
                        new_reviews=new_saved,
                        total_fetched=len(place_data.reviews)
                    )
            else:
                log.debug("no_reviews_found", name=loc['name'], place_id=place_id)

        except Exception as e:
            errors += 1
            log.error("rescrape_error", name=loc['name'], place_id=place_id, error=str(e))

        # Progress report every 25 locations
        if locations_processed % 25 == 0:
            elapsed = time.time() - start_time
            rate = locations_processed / elapsed if elapsed > 0 else 0
            remaining = (len(locations) - locations_processed) / rate if rate > 0 else 0
            print(f"Progress: {locations_processed}/{len(locations)} | "
                  f"New reviews: {total_new_reviews} | "
                  f"Improved: {locations_improved} | "
                  f"Errors: {errors} | "
                  f"ETA: {remaining:.0f}s")

        # Rate limit between locations
        time.sleep(0.5)

    return_connection(conn)

    # Final report
    elapsed = time.time() - start_time

    print()
    print("=" * 70)
    print("RESCRAPE COMPLETE")
    print("=" * 70)
    print(f"Locations processed:   {locations_processed}")
    print(f"Locations improved:    {locations_improved}")
    print(f"New reviews saved:     {total_new_reviews}")
    print(f"Errors:                {errors}")
    print(f"Duration:              {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"Avg reviews per loc:   {total_new_reviews/locations_improved:.1f}" if locations_improved > 0 else "")
    print("=" * 70)

    log.info(
        "rescrape_complete",
        locations_processed=locations_processed,
        locations_improved=locations_improved,
        new_reviews=total_new_reviews,
        errors=errors,
        duration_seconds=round(elapsed, 1)
    )


if __name__ == "__main__":
    main()
