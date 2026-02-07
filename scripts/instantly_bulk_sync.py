#!/usr/bin/env python3
"""
Instantly Bulk Sync Script
==========================
Syncs existing leads from PostgreSQL to Instantly campaigns via API v2.
Groups leads by segment and routes to the correct campaign.

Usage:
    python scripts/instantly_bulk_sync.py --dry-run          # Preview without syncing
    python scripts/instantly_bulk_sync.py                     # Sync all pending leads
    python scripts/instantly_bulk_sync.py --limit 50          # Sync max 50 leads
    python scripts/instantly_bulk_sync.py --segment cio       # Sync only CIO segment
    python scripts/instantly_bulk_sync.py --dry-run --limit 10  # Preview first 10

Author: ReviewSignal.ai
"""

import argparse
import os
import sys
import time
import logging
from datetime import datetime
from typing import Optional

import httpx
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# Configuration
INSTANTLY_API_KEY = os.getenv("INSTANTLY_API_KEY", "")
INSTANTLY_BASE_URL = "https://api.instantly.ai/api/v2/leads"

# Campaign mapping by segment (matches .env variable names)
CAMPAIGN_MAPPING = {
    "portfolio_manager": os.getenv("INSTANTLY_CAMPAIGN_PM", ""),
    "quant_analyst": os.getenv("INSTANTLY_CAMPAIGN_QUANT", ""),
    "head_alt_data": os.getenv("INSTANTLY_CAMPAIGN_ALTDATA", ""),
    "cio": os.getenv("INSTANTLY_CAMPAIGN_CIO", ""),
    "high_intent": os.getenv("INSTANTLY_CAMPAIGN_INTENT", ""),
}

# Default campaign for leads without a segment-specific campaign
DEFAULT_CAMPAIGN_ID = os.getenv("INSTANTLY_CAMPAIGN_ID", "")

# Rate limiting: max 10 requests per second
RATE_LIMIT_RPS = 10
RATE_LIMIT_INTERVAL = 1.0 / RATE_LIMIT_RPS  # 0.1 seconds between requests

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "reviewsignal"),
    "user": os.getenv("DB_USER", "reviewsignal"),
    "password": os.getenv("DB_PASS"),
}

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("instantly_bulk_sync")


def get_db_connection():
    """Create a database connection."""
    db_pass = DB_CONFIG.get("password")
    if not db_pass:
        raise RuntimeError("DB_PASS environment variable must be set")
    return psycopg2.connect(**DB_CONFIG)


def fetch_pending_leads(conn, segment_filter=None, limit=None):
    """
    Fetch leads that need to be synced to Instantly.

    Criteria:
    - nurture_sequence = false (not yet synced)
    - email IS NOT NULL
    - segment IS NOT NULL (must be segmented)
    """
    query = """
        SELECT
            id, email, name, title, company,
            linkedin_url, lead_score, personalized_angle,
            segment, priority
        FROM leads
        WHERE nurture_sequence = false
        AND email IS NOT NULL
        AND segment IS NOT NULL
    """
    params = []

    if segment_filter:
        query += " AND segment = %s"
        params.append(segment_filter)

    query += " ORDER BY lead_score DESC NULLS LAST, id ASC"

    if limit:
        query += " LIMIT %s"
        params.append(limit)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        return cur.fetchall()


