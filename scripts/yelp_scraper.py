#!/usr/bin/env python3
"""
YELP PRODUCTION SCRAPER - Main Yelp scraping script for ReviewSignal.

Connects to PostgreSQL, fetches chains and their locations, searches Yelp for
matching businesses, matches them to existing locations by name + proximity,
saves yelp_business_id, fetches reviews, and stores them with source='yelp'.

Uses modules/yelp_scraper.py (YelpScraper class) built by another agent.
Handles ImportError gracefully if the module is not yet available.

Usage:
  python3 scripts/yelp_scraper.py                              # All chains, default 500
  python3 scripts/yelp_scraper.py --chain-name "Starbucks"     # Specific chain
  python3 scripts/yelp_scraper.py --city "New York"            # Specific city
  python3 scripts/yelp_scraper.py --limit 200                  # Max locations
  python3 scripts/yelp_scraper.py --dry-run                    # Preview mode
  python3 scripts/yelp_scraper.py --match-only                 # Match locations only, no reviews
"""

import sys
import os
import time
import hashlib
import argparse
import math
from datetime import datetime
from typing import List, Dict, Optional, Tuple

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

# Lazy import of YelpScraper - may not exist yet
_yelp_scraper_cls = None


def _get_yelp_scraper_class():
    """Lazy-load YelpScraper class, handling ImportError gracefully."""
    global _yelp_scraper_cls
    if _yelp_scraper_cls is not None:
        return _yelp_scraper_cls
    try:
        from modules.yelp_scraper import YelpScraper
        _yelp_scraper_cls = YelpScraper
        return _yelp_scraper_cls
    except ImportError as e:
        log.error(
            "yelp_scraper_import_failed",
            error=str(e),
            hint="modules/yelp_scraper.py is not available yet. "
                 "Another agent is building it.",
        )
        return None


YELP_API_KEY = os.getenv("YELP_API_KEY", "")

# Yelp Fusion API daily limit
YELP_DAILY_LIMIT = 5000
# Estimated API calls per location: search + details + reviews
CALLS_PER_LOCATION = 3
# DB batch size for commits
DB_BATCH_SIZE = 50
# Progress log interval
PROGRESS_INTERVAL = 25
# Max distance in meters for proximity matching
MAX_MATCH_DISTANCE_M = 100


# ---------------------------------------------------------------------------
# Geo utilities
# ---------------------------------------------------------------------------

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance between two points in meters."""
    R = 6_371_000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def generate_review_hash(location_id: int, author_name: str, rating: int,
                         time_posted: str) -> str:
    """Generate a unique hash for Yelp review deduplication."""
    raw = "yelp:{}:{}:{}:{}".format(location_id, author_name, rating, time_posted)
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_chains(conn, chain_name: Optional[str] = None) -> List[dict]:
    """Get chains from the database."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if chain_name:
            cur.execute("SELECT id, name FROM chains WHERE name = %s", (chain_name,))
        else:
            cur.execute("SELECT id, name FROM chains ORDER BY total_locations DESC")
        return cur.fetchall()


def get_locations_for_chain(
    conn,
    chain_id: int,
    city: Optional[str] = None,
    limit: int = 500,
) -> List[dict]:
    """Get locations that need Yelp matching or review fetching."""
    conditions = ["l.chain_id = %s"]
    params: list = [chain_id]

    if city:
        conditions.append("l.city = %s")
        params.append(city)

    where = " AND ".join(conditions)
    params.append(limit)

    query = (
        "SELECT l.id, l.name, l.address, l.city, l.country, "
        "l.latitude, l.longitude, l.chain_name, "
        "l.extra_data "
        "FROM locations l "
        "WHERE {} "
        "ORDER BY l.id "
        "LIMIT %s".format(where)
    )
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        return cur.fetchall()


def get_yelp_review_count(conn, location_id: int) -> int:
    """Count existing Yelp reviews for a location."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM reviews WHERE location_id = %s AND source = 'yelp'",
            (location_id,),
        )
        return cur.fetchone()[0]


def get_yelp_business_id(conn, location_id: int) -> Optional[str]:
    """Get stored yelp_business_id from location extra_data."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT extra_data FROM locations WHERE id = %s",
            (location_id,),
        )
        row = cur.fetchone()
        if row and row["extra_data"] and isinstance(row["extra_data"], dict):
            return row["extra_data"].get("yelp_business_id")
    return None


