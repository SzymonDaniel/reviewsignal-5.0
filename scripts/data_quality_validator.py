#!/usr/bin/env python3
"""
Data quality validator for locations table.

Checks ALL locations for completeness, assigns a quality score (0-100),
updates the data_quality_score column, and reports distribution.

Scoring weights:
  - has_name:      15 points
  - has_place_id:  10 points
  - has_country:   15 points
  - has_city:      10 points
  - has_chain_id:  10 points
  - has_lat_lng:   15 points
  - has_rating:    15 points
  - has_reviews:   10 points
  Total: 100

Uses modules/db.py shared connection pool.
"""

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from modules.db import get_connection, return_connection

# Scoring weights
WEIGHTS = {
    "has_name": 15,
    "has_place_id": 10,
    "has_country": 15,
    "has_city": 10,
    "has_chain_id": 10,
    "has_lat_lng": 15,
    "has_rating": 15,
    "has_reviews": 10,
}


def compute_and_update_scores(conn) -> dict:
    """Compute quality scores for all locations and update DB. Returns stats."""
    cur = conn.cursor()

    print("Computing data quality scores for all locations...")
    # Single SQL UPDATE using CASE expressions for each field
    cur.execute(f"""
        UPDATE locations SET data_quality_score = (
            CASE WHEN name IS NOT NULL AND length(name) > 0 THEN {WEIGHTS['has_name']} ELSE 0 END
          + CASE WHEN place_id IS NOT NULL AND length(place_id) > 0 THEN {WEIGHTS['has_place_id']} ELSE 0 END
          + CASE WHEN country IS NOT NULL AND length(country) > 0 THEN {WEIGHTS['has_country']} ELSE 0 END
          + CASE WHEN city IS NOT NULL AND length(city) > 0 THEN {WEIGHTS['has_city']} ELSE 0 END
          + CASE WHEN chain_id IS NOT NULL THEN {WEIGHTS['has_chain_id']} ELSE 0 END
          + CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN {WEIGHTS['has_lat_lng']} ELSE 0 END
          + CASE WHEN rating IS NOT NULL THEN {WEIGHTS['has_rating']} ELSE 0 END
          + CASE WHEN review_count IS NOT NULL AND review_count > 0 THEN {WEIGHTS['has_reviews']} ELSE 0 END
        )
    """)
    updated = cur.rowcount
    conn.commit()
    print(f"  Updated {updated} rows.")
    cur.close()
    return {"updated": updated}


