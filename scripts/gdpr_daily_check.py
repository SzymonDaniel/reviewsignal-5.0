#!/usr/bin/env python3
"""
GDPR Daily Check Script
ReviewSignal 5.0

Daily scheduled tasks for GDPR compliance:
- Check for overdue requests and send alerts
- Send consent expiry notifications
- Expire old processing restrictions
- Clean up old webhook logs

Schedule: Run daily at 09:00 UTC via cron:
0 9 * * * /home/info_betsim/reviewsignal-5.0/venv/bin/python /home/info_betsim/reviewsignal-5.0/scripts/gdpr_daily_check.py >> /var/log/reviewsignal/gdpr_daily.log 2>&1
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, '/home/info_betsim/reviewsignal-5.0')

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from compliance.gdpr import (
    GDPRService,
    ProcessingRestrictionManager
)

# Setup logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger("gdpr.daily_check")


def main():
    """Run daily GDPR compliance checks."""
    start_time = datetime.utcnow()
    logger.info("gdpr_daily_check_started")

    # Create database session
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()

    try:
        service = GDPRService(session)
        restriction_manager = ProcessingRestrictionManager(session)

        results = {
            "started_at": start_time.isoformat(),
            "tasks": {}
        }

        # 1. Check for overdue requests
        logger.info("checking_overdue_requests")
        overdue_result = service.send_overdue_alerts()
        results["tasks"]["overdue_alerts"] = overdue_result
        logger.info("overdue_check_complete", **overdue_result)

        # 2. Send consent expiry notifications (30 days before)
        logger.info("sending_consent_expiry_notifications")
        expiry_result = service.send_consent_expiry_notifications(days_before=30)
        results["tasks"]["consent_expiry_notifications"] = expiry_result
        logger.info("consent_expiry_complete", **expiry_result)

        # 3. Expire old processing restrictions
        logger.info("expiring_old_restrictions")
        expired_count = restriction_manager.expire_old_restrictions()
        results["tasks"]["restrictions_expired"] = expired_count
        logger.info("restrictions_expired", count=expired_count)

        # 4. Expire old consents
        logger.info("expiring_old_consents")
        expired_consents = service.consent_manager.expire_old_consents()
        results["tasks"]["consents_expired"] = expired_consents
        logger.info("consents_expired", count=expired_consents)

        # 5. Clean up old webhook logs (keep 90 days)
        logger.info("cleaning_webhook_logs")
        cleanup_result = session.execute(text("""
            DELETE FROM gdpr_webhook_logs
            WHERE created_at < NOW() - INTERVAL '90 days'
        """))
        deleted_logs = cleanup_result.rowcount
        session.commit()
        results["tasks"]["webhook_logs_cleaned"] = deleted_logs
        logger.info("webhook_logs_cleaned", deleted=deleted_logs)

        # Summary
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        results["completed_at"] = end_time.isoformat()
        results["duration_seconds"] = duration

        logger.info(
            "gdpr_daily_check_completed",
            duration_seconds=duration,
            **{f"task_{k}": v for k, v in results["tasks"].items()}
        )

        print(f"""
================================================================================
GDPR Daily Check Complete
================================================================================
Started:    {results['started_at']}
Completed:  {results['completed_at']}
Duration:   {results['duration_seconds']:.2f} seconds

Results:
- Overdue alerts sent: {results['tasks']['overdue_alerts'].get('notification_sent', False)}
- Overdue requests: {results['tasks']['overdue_alerts'].get('overdue_count', 0)}
- Consent expiry notifications: {results['tasks']['consent_expiry_notifications'].get('notifications_sent', 0)}
- Processing restrictions expired: {results['tasks']['restrictions_expired']}
- Consents expired: {results['tasks']['consents_expired']}
- Webhook logs cleaned: {results['tasks']['webhook_logs_cleaned']}
================================================================================
""")

    except Exception as e:
        logger.error("gdpr_daily_check_failed", error=str(e))
        print(f"ERROR: {e}")
        raise

    finally:
        session.close()


if __name__ == "__main__":
    main()
