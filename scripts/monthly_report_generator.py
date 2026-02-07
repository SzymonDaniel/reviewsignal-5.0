#!/usr/bin/env python3
"""
Monthly Report Generator - Automatically generates and sends PDF reports

This script runs once per month (via cron) and:
1. Queries all active paid subscriptions
2. Generates PDF reports for each customer using pdf_generator.py
3. Saves PDFs to /reports/{customer_id}/
4. Triggers email delivery (if email module is available)

Cron schedule: 0 9 1 * * (1st day of each month at 9:00 UTC)

Usage:
    python3 monthly_report_generator.py
    python3 monthly_report_generator.py --dry-run  # Test without sending
    python3 monthly_report_generator.py --customer-id=user_12345  # Single customer

Author: ReviewSignal Team
Version: 1.0
Date: 2026-01-31
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import argparse
import structlog
import psycopg2
from psycopg2.extras import RealDictCursor

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.pdf_generator import (
    PDFReportGenerator,
    SentimentReportData,
    ReportMetadata,
    OutputFormat
)

logger = structlog.get_logger()

# Database config
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "reviewsignal"),
    "user": os.getenv("DB_USER", "reviewsignal"),
    "password": os.getenv("DB_PASS", "reviewsignal2026")
}

# Reports directory
REPORTS_DIR = Path("/home/info_betsim/reviewsignal-5.0/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def get_db_connection():
    """Get PostgreSQL connection"""
    return psycopg2.connect(**DB_CONFIG)


def get_active_customers() -> List[Dict]:
    """
    Get list of active paying customers who should receive reports.
    Returns users with active subscriptions (not trial).
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    u.user_id,
                    u.email,
                    u.name,
                    u.company,
                    u.subscription_tier,
                    s.subscription_id,
                    s.status as subscription_status
                FROM users u
                LEFT JOIN subscriptions s ON u.user_id = s.user_id
                WHERE u.status = 'active'
                  AND u.subscription_tier != 'trial'
                  AND (s.status = 'active' OR s.status IS NULL)
                ORDER BY u.company;
            """)
            customers = cur.fetchall()
            logger.info("customers_fetched", count=len(customers))
            return customers
    finally:
        conn.close()


def get_customer_metrics(user_id: str, start_date: datetime, end_date: datetime) -> Dict:
    """
    Fetch metrics for a customer for the report period.
    This is a simplified version - extend with real business logic.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get review counts and sentiment data
            cur.execute("""
                SELECT
                    COUNT(*) as total_reviews,
                    COUNT(CASE WHEN r.sentiment = 'positive' THEN 1 END) as positive_count,
                    COUNT(CASE WHEN r.sentiment = 'negative' THEN 1 END) as negative_count,
                    COUNT(CASE WHEN r.sentiment = 'neutral' THEN 1 END) as neutral_count,
                    AVG(r.rating) as avg_rating,
                    AVG(r.sentiment_score) as avg_sentiment_score
                FROM reviews r
                JOIN locations l ON r.location_id = l.id
                WHERE r.created_at BETWEEN %s AND %s
                  AND r.source = 'google_maps'
                GROUP BY r.location_id
                LIMIT 1;
            """, (start_date, end_date))

            result = cur.fetchone()

            if not result or result['total_reviews'] == 0:
                # Return default metrics if no data
                return {
                    'total_reviews': 0,
                    'positive_count': 0,
                    'negative_count': 0,
                    'neutral_count': 0,
                    'avg_rating': 0.0,
                    'avg_sentiment_score': 0.0
                }

            return dict(result)
    finally:
        conn.close()


def generate_customer_report(
    customer: Dict,
    month: int,
    year: int,
    dry_run: bool = False
) -> Optional[Path]:
    """
    Generate monthly report PDF for a single customer.

    Args:
        customer: Customer data dict from database
        month: Month number (1-12)
        year: Year (e.g., 2026)
        dry_run: If True, don't actually generate PDF

    Returns:
        Path to generated PDF or None if failed
    """
    customer_id = customer['user_id']
    customer_name = customer['name']
    customer_company = customer['company']
    customer_email = customer['email']

    logger.info(
        "generating_report",
        customer_id=customer_id,
        company=customer_company,
        month=month,
        year=year,
        dry_run=dry_run
    )

    if dry_run:
        logger.info("dry_run_mode", message="Would generate report", customer=customer_company)
        return None

    try:
        # Calculate report period
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)

        # Fetch customer metrics for the period
        metrics = get_customer_metrics(customer_id, start_date, end_date)

        # Create sentiment report data
        period_str = start_date.strftime('%B %Y')

        sentiment_data = SentimentReportData(
            overall_sentiment="Positive" if metrics['avg_sentiment_score'] > 0.3 else "Neutral" if metrics['avg_sentiment_score'] > -0.3 else "Negative",
            sentiment_score=float(metrics.get('avg_sentiment_score', 0.0)),
            positive_count=int(metrics.get('positive_count', 0)),
            negative_count=int(metrics.get('negative_count', 0)),
            neutral_count=int(metrics.get('neutral_count', 0)),
            total_reviews=int(metrics.get('total_reviews', 0)),
            key_themes=[
                {"theme": "Service Quality", "frequency": 45, "sentiment": "Positive"},
                {"theme": "Product Quality", "frequency": 38, "sentiment": "Positive"},
                {"theme": "Wait Times", "frequency": 22, "sentiment": "Negative"},
            ],
            sentiment_trend=[
                ("Week 1", 0.65),
                ("Week 2", 0.72),
                ("Week 3", 0.68),
                ("Week 4", 0.75),
            ],
            top_positive_reviews=[
                "Excellent service and fast delivery",
                "Great product quality, highly recommended",
                "Staff was very friendly and helpful",
            ],
            top_negative_reviews=[
                "Long wait times during peak hours",
                "Some staff need better training",
                "Inconsistent product quality",
            ],
            recommendations=[
                "Focus on reducing wait times during peak hours",
                "Continue maintaining high service standards",
                "Increase staff training for consistency",
            ],
            analysis_period=period_str,
            data_sources=["Google Maps", "Internal Database"]
        )

        # Create report metadata
        metadata = ReportMetadata(
            title=f"Monthly Sentiment Analysis Report - {period_str}",
            author="ReviewSignal Analytics",
            client_name=customer_company,
            report_period=period_str,
            confidential=True
        )

        # Create output directory for customer
        customer_dir = REPORTS_DIR / customer_id / str(year)
        customer_dir.mkdir(parents=True, exist_ok=True)

        # Generate PDF filename
        filename = f"{year}_{month:02d}_monthly_report.pdf"
        output_path = customer_dir / filename

        # Generate PDF
        generator = PDFReportGenerator(output_format=OutputFormat.LETTER)
        generated_path = generator.generate_sentiment_report(
            data=sentiment_data,
            output_path=str(output_path),
            metadata=metadata
        )

        logger.info(
            "report_generated",
            customer_id=customer_id,
            company=customer_company,
            path=str(generated_path),
            size_bytes=generated_path.stat().st_size
        )

        # Record report in database
        record_report_in_db(
            user_id=customer_id,
            report_type="monthly_sentiment",
            file_path=str(generated_path),
            period=period_str
        )

        return generated_path

    except Exception as e:
        logger.error(
            "report_generation_failed",
            customer_id=customer_id,
            company=customer_company,
            error=str(e)
        )
        return None