def report_distribution(conn):
    """Report score distribution and field-level completeness."""
    cur = conn.cursor()

    # Overall stats
    cur.execute("SELECT COUNT(*) FROM locations")
    total = cur.fetchone()[0]

    cur.execute("""
        SELECT
            MIN(data_quality_score) as min_score,
            MAX(data_quality_score) as max_score,
            ROUND(AVG(data_quality_score)::numeric, 1) as avg_score,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY data_quality_score) as median_score
        FROM locations
    """)
    row = cur.fetchone()
    min_s, max_s, avg_s, med_s = row

    print("\n" + "=" * 70)
    print("DATA QUALITY SCORE DISTRIBUTION")
    print("=" * 70)
    print(f"  Total locations: {total}")
    print(f"  Min score:       {min_s}")
    print(f"  Max score:       {max_s}")
    print(f"  Average score:   {avg_s}")
    print(f"  Median score:    {med_s}")

    # Score bucket distribution
    print(f"\n  {'Score Range':>15s}  {'Count':>8s}  {'Percent':>8s}  Bar")
    print(f"  {'-'*15}  {'-'*8}  {'-'*8}  {'-'*40}")

    cur.execute("""
        SELECT
            CASE
                WHEN data_quality_score >= 90 THEN '90-100 (A+)'
                WHEN data_quality_score >= 80 THEN '80-89  (A)'
                WHEN data_quality_score >= 70 THEN '70-79  (B)'
                WHEN data_quality_score >= 60 THEN '60-69  (C)'
                WHEN data_quality_score >= 50 THEN '50-59  (D)'
                WHEN data_quality_score >= 40 THEN '40-49  (E)'
                ELSE '0-39   (F)'
            END as bucket,
            COUNT(*) as cnt,
            CASE
                WHEN data_quality_score >= 90 THEN 7
                WHEN data_quality_score >= 80 THEN 6
                WHEN data_quality_score >= 70 THEN 5
                WHEN data_quality_score >= 60 THEN 4
                WHEN data_quality_score >= 50 THEN 3
                WHEN data_quality_score >= 40 THEN 2
                ELSE 1
            END as sort_order
        FROM locations
        GROUP BY bucket, sort_order
        ORDER BY sort_order DESC
    """)
    for bucket, cnt, _ in cur.fetchall():
        pct = cnt / total * 100 if total else 0
        bar_len = int(pct / 2.5)  # scale: 100% = 40 chars
        bar = "#" * bar_len
        print(f"  {bucket:>15s}  {cnt:>8d}  {pct:>7.1f}%  {bar}")

    # Field-level completeness
    print(f"\n  {'Field':>15s}  {'Filled':>8s}  {'Missing':>8s}  {'Pct':>7s}")
    print(f"  {'-'*15}  {'-'*8}  {'-'*8}  {'-'*7}")

    cur.execute("""
        SELECT
            COUNT(CASE WHEN name IS NOT NULL AND length(name) > 0 THEN 1 END) as has_name,
            COUNT(CASE WHEN place_id IS NOT NULL AND length(place_id) > 0 THEN 1 END) as has_place_id,
            COUNT(CASE WHEN country IS NOT NULL AND length(country) > 0 THEN 1 END) as has_country,
            COUNT(CASE WHEN city IS NOT NULL AND length(city) > 0 THEN 1 END) as has_city,
            COUNT(CASE WHEN chain_id IS NOT NULL THEN 1 END) as has_chain_id,
            COUNT(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 END) as has_lat_lng,
            COUNT(CASE WHEN rating IS NOT NULL THEN 1 END) as has_rating,
            COUNT(CASE WHEN review_count IS NOT NULL AND review_count > 0 THEN 1 END) as has_reviews
        FROM locations
    """)
    row = cur.fetchone()
    fields = ["name", "place_id", "country", "city", "chain_id", "lat_lng", "rating", "reviews"]
    for i, field in enumerate(fields):
        filled = row[i]
        missing = total - filled
        pct = filled / total * 100 if total else 0
        print(f"  {field:>15s}  {filled:>8d}  {missing:>8d}  {pct:>6.1f}%")

    # Quality grade summary
    cur.execute("""
        SELECT
            COUNT(CASE WHEN data_quality_score >= 70 THEN 1 END) as good,
            COUNT(CASE WHEN data_quality_score >= 50 AND data_quality_score < 70 THEN 1 END) as acceptable,
            COUNT(CASE WHEN data_quality_score < 50 THEN 1 END) as poor
        FROM locations
    """)
    good, acceptable, poor = cur.fetchone()
    print(f"\n  Quality Summary:")
    print(f"    GOOD (70+):       {good:>6d} ({good/total*100:5.1f}%)")
    print(f"    ACCEPTABLE (50+): {acceptable:>6d} ({acceptable/total*100:5.1f}%)")
    print(f"    POOR (<50):       {poor:>6d} ({poor/total*100:5.1f}%)")

    # Worst offenders: locations with score < 30
    print(f"\n  Sample of lowest-quality locations (score < 30):")
    cur.execute("""
        SELECT id, name, data_quality_score, country, city, rating
        FROM locations
        WHERE data_quality_score < 30
        ORDER BY data_quality_score, id
        LIMIT 10
    """)
    for loc_id, name, score, country, city, rating in cur.fetchall():
        print(f"    ID {loc_id}: score={score}, name='{name}', country='{country or ''}', city='{city or ''}', rating={rating}")

    cur.close()


def main():
    start = time.time()
    print("=" * 70)
    print("DATA QUALITY VALIDATOR")
    print("=" * 70)

    conn = get_connection()
    try:
        compute_and_update_scores(conn)
        report_distribution(conn)

        elapsed = time.time() - start
        print(f"\nCompleted in {elapsed:.1f} seconds.")
    finally:
        return_connection(conn)


if __name__ == "__main__":
    main()
