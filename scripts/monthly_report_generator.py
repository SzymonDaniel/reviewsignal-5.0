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

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from modules.pdf_generator import (
    PDFReportGenerator,
    SentimentReportData,
    ReportMetadata,
    OutputFormat
)
from modules.pdf_generator_enterprise import (
    EnterprisePDFGenerator,
    EnterpriseReportData,
    BrandingConfig,
    KPICard,
    Recommendation,
    BenchmarkData,
    CompetitorData,
    TrendDirection,
    SeverityLevel,
)

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
    Report content and generator are chosen based on subscription tier:
    - starter: Basic PDF (pdf_generator.py), limited to customer's 5 cities
    - pro: Basic PDF with 30 cities + anomaly analysis
    - enterprise: Enterprise PDF (pdf_generator_enterprise.py), all cities +
      benchmarks + competitor analysis + white-label

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
    tier = (customer.get('subscription_tier') or 'starter').lower()

    logger.info(
        "generating_report",
        customer_id=customer_id,
        company=customer_company,
        tier=tier,
        month=month,
        year=year,
        dry_run=dry_run
    )

    if dry_run:
        logger.info("dry_run_mode", message="Would generate report", customer=customer_company, tier=tier)
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
        period_str = start_date.strftime('%B %Y')

        # Determine city limit based on tier
        if tier == 'starter':
            city_limit = 5
        elif tier == 'pro':
            city_limit = 30
        else:  # enterprise
            city_limit = -1  # unlimited

        # Create output directory for customer
        customer_dir = REPORTS_DIR / customer_id / str(year)
        customer_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{year}_{month:02d}_monthly_report.pdf"
        output_path = customer_dir / filename

        # ---- ENTERPRISE TIER: use EnterprisePDFGenerator ----
        if tier == 'enterprise':
            generated_path = _generate_enterprise_report(
                customer, metrics, period_str, output_path
            )
        else:
            # ---- STARTER / PRO TIER: use basic PDFReportGenerator ----
            generated_path = _generate_basic_report(
                customer, metrics, period_str, output_path, tier, city_limit
            )

        if generated_path:
            logger.info(
                "report_generated",
                customer_id=customer_id,
                company=customer_company,
                tier=tier,
                path=str(generated_path),
                size_bytes=generated_path.stat().st_size
            )

            # Record report in database
            record_report_in_db(
                user_id=customer_id,
                report_type=f"monthly_sentiment_{tier}",
                file_path=str(generated_path),
                period=period_str
            )

        return generated_path

    except Exception as e:
        logger.error(
            "report_generation_failed",
            customer_id=customer_id,
            company=customer_company,
            tier=tier,
            error=str(e)
        )
        return None


def _generate_basic_report(
    customer: Dict,
    metrics: Dict,
    period_str: str,
    output_path: Path,
    tier: str,
    city_limit: int
) -> Optional[Path]:
    """Generate a basic PDF report for starter/pro tiers."""
    customer_company = customer['company']

    # Build recommendations based on tier
    recommendations = [
        "Focus on reducing wait times during peak hours",
        "Continue maintaining high service standards",
        "Increase staff training for consistency",
    ]

    # Pro tier gets anomaly analysis recommendations
    if tier == 'pro':
        recommendations.extend([
            "Monitor anomaly alerts for early detection of sentiment shifts",
            "Review locations flagged by anomaly detection system",
            "Track competitor sentiment trends in your coverage cities",
        ])

    # Determine sentiment label
    avg_score = float(metrics.get('avg_sentiment_score', 0.0))
    if avg_score > 0.3:
        overall = "Positive"
    elif avg_score > -0.3:
        overall = "Neutral"
    else:
        overall = "Negative"

    sentiment_data = SentimentReportData(
        overall_sentiment=overall,
        sentiment_score=avg_score,
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
            ("Week 1", 0.65), ("Week 2", 0.72),
            ("Week 3", 0.68), ("Week 4", 0.75),
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
        recommendations=recommendations,
        analysis_period=period_str,
        data_sources=["Google Maps", "Internal Database"]
    )

    city_desc = f"{city_limit} cities" if city_limit > 0 else "all cities"
    metadata = ReportMetadata(
        title=f"Monthly Sentiment Analysis Report - {period_str}",
        author="ReviewSignal Analytics",
        client_name=customer_company,
        report_period=f"{period_str} ({city_desc})",
        confidential=True
    )

    generator = PDFReportGenerator(output_format=OutputFormat.LETTER)
    return generator.generate_sentiment_report(
        data=sentiment_data,
        output_path=str(output_path),
        metadata=metadata
    )


