#!/usr/bin/env python3
"""
YELP MATCH LOCATIONS - Match existing Google Maps locations with Yelp businesses.

Dedicated script for matching our locations table rows to Yelp businesses.
Uses Yelp Business Match API (exact) and falls back to Business Search + proximity.

Each match stores yelp_business_id in locations.extra_data (JSONB) along with
match_confidence (1.0 = exact, 0.5-0.9 = proximity).

Usage:
  python3 scripts/yelp_match_locations.py                          # Default: all unmatched
  python3 scripts/yelp_match_locations.py --chain-name "Starbucks" # Specific chain
  python3 scripts/yelp_match_locations.py --limit 200              # Max locations
  python3 scripts/yelp_match_locations.py --dry-run                # Preview only
"""

import sys
import os
import time
import math
import argparse
from datetime import datetime
from typing import Optional, Tuple, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from psycopg2.extras import RealDictCursor
from modules.db import get_connection, return_connection
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
log = structlog.get_logger()

YELP_API_KEY = os.getenv("YELP_API_KEY", "")

# Max distance in meters for proximity matching
MAX_MATCH_DISTANCE_M = 100

# Yelp daily API call budget for this script (conservative)
MAX_API_CALLS = 3000

# Progress log interval
PROGRESS_INTERVAL = 25


# ---------------------------------------------------------------------------
# Geo utilities
# ---------------------------------------------------------------------------

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance between two points in meters."""
    R = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_unmatched_locations(
    conn,
    chain_name: Optional[str] = None,
    limit: int = 500,
) -> List[dict]:
    """
    Get locations that have name + city but no yelp_business_id in extra_data.
    """
    conditions = [
        "l.name IS NOT NULL",
        "length(l.name) > 0",
        "l.city IS NOT NULL",
        "length(l.city) > 0",
        "l.yelp_business_id IS NULL",
    ]
    params: list = []

    if chain_name:
        conditions.append("c.name = %s")
        params.append(chain_name)

    where = " AND ".join(conditions)
    params.append(limit)

    query = (
        "SELECT l.id, l.name, l.address, l.city, l.country, "
        "l.latitude, l.longitude, l.chain_name, l.yelp_business_id, c.name AS chain "
        "FROM locations l "
        "LEFT JOIN chains c ON l.chain_id = c.id "
        "WHERE {} "
        "ORDER BY "
        "  CASE WHEN l.chain_id IS NOT NULL THEN 0 ELSE 1 END, "
        "  l.id "
        "LIMIT %s"
    ).format(where)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        return cur.fetchall()


def save_match(conn, location_id: int, yelp_id: str,
               confidence: float) -> None:
    """Store yelp_business_id in the dedicated column."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE locations
            SET yelp_business_id = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (yelp_id, location_id),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------

