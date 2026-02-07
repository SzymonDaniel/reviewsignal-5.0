#!/usr/bin/env python3
"""
Apify Google Maps Reviews Scraper Integration
==============================================

Fetches Google Maps reviews at scale via Apify's Google Maps Reviews Scraper actor.
Stores results in PostgreSQL with deduplication, cost estimation, and rate limiting.

Actor: compass/google-maps-reviews-scraper
Docs:  https://apify.com/compass/google-maps-reviews-scraper

Usage:
  # Single location
  python3 scripts/apify_google_reviews.py --place-id ChIJN1t_tDeuEmsRUsoyG83frY4

  # All locations for a chain
  python3 scripts/apify_google_reviews.py --chain-name "Starbucks" --limit 50

  # Backfill locations with few reviews
  python3 scripts/apify_google_reviews.py --backfill --min-reviews 10 --limit 100

  # Dry run (cost estimate only)
  python3 scripts/apify_google_reviews.py --chain-name "McDonald's" --dry-run

Author: ReviewSignal Team
Version: 1.0.0
Date: February 2026
"""

import sys
import os
import time
import hashlib
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# Path & env setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

import structlog
from psycopg2.extras import RealDictCursor

from modules.db import get_connection, return_connection

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
APIFY_API_KEY = os.getenv("APIFY_API_KEY", "")
APIFY_BASE_URL = "https://api.apify.com/v2"
ACTOR_ID = "compass~google-maps-reviews-scraper"

# Cost model (approximate, based on Apify pricing as of Jan 2026)
# compass/google-maps-reviews-scraper: ~$0.50 per 1,000 reviews
COST_PER_1000_REVIEWS = 0.50

# Rate limiting
MIN_DELAY_BETWEEN_RUNS = 2.0        # seconds between actor run submissions
POLL_INTERVAL = 10                   # seconds between status polls
MAX_POLL_TIME = 600                  # 10 min max wait per run

# Retry config
MAX_API_RETRIES = 3
RETRY_BACKOFF = 2.0


