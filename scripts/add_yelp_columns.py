#!/usr/bin/env python3
"""
Migration script: Add yelp_business_id column to locations table.

Adds:
- yelp_business_id VARCHAR(200) -- Yelp Fusion API business ID
- Index on yelp_business_id for fast lookups

Usage:
    python3 scripts/add_yelp_columns.py
"""

import os
import sys

# Add project root to path for standalone script execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from modules.db import get_connection, return_connection


def run_migration():
    """Add yelp_business_id column to locations table."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Check if column already exists
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'locations' AND column_name = 'yelp_business_id'
            """)
            if cur.fetchone():
                print("Column 'yelp_business_id' already exists in locations table. Skipping.")
                return

            # Add yelp_business_id column
            print("Adding 'yelp_business_id' column to locations table...")
            cur.execute("""
                ALTER TABLE locations
                ADD COLUMN yelp_business_id VARCHAR(200)
            """)

            # Add index for fast lookups
            print("Creating index on yelp_business_id...")
            cur.execute("""
                CREATE INDEX idx_locations_yelp_business_id
                ON locations(yelp_business_id)
                WHERE yelp_business_id IS NOT NULL
            """)

            conn.commit()
            print("Migration complete: yelp_business_id column added to locations table.")

            # Verify the new column
            cur.execute("""
                SELECT column_name, data_type, character_maximum_length, column_default
                FROM information_schema.columns
                WHERE table_name = 'locations' AND column_name = 'yelp_business_id'
            """)
            row = cur.fetchone()
            if row:
                print(f"  Column: {row[0]}, Type: {row[1]}, Max Length: {row[2]}, Default: {row[3]}")

            # Show index
            cur.execute("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'locations' AND indexname = 'idx_locations_yelp_business_id'
            """)
            idx = cur.fetchone()
            if idx:
                print(f"  Index: {idx[0]}")
                print(f"  Definition: {idx[1]}")

            # Show current locations count
            cur.execute("SELECT COUNT(*) FROM locations")
            total = cur.fetchone()[0]
            print(f"\n  Total locations in table: {total}")
            print("  All locations have yelp_business_id = NULL (to be populated by YelpScraper)")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        return_connection(conn)


if __name__ == "__main__":
    run_migration()
