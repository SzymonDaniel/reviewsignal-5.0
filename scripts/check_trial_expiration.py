#!/usr/bin/env python3
"""
Trial Expiration Checker - Sends warning emails to users with expiring trials

Queries the database for users with trial subscriptions and sends:
- 3-day warning email (tier recommendation included)
- 1-day urgent warning email

Cron schedule: 0 10 * * * (daily at 10:00 UTC)
    venv/bin/python scripts/check_trial_expiration.py

Author: ReviewSignal Team
Version: 1.0
Date: 2026-02-07
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

import structlog
import psycopg2
from psycopg2.extras import RealDictCursor

from modules.email_sender import EmailSender

logger = structlog.get_logger()

# Database config
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "reviewsignal"),
    "user": os.getenv("DB_USER", "reviewsignal"),
    "password": os.getenv("DB_PASS")
}


def get_db_connection():
    """Get PostgreSQL connection."""
    if not DB_CONFIG["password"]:
        raise RuntimeError("DB_PASS environment variable is not set")
    return psycopg2.connect(**DB_CONFIG)


def get_expiring_trials(days_remaining: int) -> list:
    """
    Get users whose trial subscriptions expire in exactly days_remaining days.

    Args:
        days_remaining: Number of days until trial expires (1 or 3)

    Returns:
        List of dicts with user_id, email, name, company, trial_end_date
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            target_date = datetime.now().date() + timedelta(days=days_remaining)
            cur.execute("""
                SELECT
                    u.user_id,
                    u.email,
                    u.name,
                    u.company,
                    s.current_period_end as trial_end_date,
                    s.subscription_id
                FROM users u
                JOIN subscriptions s ON u.user_id = s.user_id
                WHERE u.subscription_tier = 'trial'
                  AND s.status = 'active'
                  AND s.current_period_end::date = %s
                  AND u.email IS NOT NULL
                  AND length(u.email) > 0
                ORDER BY u.company;
            """, (target_date,))
            users = cur.fetchall()
            logger.info(
                "expiring_trials_found",
                days_remaining=days_remaining,
                target_date=str(target_date),
                count=len(users)
            )
            return users
    except psycopg2.errors.UndefinedTable:
        logger.warning("subscriptions_table_missing", message="No subscriptions table yet")
        return []
    except psycopg2.errors.UndefinedColumn as e:
        logger.warning("column_missing", error=str(e))
        return []
    finally:
        conn.close()


def recommend_tier(user: dict) -> str:
    """
    Recommend a subscription tier based on user usage during trial.
    Default recommendation is Starter for most users.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as api_calls
                FROM webhook_events
                WHERE customer_id = %s
                  AND created_at > NOW() - INTERVAL '14 days'
            """, (user.get('user_id', ''),))
            row = cur.fetchone()
            if row and row[0] > 500:
                return "Enterprise"
            elif row and row[0] > 100:
                return "Pro"
            else:
                return "Starter"
    except Exception:
        return "Starter"
    finally:
        conn.close()


def log_email_sent(user_id: str, email_type: str, days_remaining: int):
    """Log that a trial ending email was sent (to avoid duplicates)."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS email_log (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    email_type VARCHAR(50) NOT NULL,
                    metadata JSONB,
                    sent_at TIMESTAMP DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_email_log_user ON email_log(user_id);
                CREATE INDEX IF NOT EXISTS idx_email_log_type ON email_log(email_type);
            """)
            cur.execute("""
                INSERT INTO email_log (user_id, email_type, metadata)
                VALUES (%s, %s, %s)
            """, (
                user_id,
                f'trial_ending_{days_remaining}d',
                '{"days_remaining": ' + str(days_remaining) + '}'
            ))
            conn.commit()
    except Exception as e:
        logger.warning("email_log_error", error=str(e))
        conn.rollback()
    finally:
        conn.close()


def was_email_already_sent(user_id: str, days_remaining: int) -> bool:
    """Check if we already sent this trial ending email today."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM email_log
                WHERE user_id = %s
                  AND email_type = %s
                  AND sent_at::date = CURRENT_DATE
            """, (user_id, f'trial_ending_{days_remaining}d'))
            row = cur.fetchone()
            return row is not None and row[0] > 0
    except Exception:
        return False
    finally:
        conn.close()


def main():
    """Main entry point - check trials expiring in 3 days and 1 day."""
    logger.info("trial_expiration_check_started", timestamp=datetime.now().isoformat())

    sender = EmailSender()
    total_sent = 0
    total_skipped = 0
    total_failed = 0

    for days in [3, 1]:
        users = get_expiring_trials(days)

        for user in users:
            user_id = user['user_id']
            email = user['email']
            name = user.get('name') or 'Valued Customer'

            if was_email_already_sent(user_id, days):
                logger.info("trial_email_already_sent", user_id=user_id, days=days)
                total_skipped += 1
                continue

            tier_rec = recommend_tier(user)

            try:
                result = sender.send_trial_ending_email(
                    customer_email=email,
                    customer_name=name,
                    days_remaining=days,
                    tier_recommendation=tier_rec
                )

                if result.get("success"):
                    log_email_sent(user_id, "trial_ending", days)
                    total_sent += 1
                    logger.info(
                        "trial_ending_email_sent",
                        user_id=user_id,
                        email=email,
                        days_remaining=days,
                        tier_recommendation=tier_rec
                    )
                else:
                    total_failed += 1
                    logger.error(
                        "trial_ending_email_failed",
                        user_id=user_id,
                        error=result.get("error")
                    )

            except Exception as e:
                total_failed += 1
                logger.error(
                    "trial_ending_email_exception",
                    user_id=user_id,
                    error=str(e)
                )

    logger.info(
        "trial_expiration_check_completed",
        total_sent=total_sent,
        total_skipped=total_skipped,
        total_failed=total_failed,
        timestamp=datetime.now().isoformat()
    )

    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