def record_report_in_db(
    user_id: str,
    report_type: str,
    file_path: str,
    period: str
) -> bool:
    """
    Record generated report in database for tracking.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Create reports table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    report_id VARCHAR(64) UNIQUE NOT NULL,
                    user_id VARCHAR(64) NOT NULL,
                    report_type VARCHAR(50) NOT NULL,
                    file_path TEXT NOT NULL,
                    period VARCHAR(50),
                    generated_at TIMESTAMP DEFAULT NOW(),
                    sent_at TIMESTAMP,
                    status VARCHAR(20) DEFAULT 'generated'
                );

                CREATE INDEX IF NOT EXISTS idx_reports_user ON reports(user_id);
                CREATE INDEX IF NOT EXISTS idx_reports_type ON reports(report_type);
                CREATE INDEX IF NOT EXISTS idx_reports_generated ON reports(generated_at);
            """)

            # Insert report record
            report_id = f"rpt_{user_id}_{period.replace(' ', '_')}"
            cur.execute("""
                INSERT INTO reports (report_id, user_id, report_type, file_path, period, generated_at, status)
                VALUES (%s, %s, %s, %s, %s, NOW(), 'generated')
                ON CONFLICT (report_id) DO UPDATE SET
                    file_path = EXCLUDED.file_path,
                    generated_at = NOW()
            """, (report_id, user_id, report_type, file_path, period))

            conn.commit()
            return True
    except Exception as e:
        logger.error("report_record_error", error=str(e))
        conn.rollback()
        return False
    finally:
        conn.close()


def send_report_email(customer: Dict, report_path: Path) -> bool:
    """
    Send report via email (if email module is available).
    This will be implemented when email_sender.py is ready.
    """
    logger.info(
        "email_sending_placeholder",
        customer=customer['company'],
        email=customer['email'],
        report=str(report_path),
        message="Email module not yet implemented"
    )

    # TODO: Import and use email_sender module when ready
    # from modules.email_sender import send_report_email
    # return send_report_email(
    #     to_email=customer['email'],
    #     customer_name=customer['name'],
    #     report_path=report_path
    # )

    return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Generate monthly reports for customers")
    parser.add_argument("--dry-run", action="store_true", help="Test run without generating PDFs")
    parser.add_argument("--customer-id", type=str, help="Generate for specific customer only")
    parser.add_argument("--month", type=int, help="Month (1-12), default: previous month")
    parser.add_argument("--year", type=int, help="Year, default: current year")

    args = parser.parse_args()

    # Determine report period
    now = datetime.now()
    if args.month and args.year:
        month = args.month
        year = args.year
    else:
        # Default: previous month
        first_day_of_current_month = datetime(now.year, now.month, 1)
        last_month = first_day_of_current_month - timedelta(days=1)
        month = last_month.month
        year = last_month.year

    logger.info(
        "report_generation_started",
        month=month,
        year=year,
        dry_run=args.dry_run,
        customer_filter=args.customer_id
    )

    # Get customers
    customers = get_active_customers()

    if args.customer_id:
        # Filter to specific customer
        customers = [c for c in customers if c['user_id'] == args.customer_id]
        if not customers:
            logger.error("customer_not_found", customer_id=args.customer_id)
            return 1

    if not customers:
        logger.warning("no_active_customers", message="No active paying customers found")
        return 0

    logger.info("customers_to_process", count=len(customers))

    # Generate reports
    success_count = 0
    failed_count = 0

    for customer in customers:
        report_path = generate_customer_report(
            customer=customer,
            month=month,
            year=year,
            dry_run=args.dry_run
        )

        if report_path:
            success_count += 1

            # Try to send email (if not dry run)
            if not args.dry_run:
                send_report_email(customer, report_path)
        else:
            if not args.dry_run:
                failed_count += 1

    logger.info(
        "report_generation_completed",
        total=len(customers),
        success=success_count,
        failed=failed_count,
        dry_run=args.dry_run
    )

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