# ---------------------------------------------------------------------------
# HTTP session with retry
# ---------------------------------------------------------------------------
def _build_session() -> requests.Session:
    """Build a requests session with retry logic."""
    session = requests.Session()
    retries = Retry(
        total=MAX_API_RETRIES,
        backoff_factor=RETRY_BACKOFF,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_session: Optional[requests.Session] = None


def get_session() -> requests.Session:
    """Return a reusable requests session with retries configured."""
    global _session
    if _session is None:
        _session = _build_session()
    return _session


# ---------------------------------------------------------------------------
# Apify API helpers
# ---------------------------------------------------------------------------
def _apify_headers() -> Dict[str, str]:
    """Return headers for Apify REST API."""
    return {"Content-Type": "application/json"}


def _apify_params(**extra) -> Dict[str, str]:
    """Return query params with token for Apify REST API."""
    params = {"token": APIFY_API_KEY}
    params.update(extra)
    return params


def _start_actor_run_sync(
    input_data: dict, timeout_secs: int = 300, memory_mbytes: int = 512
) -> dict:
    """
    Start an Apify actor run using the synchronous endpoint.
    Blocks until the actor finishes and returns dataset items directly.
    Falls back to async polling if the sync call times out.
    """
    url = f"{APIFY_BASE_URL}/acts/{ACTOR_ID}/run-sync-get-dataset-items"
    query_params = _apify_params(timeout=str(timeout_secs), memory=str(memory_mbytes))
    session = get_session()

    try:
        resp = session.post(
            url,
            headers=_apify_headers(),
            params=query_params,
            json=input_data,
            timeout=timeout_secs + 30,
        )
    except requests.exceptions.Timeout:
        log.warning("apify_sync_timeout", timeout=timeout_secs)
        return _start_actor_run_async(input_data, timeout_secs, memory_mbytes)

    if resp.status_code == 200:
        items = resp.json()
        if isinstance(items, list):
            return {"status": "SUCCEEDED", "items": items}
        return {"status": "SUCCEEDED", "items": []}

    # 408 = timeout on Apify side, 413 = payload too large -> async fallback
    if resp.status_code in (408, 413):
        log.warning("apify_sync_fallback", status=resp.status_code)
        return _start_actor_run_async(input_data, timeout_secs, memory_mbytes)

    resp.raise_for_status()
    return {"status": "FAILED", "items": []}


def _start_actor_run_async(
    input_data: dict, timeout_secs: int = 300, memory_mbytes: int = 512
) -> dict:
    """Start an actor run asynchronously and poll until completion."""
    url = f"{APIFY_BASE_URL}/acts/{ACTOR_ID}/runs"
    params = {"timeout": timeout_secs, "memory": memory_mbytes}
    session = get_session()

    resp = session.post(
        url,
        headers={**_apify_headers(), "Content-Type": "application/json"},
        params=params,
        json=input_data,
        timeout=60,
    )
    resp.raise_for_status()
    run_data = resp.json().get("data", {})
    run_id = run_data.get("id")
    if not run_id:
        raise RuntimeError(f"Apify did not return a run ID: {resp.text[:500]}")

    log.info("apify_async_run_started", run_id=run_id)

    # Poll for completion
    elapsed = 0
    status = "UNKNOWN"
    run_info = {}
    while elapsed < MAX_POLL_TIME:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

        try:
            status_resp = session.get(
                f"{APIFY_BASE_URL}/actor-runs/{run_id}",
                headers=_apify_headers(),
                timeout=30,
            )
            status_resp.raise_for_status()
            run_info = status_resp.json().get("data", {})
            status = run_info.get("status", "UNKNOWN")
        except requests.exceptions.RequestException as e:
            log.warning("apify_poll_error", run_id=run_id, error=str(e)[:200])
            continue

        log.debug("apify_poll", run_id=run_id, status=status, elapsed_s=elapsed)
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break
    else:
        log.error("apify_poll_timeout", run_id=run_id, elapsed=elapsed)
        return {"status": "TIMED-OUT", "items": []}

    log.info("apify_async_run_finished", run_id=run_id, status=status)

    if status != "SUCCEEDED":
        return {"status": status, "items": []}

    # Fetch dataset items
    dataset_id = run_info.get("defaultDatasetId")
    if not dataset_id:
        log.warning("apify_no_dataset", run_id=run_id)
        return {"status": status, "items": []}

    items_resp = session.get(
        f"{APIFY_BASE_URL}/datasets/{dataset_id}/items",
        headers=_apify_headers(),
        params={"format": "json"},
        timeout=120,
    )
    items_resp.raise_for_status()
    return {"status": "SUCCEEDED", "items": items_resp.json()}


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------
def estimate_cost(num_locations: int, max_reviews_per: int) -> float:
    """Return estimated dollar cost for a batch of location scrapes."""
    total_reviews = num_locations * max_reviews_per
    cost = (total_reviews / 1000) * COST_PER_1000_REVIEWS
    return round(cost, 2)


def fetch_reviews_for_location(
    place_id: str,
    max_reviews: int = 500,
    language: str = "en",
) -> List[dict]:
    """
    Fetch reviews for a single Google Maps place_id via Apify.

    Returns a list of review dicts from the actor output.
    """
    if not APIFY_API_KEY:
        raise RuntimeError("APIFY_API_KEY environment variable must be set")

    input_data = {
        "startUrls": [
            {"url": f"https://www.google.com/maps/place/?q=place_id:{place_id}"}
        ],
        "maxReviews": max_reviews,
        "language": language,
        "personalData": True,
    }

    log.info("apify_fetch_start", place_id=place_id, max_reviews=max_reviews)
    start = time.monotonic()

    result = _start_actor_run_sync(input_data, timeout_secs=300, memory_mbytes=512)
    elapsed = round(time.monotonic() - start, 1)

    items = result.get("items", [])
    log.info(
        "apify_fetch_done",
        place_id=place_id,
        status=result.get("status"),
        reviews_fetched=len(items),
        elapsed_s=elapsed,
    )
    return items


def batch_fetch_reviews(
    place_ids: List[str],
    max_reviews_per: int = 500,
    language: str = "en",
    daily_budget: Optional[float] = None,
) -> Dict[str, List[dict]]:
    """
    Fetch reviews for multiple place_ids in a single Apify actor run.

    Returns {place_id: [review_dicts]} mapping.
    Respects optional daily budget cap.
    """
    if not APIFY_API_KEY:
        raise RuntimeError("APIFY_API_KEY environment variable must be set")

    # Cost guard
    est_cost = estimate_cost(len(place_ids), max_reviews_per)
    log.info(
        "batch_cost_estimate",
        locations=len(place_ids),
        max_reviews_per=max_reviews_per,
        estimated_cost_usd=est_cost,
    )
    if daily_budget is not None and est_cost > daily_budget:
        affordable = max(1, int(daily_budget / est_cost * len(place_ids)))
        log.warning(
            "batch_budget_trimmed",
            original=len(place_ids),
            trimmed_to=affordable,
            budget=daily_budget,
        )
        place_ids = place_ids[:affordable]

    # Build start URLs for the actor
    start_urls = [
        {"url": f"https://www.google.com/maps/place/?q=place_id:{pid}"}
        for pid in place_ids
    ]

    input_data = {
        "startUrls": start_urls,
        "maxReviews": max_reviews_per,
        "language": language,
        "personalData": True,
    }

    # Scale timeout and memory for larger batches
    timeout = min(max(300, len(place_ids) * 60), 3600)
    memory = 1024 if len(place_ids) > 10 else 512

    log.info(
        "batch_fetch_start",
        locations=len(place_ids),
        timeout_s=timeout,
        memory_mb=memory,
    )
    start = time.monotonic()

    result = _start_actor_run_sync(input_data, timeout_secs=timeout, memory_mbytes=memory)
    elapsed = round(time.monotonic() - start, 1)

    items = result.get("items", [])
    log.info(
        "batch_fetch_done",
        status=result.get("status"),
        total_items=len(items),
        elapsed_s=elapsed,
    )

    # Group results by place_id
    grouped: Dict[str, List[dict]] = {pid: [] for pid in place_ids}
    for item in items:
        # The actor can return placeId, googleId, or embed it in the URL
        item_place_id = item.get("placeId") or item.get("googleId") or ""
        if item_place_id in grouped:
            grouped[item_place_id].append(item)
        else:
            # Fall back to URL matching
            url = item.get("url") or item.get("placeUrl") or ""
            matched = False
            for pid in place_ids:
                if pid in url:
                    grouped[pid].append(item)
                    matched = True
                    break
            if not matched and len(place_ids) == 1:
                # Single-location run: attach everything to the sole place_id
                grouped[place_ids[0]].append(item)

    return grouped


# ---------------------------------------------------------------------------
# Review hashing & DB persistence
# ---------------------------------------------------------------------------
def _make_review_hash(
    author_name: str, text: str, rating: int, time_posted: Optional[str]
) -> str:
    """Produce a stable SHA-256 hash (40 chars) for deduplication."""
    raw = f"{author_name or ''}|{text or ''}|{rating}|{time_posted or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def _parse_review_time(raw) -> Optional[datetime]:
    """Parse various time formats returned by the Apify actor."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(raw, tz=timezone.utc)
        except (OSError, ValueError):
            return None
    if isinstance(raw, str):
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(raw, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
    return None


def save_reviews_to_db(
    reviews: List[dict], location_id: int, place_id: str = ""
) -> Tuple[int, int]:
    """
    Save Apify review items into the reviews table.

    Returns (saved_count, skipped_duplicate_count).
    Performs hash-based deduplication against existing reviews.
    """
    conn = get_connection()
    saved = 0
    skipped = 0

    try:
        # Pre-load existing hashes for this location for fast dedup
        existing_hashes: set = set()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT review_hash FROM reviews "
                "WHERE location_id = %s AND review_hash IS NOT NULL",
                (location_id,),
            )
            existing_hashes = {row[0] for row in cur.fetchall()}

        log.debug(
            "existing_hashes_loaded",
            location_id=location_id,
            count=len(existing_hashes),
        )

        with conn.cursor() as cur:
            for item in reviews:
                try:
                    # ---- Extract fields from Apify output ----
                    author_name = (
                        item.get("name")
                        or item.get("authorName")
                        or item.get("reviewerName")
                        or item.get("author")
                        or "Anonymous"
                    )

                    rating = (
                        item.get("stars")
                        or item.get("rating")
                        or item.get("reviewRating")
                    )
                    if rating is None:
                        skipped += 1
                        continue
                    try:
                        rating = int(rating)
                    except (ValueError, TypeError):
                        skipped += 1
                        continue
                    if rating < 1 or rating > 5:
                        skipped += 1
                        continue

                    text = (
                        item.get("text")
                        or item.get("reviewText")
                        or item.get("comment")
                        or item.get("snippet")
                        or ""
                    )
                    language = (
                        item.get("reviewLanguage")
                        or item.get("language")
                        or "en"
                    )

                    # Parse review time from multiple possible fields
                    time_posted_raw = (
                        item.get("publishedAtDate")
                        or item.get("publishAt")
                        or item.get("reviewDate")
                        or item.get("time")
                        or item.get("timestamp")
                    )
                    time_posted = _parse_review_time(time_posted_raw)

                    # ---- Deduplication ----
                    review_hash = _make_review_hash(
                        author_name,
                        text,
                        rating,
                        time_posted.isoformat() if time_posted else "",
                    )
                    if review_hash in existing_hashes:
                        skipped += 1
                        continue

                    # ---- Insert ----
                    cur.execute(
                        """
                        INSERT INTO reviews (
                            location_id, place_id, author_name, rating,
                            text, time_posted, language, source,
                            review_hash, sentiment_score, created_at
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, NOW()
                        )
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            location_id,
                            place_id,
                            author_name,
                            rating,
                            text,
                            time_posted,
                            language,
                            "apify_google",
                            review_hash,
                            None,  # sentiment_score filled by NLP pipeline
                        ),
                    )
                    if cur.rowcount > 0:
                        saved += 1
                        existing_hashes.add(review_hash)
                    else:
                        skipped += 1

                except Exception as e:
                    log.warning(
                        "review_save_error",
                        error=str(e)[:200],
                        location_id=location_id,
                    )
                    conn.rollback()
                    continue

        # Update review_count and updated_at on the location row
        if saved > 0:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE locations SET
                        review_count = (
                            SELECT COUNT(*) FROM reviews WHERE location_id = %s
                        ),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (location_id, location_id),
                )
        conn.commit()

    except Exception as e:
        log.error(
            "save_reviews_to_db_error",
            error=str(e)[:300],
            location_id=location_id,
        )
        conn.rollback()
    finally:
        return_connection(conn)

    return saved, skipped


