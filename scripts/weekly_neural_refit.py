#!/usr/bin/env python3
"""
WEEKLY NEURAL REFIT - Automated Model Update
Cron job script for Neural Core weekly maintenance.

Schedule: Every Sunday at 00:00 UTC
Crontab: 0 0 * * 0 /home/info_betsim/reviewsignal-5.0/venv/bin/python /home/info_betsim/reviewsignal-5.0/scripts/weekly_neural_refit.py >> /var/log/reviewsignal/neural_refit.log 2>&1

Author: ReviewSignal Team
Version: 5.1.0
Date: February 2026
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ]
)

logger = structlog.get_logger()


def load_training_data_from_db():
    """Load recent review data for Isolation Forest training"""
    from sqlalchemy import create_engine, text
    import numpy as np

    try:
        from config import DATABASE_URL
    except ImportError:
        DATABASE_URL = "postgresql://reviewsignal:reviewsignal2026@localhost:5432/reviewsignal"

    engine = create_engine(DATABASE_URL)

    # Get recent reviews with ratings (last 30 days)
    sql = """
        SELECT
            r.rating,
            r.sentiment_score,
            l.rating as location_avg_rating,
            l.review_count
        FROM reviews r
        JOIN locations l ON r.location_id::text = l.id::text
        WHERE r.created_at > NOW() - INTERVAL '30 days'
        AND r.rating IS NOT NULL
        LIMIT 10000
    """

    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = result.fetchall()

    if not rows:
        logger.warning("no_training_data_found")
        return None

    # Convert to feature matrix
    features = []
    for row in rows:
        rating, sentiment, loc_rating, review_count = row
        features.append([
            float(rating) if rating else 3.0,
            float(sentiment) if sentiment else 0.0,
            float(loc_rating) if loc_rating else 3.0,
            min(float(review_count) if review_count else 0, 1000) / 1000  # Normalize
        ])

    return np.array(features)


def update_location_stats():
    """Update incremental statistics for all active locations"""
    from sqlalchemy import create_engine, text
    from modules.neural_core import get_neural_core

    try:
        from config import DATABASE_URL
    except ImportError:
        DATABASE_URL = "postgresql://reviewsignal:reviewsignal2026@localhost:5432/reviewsignal"

    engine = create_engine(DATABASE_URL)
    core = get_neural_core()

    # Get location statistics from database
    sql = """
        SELECT
            l.id as location_id,
            AVG(r.rating) as avg_rating,
            COUNT(r.id) as review_count
        FROM locations l
        LEFT JOIN reviews r ON r.location_id::text = l.id::text
        WHERE r.created_at > NOW() - INTERVAL '7 days'
        GROUP BY l.id
        HAVING COUNT(r.id) > 0
        LIMIT 5000
    """

    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = result.fetchall()

    updated = 0
    for row in rows:
        location_id, avg_rating, review_count = row
        if avg_rating:
            core.update_stats(f"loc_{location_id}", float(avg_rating), "location")
            updated += 1

    return updated


def main():
    """Main refit function"""
    start_time = datetime.utcnow()
    logger.info("weekly_neural_refit_started", timestamp=start_time.isoformat())

    results = {
        "started_at": start_time.isoformat(),
        "tasks": {}
    }

    try:
        # Import Neural Core
        from modules.neural_core import get_neural_core
        core = get_neural_core()

        # Task 1: Load training data
        logger.info("loading_training_data")
        training_data = load_training_data_from_db()

        if training_data is not None and len(training_data) > 0:
            logger.info("training_data_loaded", samples=len(training_data))

            # Add to Isolation Forest
            for sample in training_data:
                core.add_training_sample(sample)

            results["tasks"]["load_data"] = {
                "status": "success",
                "samples": len(training_data)
            }
        else:
            results["tasks"]["load_data"] = {
                "status": "skipped",
                "reason": "no_data"
            }

        # Task 2: Refit Isolation Forest
        logger.info("refitting_isolation_forest")
        refit_result = core.weekly_refit()
        results["tasks"]["refit_model"] = refit_result

        # Task 3: Update location statistics
        logger.info("updating_location_stats")
        stats_updated = update_location_stats()
        results["tasks"]["update_stats"] = {
            "status": "success",
            "locations_updated": stats_updated
        }

        # Task 4: Health check
        health = core.health_check()
        results["health"] = {
            "status": health["status"],
            "cache_hit_rate": health["cache"]["hit_rate"],
            "stats_tracked": health["stats_tracked"]
        }

        # Task 5: Notify running Neural API to reload model from cache
        logger.info("notifying_neural_api_to_reload")
        try:
            import requests
            response = requests.post(
                "http://localhost:8005/api/neural/reload",
                timeout=10
            )
            if response.status_code == 200:
                reload_result = response.json()
                results["tasks"]["api_reload"] = {
                    "status": "success",
                    "api_response": reload_result
                }
                logger.info("neural_api_reloaded", result=reload_result)
            else:
                results["tasks"]["api_reload"] = {
                    "status": "warning",
                    "reason": f"API returned {response.status_code}"
                }
        except Exception as reload_error:
            results["tasks"]["api_reload"] = {
                "status": "warning",
                "reason": str(reload_error)
            }
            logger.warning("neural_api_reload_failed", error=str(reload_error))

        results["status"] = "success"

    except Exception as e:
        logger.error("weekly_refit_failed", error=str(e))
        results["status"] = "error"
        results["error"] = str(e)

    # Calculate duration
    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()
    results["completed_at"] = end_time.isoformat()
    results["duration_seconds"] = round(duration, 2)

    logger.info(
        "weekly_neural_refit_complete",
        status=results["status"],
        duration=duration
    )

    # Print summary
    print("\n" + "="*60)
    print("  WEEKLY NEURAL REFIT COMPLETE")
    print("="*60)
    print(f"  Status: {results['status']}")
    print(f"  Duration: {duration:.2f}s")

    if "tasks" in results:
        for task, info in results["tasks"].items():
            status = info.get("status", "unknown")
            print(f"  - {task}: {status}")

    print("="*60 + "\n")

    return results


if __name__ == "__main__":
    main()