def save_yelp_business_id(conn, location_id: int, yelp_id: str,
                          match_confidence: float) -> None:
    """Save yelp_business_id into location extra_data (JSONB merge)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE locations
            SET extra_data = COALESCE(extra_data, '{}'::jsonb)
                || jsonb_build_object(
                    'yelp_business_id', %s::text,
                    'yelp_match_confidence', %s::float,
                    'yelp_matched_at', %s::text
                ),
                updated_at = NOW()
            WHERE id = %s
            """,
            (yelp_id, match_confidence, datetime.utcnow().isoformat(), location_id),
        )
    conn.commit()


def save_yelp_reviews_batch(conn, location_id: int,
                            reviews: List[dict]) -> int:
    """Save Yelp reviews to the reviews table. Returns count of new reviews."""
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

            # Validate review
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
                log.warning("yelp_review_insert_error", location_id=location_id, error=str(e))
                continue

    if saved > 0:
        # Update review_count on the location
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
# Matching logic
# ---------------------------------------------------------------------------

def match_yelp_to_location(
    scraper,
    location: dict,
) -> Tuple[Optional[str], float]:
    """
    Try to match a local location to a Yelp business.

    1. Try exact match via Business Match API (name + address + city + country).
    2. Fallback: search by name + city, pick closest by lat/lng.

    Returns (yelp_business_id, confidence) or (None, 0.0).
    """
    name = location.get("name", "")
    address = location.get("address", "")
    city = location.get("city", "")
    country = location.get("country", "")
    lat = location.get("latitude")
    lng = location.get("longitude")

    # --- Attempt 1: Exact match API ---
    try:
        yelp_id = scraper.match_business(
            name=name,
            address=address,
            city=city,
            state="",
            country=country,
        )
        if yelp_id:
            return (yelp_id, 1.0)
    except Exception as e:
        log.debug("yelp_match_api_error", location_id=location["id"], error=str(e))

    # --- Attempt 2: Search + proximity ---
    if not city:
        return (None, 0.0)

    try:
        search_term = location.get("chain_name") or name
        search_location = "{}, {}".format(city, country) if country else city
        results = scraper.search_businesses(
            term=search_term,
            location=search_location,
            limit=10,
        )
        if not results:
            return (None, 0.0)

        best_id = None
        best_distance = float("inf")
        for biz in results:
            biz_lat = biz.get("latitude") or biz.get("coordinates", {}).get("latitude")
            biz_lng = biz.get("longitude") or biz.get("coordinates", {}).get("longitude")
            if biz_lat is None or biz_lng is None or lat is None or lng is None:
                continue
            dist = haversine_m(lat, lng, float(biz_lat), float(biz_lng))
            if dist < best_distance:
                best_distance = dist
                best_id = biz.get("id") or biz.get("business_id")

        if best_id and best_distance <= MAX_MATCH_DISTANCE_M:
            # Confidence inversely proportional to distance
            confidence = max(0.5, 1.0 - (best_distance / MAX_MATCH_DISTANCE_M) * 0.5)
            return (best_id, round(confidence, 2))

    except Exception as e:
        log.debug("yelp_search_fallback_error", location_id=location["id"], error=str(e))

    return (None, 0.0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Yelp Production Scraper - match locations and fetch reviews"
    )
    parser.add_argument("--chain-name", type=str, default=None,
                        help="Target a specific chain (e.g. 'Starbucks')")
    parser.add_argument("--city", type=str, default=None,
                        help="Filter locations by city")
    parser.add_argument("--limit", type=int, default=500,
                        help="Max locations to process (default: 500)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview mode - no API calls or DB writes")
    parser.add_argument("--match-only", action="store_true",
                        help="Only match locations to Yelp, skip review fetching")
    args = parser.parse_args()

    # --- Pre-flight checks ---
    if not args.dry_run:
        if not YELP_API_KEY:
            log.error("YELP_API_KEY not set in environment")
            sys.exit(1)

        YelpScraperCls = _get_yelp_scraper_class()
        if YelpScraperCls is None:
            log.error("Cannot proceed without modules.yelp_scraper.YelpScraper")
            sys.exit(1)
        scraper = YelpScraperCls(api_key=YELP_API_KEY)
    else:
        scraper = None

    conn = get_connection()

    # --- Gather chains ---
    chains = get_chains(conn, chain_name=args.chain_name)
    if not chains:
        log.error("No chains found", chain_name=args.chain_name)
        return_connection(conn)
        sys.exit(1)

    log.info("=" * 70)
    log.info(
        "YELP PRODUCTION SCRAPER START",
        chains=len(chains),
        city=args.city or "ALL",
        limit=args.limit,
        dry_run=args.dry_run,
        match_only=args.match_only,
    )

    # --- Rate limit tracking ---
    api_calls_used = 0
    max_api_calls = YELP_DAILY_LIMIT  # conservative daily budget

    # Counters
    total_locations_processed = 0
    total_matched = 0
    total_already_matched = 0
    total_reviews_saved = 0
    total_errors = 0
    start_time = time.time()

    for chain in chains:
        chain_id = chain["id"]
        chain_name = chain["name"]

        remaining_limit = args.limit - total_locations_processed
        if remaining_limit <= 0:
            break

        locations = get_locations_for_chain(
            conn,
            chain_id=chain_id,
            city=args.city,
            limit=remaining_limit,
        )
        if not locations:
            continue

        log.info("Processing chain", chain=chain_name, locations=len(locations))

        for i, loc in enumerate(locations):
            if api_calls_used >= max_api_calls:
                log.warning(
                    "yelp_daily_limit_approaching",
                    api_calls_used=api_calls_used,
                    limit=max_api_calls,
                )
                break

            total_locations_processed += 1
            loc_id = loc["id"]

            # --- Step 1: Check / perform Yelp matching ---
            yelp_id = get_yelp_business_id(conn, loc_id)

            if yelp_id:
                total_already_matched += 1
            elif not args.dry_run:
                yelp_id, confidence = match_yelp_to_location(scraper, loc)
                api_calls_used += 2  # match + search fallback
                if yelp_id:
                    save_yelp_business_id(conn, loc_id, yelp_id, confidence)
                    total_matched += 1
                    log.debug(
                        "yelp_matched",
                        location_id=loc_id,
                        name=loc["name"],
                        yelp_id=yelp_id,
                        confidence=confidence,
                    )
                else:
                    log.debug(
                        "yelp_no_match",
                        location_id=loc_id,
                        name=loc["name"],
                        city=loc.get("city"),
                    )
            else:
                # dry-run: just count
                pass

            # --- Step 2: Fetch reviews if matched ---
            if yelp_id and not args.match_only and not args.dry_run:
                existing_yelp_reviews = get_yelp_review_count(conn, loc_id)
                if existing_yelp_reviews < 3:
                    try:
                        raw_reviews = scraper.get_business_reviews(yelp_id)
                        api_calls_used += 1
                        if raw_reviews:
                            saved = save_yelp_reviews_batch(conn, loc_id, raw_reviews)
                            total_reviews_saved += saved
                    except Exception as e:
                        total_errors += 1
                        log.warning(
                            "yelp_review_fetch_error",
                            location_id=loc_id,
                            yelp_id=yelp_id,
                            error=str(e),
                        )

            # --- Progress logging ---
            if total_locations_processed % PROGRESS_INTERVAL == 0:
                elapsed = time.time() - start_time
                rate = total_locations_processed / elapsed if elapsed > 0 else 0
                log.info(
                    "Progress: {}/{} locations | {} matched | {} reviews | "
                    "{} API calls | {:.1f} loc/s | {:.0f}s".format(
                        total_locations_processed,
                        args.limit,
                        total_matched,
                        total_reviews_saved,
                        api_calls_used,
                        rate,
                        elapsed,
                    )
                )

            # Rate limiting: ~1 req/s to be safe with Yelp
            if not args.dry_run:
                time.sleep(0.3)

    elapsed = time.time() - start_time

    # --- Summary ---
    log.info("=" * 70)
    log.info("YELP PRODUCTION SCRAPER DONE")
    log.info("Locations processed: {}".format(total_locations_processed))
    log.info("Already matched:     {}".format(total_already_matched))
    log.info("Newly matched:       {}".format(total_matched))
    log.info("Reviews saved:       {}".format(total_reviews_saved))
    log.info("API calls used:      {}/{}".format(api_calls_used, max_api_calls))
    log.info("Errors:              {}".format(total_errors))
    log.info("Duration:            {:.0f}s ({:.1f}min)".format(elapsed, elapsed / 60))
    if elapsed > 0:
        log.info("Rate:                {:.1f} locations/sec".format(
            total_locations_processed / elapsed))
    log.info("=" * 70)

    return_connection(conn)


if __name__ == "__main__":
    main()