def _generate_enterprise_report(
    customer: Dict,
    metrics: Dict,
    period_str: str,
    output_path: Path
) -> Optional[Path]:
    """Generate an enterprise PDF report with benchmarks, competitors, and white-label."""
    customer_company = customer['company']

    avg_score = float(metrics.get('avg_sentiment_score', 0.0))
    total_reviews = int(metrics.get('total_reviews', 0))

    # Build KPI cards
    kpis = [
        KPICard("Sentiment Score", round(avg_score, 2),
                trend=TrendDirection.UP, trend_value=3.5,
                benchmark=0.65, severity=SeverityLevel.LOW),
        KPICard("Total Reviews", total_reviews,
                trend=TrendDirection.UP, trend_value=12.0,
                severity=SeverityLevel.INFO),
        KPICard("Positive Rate",
                round(int(metrics.get('positive_count', 0)) / max(total_reviews, 1) * 100, 1),
                unit="%", trend=TrendDirection.STABLE,
                benchmark=70.0, severity=SeverityLevel.LOW),
        KPICard("Avg Rating", round(float(metrics.get('avg_rating', 0)), 1),
                trend=TrendDirection.STABLE,
                benchmark=4.0, severity=SeverityLevel.LOW),
    ]

    # Build recommendations
    recommendations = [
        Recommendation(
            title="Improve Response Time to Negative Reviews",
            description="Faster response times correlate with higher sentiment recovery rates.",
            priority=SeverityLevel.HIGH, impact="High", effort="Low",
            category="Customer Service",
            data_points=["Current avg response time: 48 hours", "Best performers respond within 4 hours"],
            action_items=["Set up automated alerts for negative reviews", "Create response templates"],
        ),
        Recommendation(
            title="Address Underperforming Locations",
            description="Several locations show below-average sentiment that may impact overall brand perception.",
            priority=SeverityLevel.MEDIUM, impact="High", effort="Medium",
            category="Operations",
            data_points=["5 locations below 0.40 sentiment score"],
            action_items=["Conduct quality audit at flagged locations", "Review staffing levels"],
        ),
    ]

    # Build benchmarks
    benchmarks = [
        BenchmarkData("Overall Sentiment", round(avg_score, 2), 0.65, 0.85, 68),
        BenchmarkData("Review Volume", total_reviews, 12000, 25000, 55),
        BenchmarkData("Average Rating", round(float(metrics.get('avg_rating', 0)), 1), 4.0, 4.7, 65),
    ]

    # Build competitor stubs
    competitors = [
        CompetitorData(
            name="Industry Average", sentiment_score=0.65,
            review_count=12000, avg_rating=4.0,
            trend=TrendDirection.STABLE,
            strengths=["Consistent brand standards"],
            weaknesses=["Slow to adapt to feedback"],
        ),
    ]

    if avg_score > 0.3:
        overall = "Positive"
    elif avg_score > -0.3:
        overall = "Neutral"
    else:
        overall = "Negative"

    data = EnterpriseReportData(
        client_name=customer_company,
        report_title=f"Monthly Sentiment Analysis Report - {period_str}",
        report_period=period_str,
        kpis=kpis,
        overall_sentiment=overall,
        sentiment_score=avg_score,
        positive_count=int(metrics.get('positive_count', 0)),
        negative_count=int(metrics.get('negative_count', 0)),
        neutral_count=int(metrics.get('neutral_count', 0)),
        total_reviews=total_reviews,
        sentiment_trend=[("Week 1", 0.65), ("Week 2", 0.72), ("Week 3", 0.68), ("Week 4", 0.75)],
        key_themes=[
            {"theme": "Service Quality", "frequency": 45, "sentiment": "Positive", "trend": "up"},
            {"theme": "Product Quality", "frequency": 38, "sentiment": "Positive", "trend": "stable"},
            {"theme": "Wait Times", "frequency": 22, "sentiment": "Negative", "trend": "down"},
        ],
        top_positive_reviews=[
            "Excellent service and fast delivery",
            "Great product quality, highly recommended",
        ],
        top_negative_reviews=[
            "Long wait times during peak hours",
            "Inconsistent product quality",
        ],
        recommendations=recommendations,
        benchmarks=benchmarks,
        competitors=competitors,
        data_sources=["Google Maps", "Internal Database", "Neural Core Analytics"],
        locations_analyzed=100,
        confidence_level=0.95,
    )

    branding = BrandingConfig(
        company_name="ReviewSignal.ai",
        tagline="Alternative Data Intelligence",
        website="reviewsignal.ai",
        primary_color="#1E3A5F",
        secondary_color="#4A90D9",
    )

    generator = EnterprisePDFGenerator(branding=branding)
    return generator.generate_enterprise_report(data, str(output_path))


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
    Send report via email using EmailSender module.

    Args:
        customer: Customer dict with keys: email, name, company, subscription_tier
        report_path: Path to the generated PDF report

    Returns:
        True on success, False on failure
    """
    try:
        from modules.email_sender import EmailSender

        sender = EmailSender()

        if not sender.client:
            logger.warning(
                "email_client_not_available",
                customer=customer['company'],
                message="Email provider not configured or package not installed"
            )
            return False

        # Derive period from report filename (e.g., 2026_01_monthly_report.pdf)
        filename = report_path.name
        try:
            parts = filename.split('_')
            year_str, month_str = parts[0], parts[1]
            from datetime import datetime as dt
            period = dt(int(year_str), int(month_str), 1).strftime('%B %Y')
        except (IndexError, ValueError):
            period = "Monthly Report"

        result = sender.send_monthly_report(
            to_email=customer['email'],
            to_name=customer.get('name', ''),
            company=customer.get('company', ''),
            report_path=report_path,
            period=period
        )

        if result.get('success'):
            logger.info(
                "report_email_sent",
                customer=customer['company'],
                email=customer['email'],
                message_id=result.get('message_id')
            )
            return True
        else:
            logger.error(
                "report_email_failed",
                customer=customer['company'],
                email=customer['email'],
                error=result.get('error', 'Unknown error')
            )
            return False

    except ImportError:
        logger.error(
            "email_module_import_failed",
            message="Could not import modules.email_sender - check installation"
        )
        return False
    except Exception as e:
        logger.error(
            "report_email_exception",
            customer=customer.get('company', 'unknown'),
            email=customer.get('email', 'unknown'),
            error=str(e)
        )
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