def mark_leads_synced(conn, lead_ids):
    """Mark leads as synced to Instantly (nurture_sequence = true)."""
    if not lead_ids:
        return 0

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE leads
            SET nurture_sequence = true,
                contacted_at = %s
            WHERE id = ANY(%s)
            """,
            (datetime.utcnow(), lead_ids),
        )
        conn.commit()
        return cur.rowcount


def get_campaign_id_for_segment(segment):
    """Get the Instantly campaign ID for a given segment."""
    campaign_id = CAMPAIGN_MAPPING.get(segment, "")
    if not campaign_id:
        campaign_id = DEFAULT_CAMPAIGN_ID
    return campaign_id


def split_name(full_name):
    """Split full name into (first_name, last_name)."""
    if not full_name:
        return ("there", "")
    parts = full_name.strip().split(None, 1)
    first_name = parts[0] if len(parts) >= 1 else "there"
    last_name = parts[1] if len(parts) >= 2 else ""
    return (first_name, last_name)


def sync_lead_to_instantly(client, lead, campaign_id):
    """
    Sync a single lead to Instantly via API v2.
    Returns (success: bool, response_text: str)
    """
    first_name, last_name = split_name(lead.get("name"))

    custom_variables = {
        "title": lead.get("title") or "",
        "company_name": lead.get("company") or "",
        "linkedin": lead.get("linkedin_url") or "",
        "segment": lead.get("segment") or "",
        "lead_score": str(lead.get("lead_score") or 50),
        "priority": lead.get("priority") or "medium",
    }

    if lead.get("personalized_angle"):
        custom_variables["personalized_angle"] = lead["personalized_angle"]

    payload = {
        "campaign_id": campaign_id,
        "email": lead["email"],
        "first_name": first_name,
        "last_name": last_name,
        "company_name": lead.get("company") or "",
        "personalization": lead.get("personalized_angle") or lead.get("title") or "",
        "custom_variables": custom_variables,
    }

    try:
        response = client.post(
            INSTANTLY_BASE_URL,
            json=payload,
            headers={
                "Authorization": "Bearer " + INSTANTLY_API_KEY,
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )

        if response.status_code in (200, 201):
            return (True, response.text)
        else:
            return (False, "HTTP %d: %s" % (response.status_code, response.text))
    except httpx.TimeoutException:
        return (False, "Request timed out")
    except httpx.RequestError as e:
        return (False, "Request error: %s" % str(e))


def run_sync(dry_run=False, limit=None, segment_filter=None):
    """
    Main sync function.

    Args:
        dry_run: If True, only preview what would be synced
        limit: Maximum number of leads to sync
        segment_filter: Only sync leads from this segment

    Returns dict with sync statistics.
    """
    stats = {
        "total_pending": 0,
        "synced": 0,
        "failed": 0,
        "skipped_no_campaign": 0,
        "by_segment": {},
        "errors": [],
    }

    # Validate configuration
    if not INSTANTLY_API_KEY and not dry_run:
        logger.error("INSTANTLY_API_KEY not set in environment")
        print("\nERROR: INSTANTLY_API_KEY environment variable is not set.")
        print("Set it in your .env file and try again.")
        return stats

    # Check campaign mappings
    configured_campaigns = {k: v for k, v in CAMPAIGN_MAPPING.items() if v}
    if not configured_campaigns and not DEFAULT_CAMPAIGN_ID:
        logger.error("No campaign IDs configured")
        print("\nERROR: No Instantly campaign IDs are configured.")
        print("Set INSTANTLY_CAMPAIGN_* variables in your .env file.")
        return stats

    logger.info("Connecting to database...")
    conn = get_db_connection()

    try:
        # Fetch pending leads
        leads = fetch_pending_leads(conn, segment_filter, limit)
        stats["total_pending"] = len(leads)

        if not leads:
            logger.info("No pending leads to sync")
            print("\nNo pending leads found matching criteria.")
            return stats

        # Group by segment for reporting
        by_segment = {}
        for lead in leads:
            seg = lead["segment"]
            if seg not in by_segment:
                by_segment[seg] = []
            by_segment[seg].append(lead)

        # Print summary
        print("\n" + "=" * 70)
        if dry_run:
            print("INSTANTLY BULK SYNC (DRY RUN)")
        else:
            print("INSTANTLY BULK SYNC")
        print("Date: %s" % datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))
        print("=" * 70 + "\n")

        print("Total leads to sync: %d" % len(leads))
        if limit:
            print("Limit: %d" % limit)
        if segment_filter:
            print("Segment filter: %s" % segment_filter)
        print()

        print("Segment breakdown:")
        print("  %-25s %6s %-40s" % ("Segment", "Count", "Campaign ID"))
        print("  %s %s %s" % ("-" * 25, "-" * 6, "-" * 40))

        for seg, seg_leads in sorted(by_segment.items(), key=lambda x: -len(x[1])):
            campaign_id = get_campaign_id_for_segment(seg)
            status = campaign_id[:36] + "..." if campaign_id else "NOT CONFIGURED"
            print("  %-25s %6d %-40s" % (seg, len(seg_leads), status))
            stats["by_segment"][seg] = {
                "total": len(seg_leads), "synced": 0, "failed": 0
            }

        print()

        if dry_run:
            print("DRY RUN MODE - No leads will be synced.\n")
            print("Sample leads that would be synced:")
            print("  %-40s %-20s %-25s" % ("Email", "Segment", "Company"))
            print("  %s %s %s" % ("-" * 40, "-" * 20, "-" * 25))
            for lead in leads[:20]:
                company = (lead.get("company") or "N/A")[:25]
                print(
                    "  %-40s %-20s %-25s"
                    % (lead["email"], lead["segment"], company)
                )
            if len(leads) > 20:
                print("  ... and %d more leads" % (len(leads) - 20))
            print()
            return stats

        # Actual sync
        logger.info("Starting sync of %d leads..." % len(leads))
        synced_ids = []
        last_request_time = 0.0

        with httpx.Client() as client:
            for i, lead in enumerate(leads, 1):
                segment = lead["segment"]
                campaign_id = get_campaign_id_for_segment(segment)

                if not campaign_id:
                    stats["skipped_no_campaign"] += 1
                    logger.warning(
                        "No campaign for segment '%s', skipping %s"
                        % (segment, lead["email"])
                    )
                    continue

                # Rate limiting
                elapsed = time.time() - last_request_time
                if elapsed < RATE_LIMIT_INTERVAL:
                    time.sleep(RATE_LIMIT_INTERVAL - elapsed)

                last_request_time = time.time()
                success, response_text = sync_lead_to_instantly(
                    client, lead, campaign_id
                )

                if success:
                    stats["synced"] += 1
                    stats["by_segment"][segment]["synced"] += 1
                    synced_ids.append(lead["id"])

                    if i % 50 == 0 or i == len(leads):
                        logger.info("Progress: %d/%d synced" % (i, len(leads)))
                else:
                    stats["failed"] += 1
                    stats["by_segment"][segment]["failed"] += 1
                    stats["errors"].append(
                        {"email": lead["email"], "error": response_text}
                    )
                    logger.error(
                        "Failed to sync %s: %s"
                        % (lead["email"], response_text)
                    )

                # Batch update nurture_sequence every 100 leads
                if len(synced_ids) >= 100:
                    mark_leads_synced(conn, synced_ids)
                    logger.info(
                        "Marked %d leads as synced in DB" % len(synced_ids)
                    )
                    synced_ids = []

        # Mark remaining synced leads
        if synced_ids:
            mark_leads_synced(conn, synced_ids)
            logger.info(
                "Marked final %d leads as synced in DB" % len(synced_ids)
            )

    finally:
        conn.close()

    # Print results
    print("\n" + "=" * 70)
    print("SYNC RESULTS")
    print("=" * 70 + "\n")
    print("  Total processed:       %d" % stats["total_pending"])
    print("  Successfully synced:   %d" % stats["synced"])
    print("  Failed:                %d" % stats["failed"])
    print("  Skipped (no campaign): %d" % stats["skipped_no_campaign"])
    print()

    if stats["by_segment"]:
        print("  By segment:")
        for seg, seg_stats in stats["by_segment"].items():
            print(
                "    %-25s synced=%-5d failed=%-5d"
                % (seg, seg_stats["synced"], seg_stats["failed"])
            )
        print()

    if stats["errors"]:
        print("  Errors (%d):" % len(stats["errors"]))
        for err in stats["errors"][:10]:
            print("    %s: %s" % (err["email"], err["error"]))
        if len(stats["errors"]) > 10:
            print(
                "    ... and %d more errors" % (len(stats["errors"]) - 10)
            )
        print()

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Sync leads from PostgreSQL to Instantly campaigns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/instantly_bulk_sync.py --dry-run
  python scripts/instantly_bulk_sync.py --limit 50
  python scripts/instantly_bulk_sync.py --segment cio
  python scripts/instantly_bulk_sync.py --dry-run --segment high_intent
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be synced without making API calls",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of leads to sync",
    )
    parser.add_argument(
        "--segment",
        type=str,
        default=None,
        choices=list(CAMPAIGN_MAPPING.keys()),
        help="Only sync leads from this segment",
    )

    args = parser.parse_args()

    # Validate API key early
    if not INSTANTLY_API_KEY and not args.dry_run:
        print("ERROR: INSTANTLY_API_KEY not set. Use --dry-run to preview.")
        sys.exit(1)

    db_pass = os.getenv("DB_PASS")
    if not db_pass:
        print("ERROR: DB_PASS environment variable must be set.")
        sys.exit(1)

    print("\nReviewSignal - Instantly Bulk Sync\n")

    stats = run_sync(
        dry_run=args.dry_run,
        limit=args.limit,
        segment_filter=args.segment,
    )

    if not args.dry_run and stats["synced"] > 0:
        print("Done! %d leads synced to Instantly.\n" % stats["synced"])
    elif args.dry_run:
        print("Dry run complete. Use without --dry-run to sync.\n")
    else:
        print("No leads were synced.\n")


if __name__ == "__main__":
    main()