def try_match(
    scraper,
    location: dict,
) -> Tuple[Optional[str], float]:
    """
    Attempt to match a location to a Yelp business.

    Strategy:
      1. Yelp Business Match API (exact: name + address + city + country)
      2. Fallback: Yelp Business Search (term + location) + closest by lat/lng

    Returns (yelp_business_id, confidence) or (None, 0.0).
    """
    name = location.get("name", "")
    address = location.get("address", "")
    city = location.get("city", "")
    country = location.get("country", "")
    lat = float(location.get("latitude")) if location.get("latitude") is not None else None
    lng = float(location.get("longitude")) if location.get("longitude") is not None else None

    api_calls = 0

    # --- Attempt 1: Exact match ---
    # Parse address1 from full address (e.g. "1912 Pike Pl, Seattle, WA 98101, USA" → "1912 Pike Pl")
    address1 = address.split(",")[0].strip() if address else ""
    # Try to extract state from address for US locations
    state = ""
    if country in ("US", "United States") and address:
        parts = [p.strip() for p in address.split(",")]
        for part in parts:
            tokens = part.split()
            if len(tokens) >= 2 and len(tokens[-2]) == 2 and tokens[-2].isupper():
                state = tokens[-2]
                break
    try:
        yelp_id = scraper.match_business(
            name=name,
            address=address1,
            city=city,
            state=state,
            country=country,
        )
        api_calls += 1
        if yelp_id:
            return (yelp_id, 1.0)
    except Exception as e:
        api_calls += 1
        log.debug("match_api_error", location_id=location["id"], error=str(e))

    # --- Attempt 2: Search + proximity ---
    if not city:
        return (None, 0.0)

    try:
        search_term = location.get("chain_name") or location.get("chain") or name
        search_location = "{}, {}".format(city, country) if country else city
        results = scraper.search_businesses(
            term=search_term,
            location=search_location,
            limit=10,
        )
        api_calls += 1

        if not results:
            return (None, 0.0)

        best_id = None
        best_distance = float("inf")
        for biz in results:
            biz_lat = getattr(biz, "latitude", None)
            biz_lng = getattr(biz, "longitude", None)
            if biz_lat is None or biz_lng is None or lat is None or lng is None:
                continue
            dist = haversine_m(lat, lng, float(biz_lat), float(biz_lng))
            if dist < best_distance:
                best_distance = dist
                best_id = getattr(biz, "id", None)

        if best_id and best_distance <= MAX_MATCH_DISTANCE_M:
            confidence = max(0.5, 1.0 - (best_distance / MAX_MATCH_DISTANCE_M) * 0.5)
            return (best_id, round(confidence, 2))

    except Exception as e:
        log.debug("search_fallback_error", location_id=location["id"], error=str(e))

    return (None, 0.0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Match existing locations with Yelp businesses"
    )
    parser.add_argument("--chain-name", type=str, default=None,
                        help="Target a specific chain")
    parser.add_argument("--limit", type=int, default=500,
                        help="Max locations to process (default: 500)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview locations without making API calls")
    args = parser.parse_args()

    # --- Pre-flight ---
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
    else:
        scraper = None

    conn = get_connection()

    # --- Get unmatched locations ---
    locations = get_unmatched_locations(conn, chain_name=args.chain_name, limit=args.limit)

    log.info("=" * 70)
    log.info(
        "YELP LOCATION MATCHER START",
        unmatched_found=len(locations),
        chain_filter=args.chain_name or "ALL",
        limit=args.limit,
        dry_run=args.dry_run,
    )

    if not locations:
        log.info("No unmatched locations found. Nothing to do.")
        return_connection(conn)
        return

    # --- Dry run: show chain breakdown ---
    chain_counts: dict = {}
    for loc in locations:
        c = loc.get("chain") or loc.get("chain_name") or "Unknown"
        chain_counts[c] = chain_counts.get(c, 0) + 1
    log.info("Chain breakdown:")
    for c, cnt in sorted(chain_counts.items(), key=lambda x: -x[1]):
        log.info("  {}: {} locations".format(c, cnt))

    if args.dry_run:
        log.info("DRY RUN - no API calls made.")
        return_connection(conn)
        return

    # --- Process ---
    matched = 0
    unmatched = 0
    errors = 0
    api_calls = 0
    start_time = time.time()

    for i, loc in enumerate(locations):
        if api_calls >= MAX_API_CALLS:
            log.warning("API call budget exhausted", api_calls=api_calls)
            break

        try:
            yelp_id, confidence = try_match(scraper, loc)
            api_calls += 2  # worst case: match + search

            if yelp_id:
                save_match(conn, loc["id"], yelp_id, confidence)
                matched += 1
                log.debug(
                    "matched",
                    location_id=loc["id"],
                    name=loc["name"],
                    yelp_id=yelp_id,
                    confidence=confidence,
                )
            else:
                unmatched += 1
        except Exception as e:
            errors += 1
            log.warning("match_error", location_id=loc["id"], error=str(e))

        # Progress
        processed = i + 1
        if processed % PROGRESS_INTERVAL == 0:
            elapsed = time.time() - start_time
            log.info(
                "Progress: {}/{} | matched={} unmatched={} errors={} | "
                "~{} API calls | {:.0f}s".format(
                    processed, len(locations), matched, unmatched,
                    errors, api_calls, elapsed,
                )
            )

        # Rate limit
        time.sleep(0.3)

    elapsed = time.time() - start_time
    total_processed = matched + unmatched + errors

    # --- Summary ---
    log.info("=" * 70)
    log.info("YELP LOCATION MATCHER DONE")
    log.info("Total processed:  {}".format(total_processed))
    log.info("Matched:          {} ({:.1f}%)".format(
        matched, matched / total_processed * 100 if total_processed else 0))
    log.info("Unmatched:        {}".format(unmatched))
    log.info("Errors:           {}".format(errors))
    log.info("API calls:        ~{}".format(api_calls))
    log.info("Duration:         {:.0f}s ({:.1f}min)".format(elapsed, elapsed / 60))
    log.info("=" * 70)

    return_connection(conn)


if __name__ == "__main__":
    main()
