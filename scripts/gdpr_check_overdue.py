#!/usr/bin/env python3
"""
GDPR Overdue Requests Check Script
ReviewSignal 5.0

Cron job to check for overdue GDPR requests and send alerts.
Schedule: 0 9 * * * (daily at 9:00 AM)

Usage:
    python scripts/gdpr_check_overdue.py [--alert-email email@example.com]
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

logger = structlog.get_logger("gdpr.check_overdue")


def check_overdue_requests(alert_email: str = None) -> dict:
    """
    Check for overdue GDPR requests.

    Args:
        alert_email: Email address to send alerts to

    Returns:
        Dict with check results
    """
    logger.info("overdue_check_started")

    # Create database session
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Initialize GDPR service
        gdpr_service = GDPRService(session)

        # Get overdue requests
        overdue = gdpr_service.get_overdue_requests()
        pending = gdpr_service.get_pending_requests()

        # Calculate urgency levels
        critical = []  # More than 30 days overdue
        warning = []   # 1-30 days overdue
        approaching = []  # Less than 7 days remaining

        for req in overdue:
            days_overdue = -req.get("days_remaining", 0)
            if days_overdue > 30:
                critical.append(req)
            else:
                warning.append(req)

        for req in pending:
            if not req.get("is_overdue") and req.get("days_remaining", 30) < 7:
                approaching.append(req)

        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_overdue": len(overdue),
            "total_pending": len(pending),
            "critical_count": len(critical),
            "warning_count": len(warning),
            "approaching_deadline_count": len(approaching),
            "critical_requests": critical,
            "warning_requests": warning,
            "approaching_requests": approaching
        }

        logger.info(
            "overdue_check_completed",
            total_overdue=len(overdue),
            critical=len(critical),
            warning=len(warning),
            approaching=len(approaching)
        )

        # Send alert if there are overdue requests and email is provided
        if overdue and alert_email:
            send_alert(alert_email, results)

        return results

    except Exception as e:
        logger.error("overdue_check_failed", error=str(e))
        raise

    finally:
        session.close()


def send_alert(email: str, results: dict) -> None:
    """
    Send alert email about overdue requests.

    Args:
        email: Recipient email
        results: Check results
    """
    # In production, this would send an actual email
    # For now, just log the alert
    logger.warning(
        "overdue_alert_triggered",
        recipient=email,
        critical=results["critical_count"],
        warning=results["warning_count"]
    )

    # TODO: Implement actual email sending
    # Could use SendGrid, AWS SES, or similar
    print(f"\n*** ALERT: Email would be sent to {email} ***")
    print(f"    Critical: {results['critical_count']} overdue requests")
    print(f"    Warning: {results['warning_count']} overdue requests")
    print(f"    Approaching: {results['approaching_deadline_count']} requests nearing deadline")


def main():
    parser = argparse.ArgumentParser(
        description="GDPR Overdue Requests Check Script"
    )
    parser.add_argument(
        "--alert-email",
        type=str,
        help="Email address for alerts"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only output if there are issues"
    )

    args = parser.parse_args()

    if not args.quiet:
        print("=" * 60)
        print("GDPR OVERDUE REQUESTS CHECK")
        print(f"Time: {datetime.utcnow().isoformat()}")
        print("=" * 60)

    try:
        results = check_overdue_requests(alert_email=args.alert_email)

        if args.quiet and results["total_overdue"] == 0:
            # Quiet mode and no issues - exit silently
            sys.exit(0)

        # Print summary
        print("\nGDPR Compliance Status:")
        print("-" * 40)

        # Status indicator
        if results["critical_count"] > 0:
            status = "CRITICAL"
            status_emoji = "!!"
        elif results["warning_count"] > 0:
            status = "WARNING"
            status_emoji = "!"
        elif results["approaching_deadline_count"] > 0:
            status = "ATTENTION"
            status_emoji = "?"
        else:
            status = "OK"
            status_emoji = "ok"

        print(f"\n  Status: [{status_emoji}] {status}")
        print(f"\n  Pending requests: {results['total_pending']}")
        print(f"  Overdue requests: {results['total_overdue']}")

        if results["critical_count"] > 0:
            print(f"\n  CRITICAL ({results['critical_count']}):")
            for req in results["critical_requests"]:
                print(f"    - ID {req['request_id']}: {req['subject_email']} ({req['request_type']})")
                print(f"      Deadline: {req['deadline_at']}, Days overdue: {-req['days_remaining']}")

        if results["warning_count"] > 0:
            print(f"\n  WARNING ({results['warning_count']}):")
            for req in results["warning_requests"]:
                print(f"    - ID {req['request_id']}: {req['subject_email']} ({req['request_type']})")
                print(f"      Deadline: {req['deadline_at']}, Days overdue: {-req['days_remaining']}")

        if results["approaching_deadline_count"] > 0:
            print(f"\n  APPROACHING DEADLINE ({results['approaching_deadline_count']}):")
            for req in results["approaching_requests"]:
                print(f"    - ID {req['request_id']}: {req['subject_email']} ({req['request_type']})")
                print(f"      Deadline: {req['deadline_at']}, Days remaining: {req['days_remaining']}")

        print("\n" + "=" * 60)

        # Exit with appropriate code
        if results["critical_count"] > 0:
            sys.exit(2)  # Critical issues
        elif results["warning_count"] > 0:
            sys.exit(1)  # Warnings
        else:
            sys.exit(0)  # All OK

    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(3)


if __name__ == "__main__":
    main()
