#!/usr/bin/env python3
"""
GDPR Retention Cleanup Script
ReviewSignal 5.0

Cron job to automatically clean up data based on retention policies.
Schedule: 0 2 * * * (daily at 2:00 AM)

Usage:
    python scripts/gdpr_retention_cleanup.py [--dry-run]
"""

import sys
import os
import argparse
import structlog
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from compliance.gdpr import GDPRService
from compliance.gdpr.consent_manager import ConsentManager

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("gdpr.retention_cleanup")


def run_cleanup(dry_run: bool = False) -> dict:
    """
    Run retention cleanup for all configured policies.

    Args:
        dry_run: If True, only preview what would be cleaned

    Returns:
        Dict with cleanup results
    """
    logger.info("retention_cleanup_started", dry_run=dry_run)

    # Create database session
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Initialize GDPR service
        gdpr_service = GDPRService(session)

        # Run retention cleanup
        results = gdpr_service.run_retention_cleanup(dry_run=dry_run)

        # Also expire old consents
        consent_manager = ConsentManager(session)
        expired_consents = consent_manager.expire_old_consents()
        results["expired_consents"] = expired_consents

        logger.info(
            "retention_cleanup_completed",
            dry_run=dry_run,
            total_affected=results["total_affected"],
            expired_consents=expired_consents,
            tables=list(results["tables"].keys()),
            errors=results.get("errors", [])
        )

        return results

    except Exception as e:
        logger.error("retention_cleanup_failed", error=str(e))
        raise

    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description="GDPR Retention Cleanup Script"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be cleaned without actually deleting"
    )
    parser.add_argument(
        "--table",
        type=str,
        help="Clean specific table only"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("GDPR RETENTION CLEANUP")
    print(f"Time: {datetime.utcnow().isoformat()}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("=" * 60)

    try:
        results = run_cleanup(dry_run=args.dry_run)

        print("\nResults:")
        print(f"  Total affected: {results['total_affected']}")
        print(f"  Expired consents: {results.get('expired_consents', 0)}")

        if results.get("tables"):
            print("\n  Tables processed:")
            for table, info in results["tables"].items():
                action = info.get("action", "unknown")
                count = info.get("count", 0)
                print(f"    - {table}: {count} records ({action})")

        if results.get("errors"):
            print("\n  Errors:")
            for error in results["errors"]:
                print(f"    - {error}")

        print("\n" + "=" * 60)
        print("Cleanup completed successfully")
        print("=" * 60)

    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
