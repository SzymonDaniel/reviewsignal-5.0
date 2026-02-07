#!/usr/bin/env python3
"""
ACCELERATED COVERAGE SCRAPER - Fast review backfill for high-value chains.

Focuses on chains that hedge funds care about (Walmart, Starbucks, etc.)
Uses ThreadPoolExecutor for parallel API calls to accelerate coverage.

Usage:
  python3 scripts/accelerated_coverage.py                           # Default: top chains, 500 batch
  python3 scripts/accelerated_coverage.py --chain-name Walmart      # Specific chain
  python3 scripts/accelerated_coverage.py --country US              # US locations only
  python3 scripts/accelerated_coverage.py --batch-size 1000         # Custom batch
  python3 scripts/accelerated_coverage.py --limit 500               # Max locations total
  python3 scripts/accelerated_coverage.py --threads 3               # Parallel threads (default 5)
  python3 scripts/accelerated_coverage.py --dry-run                 # Preview without scraping
"""

import sys
import os
import time
import hashlib
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

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

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

HIGH_VALUE_CHAINS = [
    "Walmart", "Starbucks", "McDonald's", "Subway", "Taco Bell",
    "Chipotle", "Domino's", "KFC", "Pizza Hut", "Burger King",
    "Wendy's", "Dunkin'", "Kroger", "Whole Foods Market",
    "Trader Joe's", "Safeway", "Publix", "H-E-B", "Walgreens",
    "CVS Pharmacy", "Rite Aid", "Olive Garden", "IHOP", "Denny's",
    "Panera Bread", "Texas Roadhouse", "Red Lobster",
    "Outback Steakhouse", "TGI Friday's", "Cracker Barrel",
    "The Cheesecake Factory", "IKEA", "Best Western", "Holiday Inn",
    "Tesco", "Lidl", "Edeka", "Netto", "Penny", "Spar",
]


def generate_review_hash(location_id, author_name, rating, time_posted):
    raw = "{}:{}:{}:{}".format(location_id, author_name, rating, time_posted)
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


def get_coverage_stats(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM locations")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT location_id) FROM reviews WHERE location_id IS NOT NULL")
        with_reviews = cur.fetchone()[0]
        return total, with_reviews


def get_uncovered_locations(conn, chain_name=None, country=None, batch_size=500, limit=None):
    effective_limit = min(batch_size, limit) if limit else batch_size
    conditions = ["r.id IS NULL", "l.place_id IS NOT NULL", "l.place_id LIKE 'ChIJ%%'"]
    params = []
    if chain_name:
        conditions.append("c.name = %s")
        params.append(chain_name)
    else:
        placeholders = ",".join(["%s"] * len(HIGH_VALUE_CHAINS))
        conditions.append("c.name IN ({})".format(placeholders))
        params.extend(HIGH_VALUE_CHAINS)
    if country:
        conditions.append("l.country = %s")
        params.append(country)
    where_clause = " AND ".join(conditions)
    params.append(effective_limit)
    query = (
        "SELECT l.id, l.place_id, l.name, l.chain_name, c.name as chain "
        "FROM locations l "
        "JOIN chains c ON l.chain_id = c.id "
        "LEFT JOIN reviews r ON r.location_id = l.id "
        "WHERE " + where_clause + " "
        "ORDER BY "
        "CASE "
        "WHEN c.name IN ('Walmart','Starbucks','McDonald''s','Kroger','Chipotle','Domino''s') THEN 0 "
        "WHEN c.name IN ('Walgreens','CVS Pharmacy','Whole Foods Market','Trader Joe''s') THEN 1 "
        "WHEN c.name IN ('Olive Garden','IHOP','Panera Bread','Denny''s') THEN 2 "
        "ELSE 3 END, l.id "
        "LIMIT %s"
    )
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        return cur.fetchall()


def scrape_single_location(scraper, location):
    place_id = location["place_id"]
    loc_id = location["id"]
    try:
        details = scraper.get_place_details(place_id)
        if not details or not details.reviews:
            return (loc_id, [], None)
        reviews = []
        for review in details.reviews:
            review_time = review.get("time", 0)
            author = review.get("author_name", "Anonymous")
            rating = review.get("rating", 0)
            text = review.get("text", "")
            language = review.get("language", "en")

            # --- REVIEW VALIDATION GATE ---
            rev_dict = {"text": text, "rating": rating, "author_name": author}
            rev_valid, _issues = ReviewValidator.validate(rev_dict)
            if not rev_valid:
                continue

            review_hash = generate_review_hash(loc_id, author, rating, review_time)
            reviews.append({
                "location_id": loc_id,
                "place_id": place_id,
                "author_name": author,
                "rating": rating,
                "text": text,
                "time_posted": review_time,
                "language": language,
                "source": "google_maps",
                "review_hash": review_hash,
                "sentiment_score": rev_dict.get("sentiment_score"),
            })
        return (loc_id, reviews, None)
    except Exception as e:
        return (loc_id, [], str(e))


