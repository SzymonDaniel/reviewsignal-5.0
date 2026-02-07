#!/usr/bin/env python3
"""
MASS REVIEW SCRAPER - Masowe pobieranie recenzji dla istniejących lokalizacji
System 5.0 - Cel: 80%+ pokrycie recenzji dla 27,000+ lokalizacji

Strategia:
1. Pobierz wszystkie lokalizacje bez recenzji (review_count = 0)
2. Dla każdej lokalizacji pobierz recenzje z Google Maps API
3. Zapisz recenzje do bazy (tabela reviews)
4. Aktualizuj review_count w tabeli locations
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from modules.real_scraper import GoogleMapsRealScraper
from modules.db import get_connection, return_connection
from psycopg2.extras import RealDictCursor
import structlog
from typing import List, Dict
import time
from datetime import datetime

logger = structlog.get_logger()

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

BATCH_SIZE = 100  # Process 100 locations at a time
TARGET_COVERAGE = 0.80  # 80% locations with reviews

# ═══════════════════════════════════════════════════════════════
# DATABASE FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def get_db_connection():
    """Get PostgreSQL connection from shared pool."""
    return get_connection()

def get_locations_without_reviews(conn, limit: int = 1000):
    """Get locations that need review scraping - only valid Google Maps place_ids"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, place_id, name, chain_name, city, country, review_count
            FROM locations
            WHERE (review_count = 0 OR review_count IS NULL)
            AND place_id LIKE 'ChIJ%%'  -- Only Google Maps place IDs (not OSM node/way/relation)
            AND source = 'google_maps'
            ORDER BY
                CASE
                    WHEN chain_id IS NOT NULL THEN 0
                    ELSE 1
                END,
                created_at DESC
            LIMIT %s
            """,
            (limit,)
        )
        return cur.fetchall()

def save_reviews_to_db(conn, location_id: int, reviews: List[Dict]):
    """Save reviews to database"""
    if not reviews:
        return 0

    saved_count = 0
    with conn.cursor() as cur:
        for review in reviews:
            try:
                cur.execute(
                    """
                    INSERT INTO reviews (
                        location_id,
                        author_name,
                        rating,
                        text,
                        time_posted,
                        language,
                        source
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        location_id,
                        review.get('author_name', 'Anonymous'),
                        review.get('rating', 0),
                        review.get('text', ''),
                        datetime.fromtimestamp(review.get('time', 0)),
                        review.get('language', 'en'),
                        'google_maps'
                    )
                )
                if cur.rowcount > 0:
                    saved_count += 1
            except Exception as e:
                logger.error("review_save_error", error=str(e), review=review)
                continue

        # Update review_count in locations
        cur.execute(
            """
            UPDATE locations
            SET review_count = (
                SELECT COUNT(*) FROM reviews WHERE location_id = %s
            ),
            updated_at = NOW()
            WHERE id = %s
            """,
            (location_id, location_id)
        )

        conn.commit()

    return saved_count

# ═══════════════════════════════════════════════════════════════
# SCRAPING FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def scrape_reviews_for_location(scraper: GoogleMapsRealScraper, place_id: str) -> List[Dict]:
    """Scrape reviews for a single location"""
    try:
        place_data = scraper.get_place_details(place_id)
        if place_data and place_data.reviews:
            return [review for review in place_data.reviews]
        return []
    except Exception as e:
        logger.error("review_scrape_error", place_id=place_id, error=str(e))
        return []

def process_batch(scraper: GoogleMapsRealScraper, conn, locations: List[Dict]):
    """Process a batch of locations"""
    total_reviews = 0
    locations_processed = 0

    for location in locations:
        try:
            reviews = scrape_reviews_for_location(scraper, location['place_id'])

            if reviews:
                saved_count = save_reviews_to_db(conn, location['id'], reviews)
                total_reviews += saved_count

                logger.info(
                    "reviews_scraped",
                    location_id=location['id'],
                    name=location['name'],
                    chain=location['chain_name'],
                    reviews_count=saved_count
                )

            locations_processed += 1

            # Progress report every 10 locations
            if locations_processed % 10 == 0:
                logger.info(
                    "batch_progress",
                    processed=locations_processed,
                    total_reviews=total_reviews
                )

            # Rate limiting - small delay
            time.sleep(0.1)

        except Exception as e:
            logger.error(
                "location_processing_error",
                location_id=location['id'],
                error=str(e)
            )
            continue

    return locations_processed, total_reviews