# ---------------------------------------------------------------------------
# DB query helpers
# ---------------------------------------------------------------------------
def get_locations_needing_reviews(
    min_reviews: int = 10,
    chain_name: Optional[str] = None,
    limit: int = 100,
    oldest_first: bool = False,
) -> List[dict]:
    """
    Find locations that have fewer than *min_reviews* reviews in the DB.

    If oldest_first=True, sort by updated_at ASC (NULL first) so that
    locations with the stalest data get priority.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = [
                "l.place_id IS NOT NULL",
                "l.place_id LIKE 'ChIJ%%'",
                "COALESCE(l.review_count, 0) < %s",
            ]
            params: list = [min_reviews]

            if chain_name:
                conditions.append("l.chain_name ILIKE %s")
                params.append(f"%{chain_name}%")

            where = " AND ".join(conditions)
            order = (
                "l.updated_at ASC NULLS FIRST, l.id"
                if oldest_first
                else "COALESCE(l.review_count, 0) ASC, l.id"
            )

            params.append(limit)
            cur.execute(
                f"""
                SELECT l.id, l.place_id, l.name, l.chain_name,
                       l.city, l.country,
                       COALESCE(l.review_count, 0) AS review_count,
                       l.updated_at AS last_scraped
                FROM locations l
                WHERE {where}
                ORDER BY {order}
                LIMIT %s
                """,
                params,
            )
            return cur.fetchall()
    finally:
        return_connection(conn)


def get_locations_by_chain(chain_name: str, limit: int = 200) -> List[dict]:
    """Return locations for a given chain, ordered by fewest reviews first."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT l.id, l.place_id, l.name, l.chain_name,
                       l.city, l.country,
                       COALESCE(l.review_count, 0) AS review_count,
                       l.updated_at AS last_scraped
                FROM locations l
                WHERE l.chain_name ILIKE %s
                  AND l.place_id IS NOT NULL
                  AND l.place_id LIKE 'ChIJ%%'
                ORDER BY COALESCE(l.review_count, 0) ASC, l.id
                LIMIT %s
                """,
                (f"%{chain_name}%", limit),
            )
            return cur.fetchall()
    finally:
        return_connection(conn)


def get_stale_locations(limit: int = 100) -> List[dict]:
    """
    Return locations sorted by oldest updated_at (NULL first).
    Used by the cron wrapper for daily incremental fetches.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT l.id, l.place_id, l.name, l.chain_name,
                       l.city, l.country,
                       COALESCE(l.review_count, 0) AS review_count,
                       l.updated_at AS last_scraped
                FROM locations l
                WHERE l.place_id IS NOT NULL
                  AND l.place_id LIKE 'ChIJ%%'
                ORDER BY l.updated_at ASC NULLS FIRST, l.id
                LIMIT %s
                """,
                (limit,),
            )
            return cur.fetchall()
    finally:
        return_connection(conn)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def process_locations(
    locations: List[dict],
    max_reviews: int = 500,
    dry_run: bool = False,
    daily_budget: Optional[float] = None,
) -> Dict[str, int]:
    """
    End-to-end pipeline: fetch reviews via Apify and persist in PostgreSQL.

    Returns a summary stats dict.
    """
    stats = {
        "locations_total": len(locations),
        "locations_processed": 0,
        "locations_with_new_reviews": 0,
        "reviews_saved": 0,
        "reviews_skipped_dup": 0,
        "errors": 0,
        "estimated_cost_usd": estimate_cost(len(locations), max_reviews),
    }

    if not locations:
        log.info("no_locations_to_process")
        return stats

    # ---- Cost report ----
    log.info(
        "cost_estimate",
        locations=len(locations),
        max_reviews=max_reviews,
        estimated_usd=stats["estimated_cost_usd"],
    )
    if dry_run:
        log.info(
            "dry_run_exit",
            msg="No API calls will be made. Showing estimate only.",
        )
        _print_dry_run_table(locations, max_reviews, stats["estimated_cost_usd"])
        return stats

    # ---- Budget guard ----
    if daily_budget is not None and stats["estimated_cost_usd"] > daily_budget:
        affordable = max(
            1, int(daily_budget / stats["estimated_cost_usd"] * len(locations))
        )
        log.warning(
            "budget_trim",
            original=len(locations),
            affordable=affordable,
            budget_usd=daily_budget,
        )
        locations = locations[:affordable]
        stats["locations_total"] = len(locations)
        stats["estimated_cost_usd"] = estimate_cost(len(locations), max_reviews)

    # ---- Chunk into groups of 20 for Apify efficiency ----
    CHUNK_SIZE = 20
    chunks = [
        locations[i : i + CHUNK_SIZE]
        for i in range(0, len(locations), CHUNK_SIZE)
    ]

    for chunk_idx, chunk in enumerate(chunks):
        log.info(
            "processing_chunk",
            chunk=chunk_idx + 1,
            total_chunks=len(chunks),
            locations_in_chunk=len(chunk),
        )

        place_ids = [loc["place_id"] for loc in chunk]
        pid_to_loc = {loc["place_id"]: loc for loc in chunk}

        try:
            grouped = batch_fetch_reviews(
                place_ids,
                max_reviews_per=max_reviews,
                daily_budget=daily_budget,
            )

            for pid, rev_items in grouped.items():
                loc = pid_to_loc.get(pid)
                if not loc:
                    continue

                if not rev_items:
                    stats["locations_processed"] += 1
                    continue

                saved, duped = save_reviews_to_db(
                    rev_items, loc["id"], place_id=pid
                )
                stats["reviews_saved"] += saved
                stats["reviews_skipped_dup"] += duped
                stats["locations_processed"] += 1
                if saved > 0:
                    stats["locations_with_new_reviews"] += 1

                log.info(
                    "location_done",
                    place_id=pid,
                    name=loc.get("name", "")[:50],
                    chain=loc.get("chain_name", ""),
                    saved=saved,
                    duped=duped,
                )

        except requests.exceptions.HTTPError as e:
            stats["errors"] += 1
            status_code = getattr(e.response, "status_code", "?")
            log.error(
                "chunk_http_error",
                chunk=chunk_idx + 1,
                status=status_code,
                error=str(e)[:200],
            )
        except Exception as e:
            stats["errors"] += 1
            log.error(
                "chunk_error", chunk=chunk_idx + 1, error=str(e)[:300]
            )

        # Rate-limit between chunks
        if chunk_idx < len(chunks) - 1:
            time.sleep(MIN_DELAY_BETWEEN_RUNS)

    return stats


def _print_dry_run_table(
    locations: List[dict], max_reviews: int, total_cost: float
):
    """Print a human-readable summary table for dry-run mode."""
    print("\n" + "=" * 72)
    print("  APIFY GOOGLE REVIEWS -- DRY RUN COST ESTIMATE")
    print("=" * 72)
    print(f"  Locations to scrape:  {len(locations)}")
    print(f"  Max reviews/location: {max_reviews}")
    print(f"  Cost per 1K reviews:  ${COST_PER_1000_REVIEWS:.2f}")
    print(f"  Estimated total cost: ${total_cost:.2f}")
    print("-" * 72)
    print(f"  {'#':<4} {'Place ID':<30} {'Name':<25} {'Chain':<15}")
    print("-" * 72)
    for i, loc in enumerate(locations[:25]):
        pid = loc.get("place_id", "")[:28]
        name = (loc.get("name", "") or "")[:23]
        chain = (loc.get("chain_name", "") or "")[:13]
        print(f"  {i+1:<4} {pid:<30} {name:<25} {chain:<15}")
    if len(locations) > 25:
        print(f"  ... and {len(locations) - 25} more locations")
    print("=" * 72 + "\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Apify Google Maps Reviews Scraper for ReviewSignal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single place
  python3 scripts/apify_google_reviews.py --place-id ChIJN1t_tDeuEmsRUsoyG83frY4

  # Chain batch
  python3 scripts/apify_google_reviews.py --chain-name "Starbucks" --limit 50

  # Backfill locations with < 10 reviews
  python3 scripts/apify_google_reviews.py --backfill --min-reviews 10 --limit 100

  # Dry run (cost estimate only, no Apify calls)
  python3 scripts/apify_google_reviews.py --chain-name "KFC" --dry-run

  # Cron-style: oldest data first, $1 budget cap
  python3 scripts/apify_google_reviews.py --backfill --oldest-first --budget 1.00
        """,
    )
    parser.add_argument(
        "--place-id", type=str,
        help="Single Google Maps place_id to scrape",
    )
    parser.add_argument(
        "--chain-name", type=str,
        help="Scrape locations matching this chain name",
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Max locations to process (default: 100)",
    )
    parser.add_argument(
        "--max-reviews", type=int, default=500,
        help="Max reviews per location (default: 500)",
    )
    parser.add_argument(
        "--min-reviews", type=int, default=10,
        help="Threshold for --backfill mode (default: 10)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show cost estimate only, no API calls",
    )
    parser.add_argument(
        "--backfill", action="store_true",
        help="Target locations with fewer than --min-reviews",
    )
    parser.add_argument(
        "--budget", type=float, default=None,
        help="Max USD spend for this run",
    )
    parser.add_argument(
        "--oldest-first", action="store_true",
        help="Prioritize locations with oldest review data",
    )

    args = parser.parse_args()

    # ---- Validate ----
    if not APIFY_API_KEY and not args.dry_run:
        log.error(
            "APIFY_API_KEY is not set. Add APIFY_API_KEY=your_key to .env"
        )
        sys.exit(1)

    if not any([args.place_id, args.chain_name, args.backfill]):
        parser.error(
            "You must specify --place-id, --chain-name, or --backfill"
        )

    start_time = time.monotonic()

    # ======== Single place_id mode ========
    if args.place_id:
        cost = estimate_cost(1, args.max_reviews)
        log.info(
            "single_location_mode",
            place_id=args.place_id,
            est_cost_usd=cost,
        )

        if args.dry_run:
            print(
                f"\n  Dry run: 1 location, up to {args.max_reviews} "
                f"reviews, est. ${cost:.2f}\n"
            )
            return

        # Look up the location row in PostgreSQL
        conn = get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, place_id, name, chain_name "
                    "FROM locations WHERE place_id = %s",
                    (args.place_id,),
                )
                loc = cur.fetchone()
        finally:
            return_connection(conn)

        if not loc:
            log.error(
                "place_id_not_in_db",
                place_id=args.place_id,
                hint="The place_id must already exist in the locations table.",
            )
            sys.exit(1)

        reviews = fetch_reviews_for_location(
            args.place_id, max_reviews=args.max_reviews
        )
        if reviews:
            saved, duped = save_reviews_to_db(
                reviews, loc["id"], place_id=args.place_id
            )
            log.info(
                "single_done",
                name=loc.get("name", ""),
                saved=saved,
                duped=duped,
                elapsed_s=round(time.monotonic() - start_time, 1),
            )
        else:
            log.warning("no_reviews_returned", place_id=args.place_id)
        return

    # ======== Chain mode ========
    if args.chain_name:
        locations = get_locations_by_chain(args.chain_name, limit=args.limit)
        log.info(
            "chain_mode", chain=args.chain_name, locations_found=len(locations)
        )

    # ======== Backfill mode ========
    elif args.backfill:
        locations = get_locations_needing_reviews(
            min_reviews=args.min_reviews,
            chain_name=args.chain_name,
            limit=args.limit,
            oldest_first=args.oldest_first,
        )
        log.info(
            "backfill_mode",
            min_reviews=args.min_reviews,
            locations_found=len(locations),
        )
    else:
        locations = []

    if not locations:
        log.info("no_locations_found")
        return

    # ======== Process ========
    stats = process_locations(
        locations,
        max_reviews=args.max_reviews,
        dry_run=args.dry_run,
        daily_budget=args.budget,
    )

    elapsed = round(time.monotonic() - start_time, 1)

    # ======== Final report ========
    print("\n" + "=" * 60)
    print("  APIFY GOOGLE REVIEWS -- RUN COMPLETE")
    print("=" * 60)
    print(f"  Locations total:          {stats['locations_total']}")
    print(f"  Locations processed:      {stats['locations_processed']}")
    print(f"  Locations w/ new reviews: {stats['locations_with_new_reviews']}")
    print(f"  Reviews saved:            {stats['reviews_saved']}")
    print(f"  Reviews skipped (dupes):  {stats['reviews_skipped_dup']}")
    print(f"  Errors:                   {stats['errors']}")
    print(f"  Estimated cost:           ${stats['estimated_cost_usd']:.2f}")
    print(f"  Elapsed:                  {elapsed}s")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
