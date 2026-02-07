#!/usr/bin/env python3
"""
Review Data Quality Cleanup Script.

Fixes all known data quality issues in the reviews table:
1. Duplicate reviews (same text + location_id) - keeps oldest (lowest id)
2. Orphan reviews (NULL location_id with no matchable place_id)
3. Very short reviews (<3 chars) that add no analytical value
4. Adds a unique index to prevent future duplicates

Usage:
    python3 scripts/clean_duplicate_reviews.py --dry-run     # Preview only
    python3 scripts/clean_duplicate_reviews.py               # Execute cleanup
    python3 scripts/clean_duplicate_reviews.py --skip-index   # Skip index creation

Requires: DB_PASS environment variable.
"""

import argparse
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from modules.db import get_connection, return_connection


def count_duplicates(conn):
    """Count duplicate review groups and total excess rows."""
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) as groups, COALESCE(SUM(cnt - 1), 0) as excess
        FROM (
            SELECT text, location_id, COUNT(*) as cnt
            FROM reviews
            WHERE text IS NOT NULL AND location_id IS NOT NULL
            GROUP BY text, location_id
            HAVING COUNT(*) > 1
        ) sub
    """)
    row = cur.fetchone()
    cur.close()
    return {"groups": row[0], "excess_rows": row[1]}


def delete_duplicates(conn, dry_run=False):
    """Delete duplicate reviews, keeping the one with the lowest id per group."""
    cur = conn.cursor()

    # First, count what we will delete
    cur.execute("""
        SELECT COUNT(*) FROM reviews
        WHERE id IN (
            SELECT r.id
            FROM reviews r
            INNER JOIN (
                SELECT text, location_id, MIN(id) as keep_id
                FROM reviews
                WHERE text IS NOT NULL AND location_id IS NOT NULL
                GROUP BY text, location_id
                HAVING COUNT(*) > 1
            ) dup ON r.text = dup.text
                 AND r.location_id = dup.location_id
                 AND r.id > dup.keep_id
        )
    """)
    to_delete = cur.fetchone()[0]

    if to_delete == 0:
        cur.close()
        return 0

    if dry_run:
        print("  [DRY RUN] Would delete %d duplicate review rows" % to_delete)
        cur.close()
        return to_delete

    # Delete duplicates, keeping the oldest (lowest id) in each group
    cur.execute("""
        DELETE FROM reviews
        WHERE id IN (
            SELECT r.id
            FROM reviews r
            INNER JOIN (
                SELECT text, location_id, MIN(id) as keep_id
                FROM reviews
                WHERE text IS NOT NULL AND location_id IS NOT NULL
                GROUP BY text, location_id
                HAVING COUNT(*) > 1
            ) dup ON r.text = dup.text
                 AND r.location_id = dup.location_id
                 AND r.id > dup.keep_id
        )
    """)
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    return deleted


def count_orphans(conn):
    """Count reviews with NULL location_id."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM reviews WHERE location_id IS NULL")
    count = cur.fetchone()[0]
    cur.close()
    return count