# ═══════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════

def main():
    """Main scraping orchestrator"""
    start_time = datetime.now()

    logger.info(
        "mass_review_scraping_started",
        target_coverage=f"{TARGET_COVERAGE*100}%",
        timestamp=start_time.isoformat()
    )

    # Initialize scraper
    scraper = GoogleMapsRealScraper(
        api_key=GOOGLE_MAPS_API_KEY,
        redis_url="redis://localhost:6379/0",
        rate_limit=50,
        max_workers=5
    )

    conn = get_db_connection()

    # Get total locations
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM locations")
        total_locations = cur.fetchone()['total']

        cur.execute("SELECT COUNT(*) as with_reviews FROM locations WHERE review_count > 0")
        locations_with_reviews = cur.fetchone()['with_reviews']

    target_count = int(total_locations * TARGET_COVERAGE)
    needed_count = target_count - locations_with_reviews

    logger.info(
        "scraping_plan",
        total_locations=total_locations,
        current_with_reviews=locations_with_reviews,
        target_count=target_count,
        needed=needed_count
    )

    print("\n" + "="*70)
    print("MASS REVIEW SCRAPING")
    print("="*70)
    print(f"Total Locations:           {total_locations:,}")
    print(f"Currently with reviews:    {locations_with_reviews:,} ({locations_with_reviews/total_locations*100:.1f}%)")
    print(f"Target coverage:           {TARGET_COVERAGE*100:.0f}% ({target_count:,} locations)")
    print(f"Need to scrape:            {needed_count:,} locations")
    print("="*70 + "\n")

    total_processed = 0
    total_reviews_scraped = 0

    # Process in batches
    while total_processed < needed_count:
        # Get next batch
        locations = get_locations_without_reviews(conn, BATCH_SIZE)

        if not locations:
            logger.info("no_more_locations", message="All locations processed or no more without reviews")
            break

        logger.info(
            "batch_started",
            batch_size=len(locations),
            total_processed=total_processed
        )

        # Process batch
        processed, reviews = process_batch(scraper, conn, locations)
        total_processed += processed
        total_reviews_scraped += reviews

        # Progress report
        current_coverage = (locations_with_reviews + total_processed) / total_locations * 100

        logger.info(
            "progress_update",
            total_processed=total_processed,
            total_reviews=total_reviews_scraped,
            current_coverage=f"{current_coverage:.1f}%",
            needed_remaining=needed_count - total_processed
        )

        print(f"Progress: {total_processed:,}/{needed_count:,} | Reviews: {total_reviews_scraped:,} | Coverage: {current_coverage:.1f}%")

    return_connection(conn)

    # FINAL REPORT
    duration = datetime.now() - start_time

    # Get final stats
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as with_reviews FROM locations WHERE review_count > 0")
        final_with_reviews = cur.fetchone()['with_reviews']

        cur.execute("SELECT SUM(review_count) as total_reviews FROM locations")
        total_reviews_db = cur.fetchone()['total_reviews'] or 0
    return_connection(conn)

    final_coverage = final_with_reviews / total_locations * 100

    print("\n" + "="*70)
    print("MASS REVIEW SCRAPING COMPLETED!")
    print("="*70)
    print(f"Locations Processed:       {total_processed:,}")
    print(f"Reviews Scraped:           {total_reviews_scraped:,}")
    print(f"Final Coverage:            {final_coverage:.1f}% ({final_with_reviews:,}/{total_locations:,})")
    print(f"Total Reviews in DB:       {total_reviews_db:,}")
    print(f"Duration:                  {duration.total_seconds() / 60:.1f} minutes")
    print("="*70)

    logger.info(
        "mass_review_scraping_completed",
        locations_processed=total_processed,
        reviews_scraped=total_reviews_scraped,
        final_coverage=f"{final_coverage:.1f}%",
        duration_minutes=duration.total_seconds() / 60,
        timestamp=datetime.now().isoformat()
    )

if __name__ == "__main__":
    main()
