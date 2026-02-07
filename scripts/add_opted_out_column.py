#!/usr/bin/env python3
"""
Migration script: Add opted_out columns to leads table.

Adds:
- opted_out BOOLEAN DEFAULT FALSE
- opted_out_at TIMESTAMP
- Index on opted_out

Usage:
    python3 scripts/add_opted_out_column.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from modules.db import get_connection, return_connection


def run_migration():
    """Add opted_out and opted_out_at columns to leads table."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Check if column already exists
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'leads' AND column_name = 'opted_out'
            """)
            if cur.fetchone():
                print("Column 'opted_out' already exists in leads table. Skipping.")
                return

            # Add opted_out column
            print("Adding 'opted_out' column to leads table...")
            cur.execute("""
                ALTER TABLE leads
                ADD COLUMN opted_out BOOLEAN DEFAULT FALSE
            """)

            # Add opted_out_at column
            print("Adding 'opted_out_at' column to leads table...")
            cur.execute("""
                ALTER TABLE leads
                ADD COLUMN opted_out_at TIMESTAMP
            """)

            # Add index on opted_out for fast filtering
            print("Creating index on opted_out...")
            cur.execute("""
                CREATE INDEX idx_leads_opted_out ON leads(opted_out)
            """)

            conn.commit()
            print("Migration complete: opted_out + opted_out_at columns added to leads table.")

            # Verify
            cur.execute("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_name = 'leads' AND column_name IN ('opted_out', 'opted_out_at')
                ORDER BY column_name
            """)
            for row in cur.fetchall():
                print(f"  Column: {row[0]}, Type: {row[1]}, Default: {row[2]}")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        return_connection(conn)


if __name__ == "__main__":
    run_migration()