def delete_orphans(conn, dry_run=False):
    """Delete reviews with NULL location_id (unmatchable orphans)."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM reviews WHERE location_id IS NULL")
    to_delete = cur.fetchone()[0]

    if to_delete == 0:
        cur.close()
        return 0

    if dry_run:
        print("  [DRY RUN] Would delete %d orphan reviews (NULL location_id)" % to_delete)
        cur.close()
        return to_delete

    cur.execute("DELETE FROM reviews WHERE location_id IS NULL")
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    return deleted


def count_short_reviews(conn, min_length=3):
    """Count reviews with text shorter than min_length."""
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM reviews WHERE text IS NOT NULL AND length(text) < %s",
        (min_length,)
    )
    count = cur.fetchone()[0]
    cur.close()
    return count


def delete_short_reviews(conn, min_length=3, dry_run=False):
    """Delete reviews with text shorter than min_length chars."""
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM reviews WHERE text IS NOT NULL AND length(text) < %s",
        (min_length,)
    )
    to_delete = cur.fetchone()[0]

    if to_delete == 0:
        cur.close()
        return 0

    if dry_run:
        print("  [DRY RUN] Would delete %d short reviews (text < %d chars)" % (to_delete, min_length))
        cur.close()
        return to_delete

    cur.execute(
        "DELETE FROM reviews WHERE text IS NOT NULL AND length(text) < %s",
        (min_length,)
    )
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    return deleted


def check_dedup_index_exists(conn):
    """Check if the deduplication prevention index already exists."""
    cur = conn.cursor()
    cur.execute("""
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_reviews_text_location_unique'
    """)
    exists = cur.fetchone() is not None
    cur.close()
    return exists


def create_dedup_index(conn, dry_run=False):
    """Create a unique partial index to prevent future duplicates."""
    if check_dedup_index_exists(conn):
        print("  Index idx_reviews_text_location_unique already exists - skipping")
        return False

    if dry_run:
        print("  [DRY RUN] Would create unique index on (md5(text), location_id)")
        return True

    cur = conn.cursor()
    # Use md5 hash of text to keep the index small while still detecting dupes
    cur.execute("""
        CREATE UNIQUE INDEX idx_reviews_text_location_unique
        ON reviews (md5(text), location_id)
        WHERE text IS NOT NULL AND location_id IS NOT NULL
    """)
    conn.commit()
    cur.close()
    return True


def get_review_stats(conn):
    """Get comprehensive review statistics."""
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN sentiment_score IS NOT NULL THEN 1 END) as with_sentiment,
            COUNT(CASE WHEN rating IS NOT NULL THEN 1 END) as with_rating,
            COUNT(CASE WHEN text IS NOT NULL AND length(text) > 0 THEN 1 END) as with_text,
            COUNT(CASE WHEN text IS NOT NULL AND length(text) >= 3 THEN 1 END) as with_meaningful_text,
            COUNT(CASE WHEN location_id IS NOT NULL THEN 1 END) as with_location,
            COUNT(CASE WHEN source IS NOT NULL THEN 1 END) as with_source,
            ROUND(AVG(rating)::numeric, 2) as avg_rating,
            ROUND(AVG(sentiment_score)::numeric, 4) as avg_sentiment
        FROM reviews
    """)
    row = cur.fetchone()
    cols = [desc[0] for desc in cur.description]
    cur.close()
    return dict(zip(cols, row))