def save_reviews_batch(conn, all_reviews):
    total_saved = 0
    locations_updated = 0
    with conn.cursor() as cur:
        for loc_id, reviews in all_reviews.items():
            saved = 0
            for review in reviews:
                try:
                    cur.execute(
                        "INSERT INTO reviews (location_id, place_id, author_name, rating, text, "
                        "time_posted, language, source, review_hash, sentiment_score) "
                        "VALUES (%s, %s, %s, %s, %s, to_timestamp(%s), %s, %s, %s, %s) "
                        "ON CONFLICT (review_hash) DO NOTHING",
                        (review["location_id"], review["place_id"], review["author_name"],
                         review["rating"], review["text"], review["time_posted"],
                         review["language"], review["source"], review["review_hash"],
                         review.get("sentiment_score")))
                    if cur.rowcount > 0:
                        saved += 1
                except Exception:
                    continue
            if saved > 0:
                cur.execute(
                    "UPDATE locations SET review_count = "
                    "(SELECT COUNT(*) FROM reviews WHERE location_id = %s) "
                    "WHERE id = %s", (loc_id, loc_id))
                locations_updated += 1
            total_saved += saved
    conn.commit()
    return total_saved, locations_updated


def main():
    parser = argparse.ArgumentParser(description="Accelerated review coverage scraper")
    parser.add_argument("--chain-name", type=str, default=None, help="Target specific chain")
    parser.add_argument("--country", type=str, default=None, help="Filter by country")
    parser.add_argument("--batch-size", type=int, default=500, help="Locations per batch (default: 500)")
    parser.add_argument("--limit", type=int, default=None, help="Max total locations to process")
    parser.add_argument("--threads", type=int, default=5, help="Parallel scraping threads (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Preview locations without scraping")
    args = parser.parse_args()

    if not GOOGLE_MAPS_API_KEY and not args.dry_run:
        log.error("GOOGLE_MAPS_API_KEY not set in environment")
        sys.exit(1)

    conn = get_connection()
    total, with_reviews = get_coverage_stats(conn)
    coverage_before = round(with_reviews / total * 100, 1) if total > 0 else 0

    log.info("=" * 70)
    log.info("ACCELERATED COVERAGE SCRAPER START",
             coverage="{}/{} ({}%)".format(with_reviews, total, coverage_before),
             chain_filter=args.chain_name or "HIGH_VALUE_CHAINS",
             country_filter=args.country or "ALL",
             batch_size=args.batch_size, limit=args.limit, threads=args.threads)

    locations = get_uncovered_locations(
        conn, chain_name=args.chain_name, country=args.country,
        batch_size=args.batch_size, limit=args.limit)
    log.info("Found {} uncovered locations to process".format(len(locations)))

    if not locations:
        log.info("No uncovered locations found matching criteria.")
        return_connection(conn)
        return

    chain_counts = {}
    for loc in locations:
        chain = loc.get("chain", loc.get("chain_name", "Unknown"))
        chain_counts[chain] = chain_counts.get(chain, 0) + 1
    log.info("Chain breakdown:")
    for chain, count in sorted(chain_counts.items(), key=lambda x: -x[1]):
        log.info("  {}: {} locations".format(chain, count))

    if args.dry_run:
        log.info("DRY RUN - no scraping performed")
        return_connection(conn)
        return

    from modules.real_scraper import GoogleMapsRealScraper
    scraper = GoogleMapsRealScraper(
        api_key=GOOGLE_MAPS_API_KEY, rate_limit=10, max_workers=args.threads)

    total_reviews_saved = 0
    total_locations_updated = 0
    total_errors = 0
    start_time = time.time()

    sub_batch_size = 50
    for batch_start in range(0, len(locations), sub_batch_size):
        batch = locations[batch_start:batch_start + sub_batch_size]
        all_reviews = {}
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            futures = {executor.submit(scrape_single_location, scraper, loc): loc for loc in batch}
            for future in as_completed(futures):
                loc = futures[future]
                try:
                    loc_id, reviews, error = future.result()
                    if error:
                        total_errors += 1
                        log.warning("Error scraping location {}: {}".format(loc_id, error))
                    elif reviews:
                        all_reviews[loc_id] = reviews
                except Exception as e:
                    total_errors += 1
                    log.error("Thread error for location {}: {}".format(loc.get("id"), e))
        if all_reviews:
            saved, updated = save_reviews_batch(conn, all_reviews)
            total_reviews_saved += saved
            total_locations_updated += updated
        elapsed = time.time() - start_time
        processed = batch_start + len(batch)
        rate = processed / elapsed if elapsed > 0 else 0
        log.info("Progress: {}/{} locations ({} reviews, {} with data, {} errors, {:.1f} loc/s, {:.0f}s)".format(
            processed, len(locations), total_reviews_saved, total_locations_updated, total_errors, rate, elapsed))

    elapsed = time.time() - start_time
    total_after, with_reviews_after = get_coverage_stats(conn)
    coverage_after = round(with_reviews_after / total_after * 100, 1) if total_after > 0 else 0

    log.info("=" * 70)
    log.info("ACCELERATED COVERAGE SCRAPER DONE")
    log.info("Processed: {} locations in {:.0f}s ({:.1f}min)".format(len(locations), elapsed, elapsed / 60))
    log.info("Reviews saved: {}".format(total_reviews_saved))
    log.info("Locations with new reviews: {}".format(total_locations_updated))
    log.info("Errors: {}".format(total_errors))
    log.info("Coverage: {}% -> {}% ({}/{})".format(coverage_before, coverage_after, with_reviews_after, total_after))
    if elapsed > 0:
        log.info("Rate: {:.1f} locations/sec".format(len(locations) / elapsed))
    log.info("=" * 70)

    return_connection(conn)


if __name__ == "__main__":
    main()