def main():
    parser = argparse.ArgumentParser(
        description="Clean review data quality issues: duplicates, orphans, short reviews."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes without modifying the database"
    )
    parser.add_argument(
        "--skip-index", action="store_true",
        help="Skip creating the deduplication prevention index"
    )
    parser.add_argument(
        "--min-length", type=int, default=3,
        help="Minimum text length to keep (default: 3)"
    )
    args = parser.parse_args()

    start_time = time.time()
    mode = "DRY RUN" if args.dry_run else "EXECUTE"

    print("=" * 70)
    print("  REVIEW DATA QUALITY CLEANUP - %s" % mode)
    print("=" * 70)
    print()

    conn = get_connection()
    try:
        # --- Pre-cleanup stats ---
        print("  [1/6] Gathering pre-cleanup statistics...")
        pre_stats = get_review_stats(conn)
        dup_info = count_duplicates(conn)
        orphan_count = count_orphans(conn)
        short_count = count_short_reviews(conn, args.min_length)

        print("        Total reviews:        %s" % "{:,}".format(pre_stats["total"]))
        print("        With sentiment:       %s" % "{:,}".format(pre_stats["with_sentiment"]))
        print("        With rating:          %s" % "{:,}".format(pre_stats["with_rating"]))
        print("        With text (>0):       %s" % "{:,}".format(pre_stats["with_text"]))
        print("        With location_id:     %s" % "{:,}".format(pre_stats["with_location"]))
        print("        Duplicate groups:     %s" % "{:,}".format(dup_info["groups"]))
        print("        Duplicate excess:     %s" % "{:,}".format(dup_info["excess_rows"]))
        print("        Orphans (no loc):     %s" % "{:,}".format(orphan_count))
        print("        Short text (<%d):     %s" % (args.min_length, "{:,}".format(short_count)))
        print()

        total_to_remove = dup_info["excess_rows"] + orphan_count + short_count
        if total_to_remove == 0:
            print("  Nothing to clean. All reviews are in good shape.")
            print("=" * 70)
            return

        # --- Step 2: Remove duplicates ---
        print("  [2/6] Removing duplicate reviews (keeping oldest per group)...")
        dup_deleted = delete_duplicates(conn, dry_run=args.dry_run)
        print("        Deleted: %s duplicate rows" % "{:,}".format(dup_deleted))
        print()

        # --- Step 3: Remove orphans ---
        print("  [3/6] Removing orphan reviews (NULL location_id, no place_id)...")
        orphan_deleted = delete_orphans(conn, dry_run=args.dry_run)
        print("        Deleted: %s orphan rows" % "{:,}".format(orphan_deleted))
        print()

        # --- Step 4: Remove short reviews ---
        print("  [4/6] Removing very short reviews (text < %d chars)..." % args.min_length)
        short_deleted = delete_short_reviews(conn, args.min_length, dry_run=args.dry_run)
        print("        Deleted: %s short review rows" % "{:,}".format(short_deleted))
        print()

        # --- Step 5: Create prevention index ---
        if args.skip_index:
            print("  [5/6] Skipping deduplication index (--skip-index)")
        else:
            print("  [5/6] Creating deduplication prevention index...")
            index_created = create_dedup_index(conn, dry_run=args.dry_run)
            if index_created and not args.dry_run:
                print("        Created unique index: idx_reviews_text_location_unique")
            print()

        # --- Step 6: Post-cleanup stats ---
        print("  [6/6] Gathering post-cleanup statistics...")
        if not args.dry_run:
            post_stats = get_review_stats(conn)
        else:
            # Estimate post stats for dry run
            post_stats = dict(pre_stats)
            estimated_removed = dup_deleted + orphan_deleted + short_deleted
            post_stats["total"] = pre_stats["total"] - estimated_removed

        elapsed = time.time() - start_time
        total_deleted = dup_deleted + orphan_deleted + short_deleted

        print()
        print("=" * 70)
        if args.dry_run:
            print("  DRY RUN COMPLETE - No changes made")
        else:
            print("  CLEANUP COMPLETE")
        print("=" * 70)
        print()
        print("  Summary:")
        print("    Duplicates removed:    %s" % "{:,}".format(dup_deleted))
        print("    Orphans removed:       %s" % "{:,}".format(orphan_deleted))
        print("    Short reviews removed: %s" % "{:,}".format(short_deleted))
        print("    Total removed:         %s" % "{:,}".format(total_deleted))
        print()
        print("  Before: %s reviews" % "{:,}".format(pre_stats["total"]))
        print("  After:  %s reviews" % "{:,}".format(post_stats["total"]))
        print("  Runtime: %.1fs" % elapsed)
        print()

        if not args.dry_run:
            print("  Post-cleanup quality:")
            print("    With sentiment:    %s / %s (%.1f%%)" % (
                "{:,}".format(post_stats["with_sentiment"]),
                "{:,}".format(post_stats["total"]),
                post_stats["with_sentiment"] / post_stats["total"] * 100 if post_stats["total"] > 0 else 0
            ))
            print("    With rating:       %s / %s (%.1f%%)" % (
                "{:,}".format(post_stats["with_rating"]),
                "{:,}".format(post_stats["total"]),
                post_stats["with_rating"] / post_stats["total"] * 100 if post_stats["total"] > 0 else 0
            ))
            print("    With text (>=3):   %s / %s (%.1f%%)" % (
                "{:,}".format(post_stats["with_meaningful_text"]),
                "{:,}".format(post_stats["total"]),
                post_stats["with_meaningful_text"] / post_stats["total"] * 100 if post_stats["total"] > 0 else 0
            ))
            print("    With location_id:  %s / %s (%.1f%%)" % (
                "{:,}".format(post_stats["with_location"]),
                "{:,}".format(post_stats["total"]),
                post_stats["with_location"] / post_stats["total"] * 100 if post_stats["total"] > 0 else 0
            ))
            print("    Avg rating:        %s" % post_stats["avg_rating"])
            print("    Avg sentiment:     %s" % post_stats["avg_sentiment"])
        print("=" * 70)

    finally:
        return_connection(conn)


if __name__ == "__main__":
    main()
