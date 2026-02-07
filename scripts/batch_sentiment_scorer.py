#!/usr/bin/env python3
"""
Batch Sentiment Scorer - VADER-based sentiment scoring for reviews.

Processes reviews with NULL sentiment_score in batches, using VADER
(Valence Aware Dictionary and sEntiment Reasoner) for fast, local,
zero-cost sentiment analysis.

Usage:
    python3 scripts/batch_sentiment_scorer.py                  # Score all NULL reviews
    python3 scripts/batch_sentiment_scorer.py --limit 1000     # Score first 1000
    python3 scripts/batch_sentiment_scorer.py --dry-run        # Preview only
    python3 scripts/batch_sentiment_scorer.py --batch-size 200 # Custom batch size

Output: sentiment_score in range -1.0 (most negative) to 1.0 (most positive)
"""

import argparse
import os
import signal
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from modules.db import get_connection, return_connection

_interrupted = False


def _signal_handler(signum, frame):
    global _interrupted
    _interrupted = True
    print("\n[!] Interrupt received. Finishing current batch and exiting...")


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


class BatchSentimentScorer:
    """Score reviews using VADER sentiment analysis."""

    def __init__(self, batch_size=500, limit=0, dry_run=False):
        self.batch_size = batch_size
        self.limit = limit
        self.dry_run = dry_run
        self.analyzer = SentimentIntensityAnalyzer()
        self.total_processed = 0
        self.total_scored = 0
        self.total_skipped = 0
        self.total_errors = 0
        self.score_sum = 0.0
        self.start_time = None

    def score_text(self, text):
        """Compute VADER compound sentiment score (-1.0 to 1.0)."""
        if not text or not text.strip():
            return 0.0
        scores = self.analyzer.polarity_scores(text)
        return scores["compound"]

    def _count_remaining(self):
        """Count reviews with NULL sentiment_score that have text."""
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM reviews "
                "WHERE sentiment_score IS NULL "
                "AND text IS NOT NULL AND length(text) > 0"
            )
            count = cur.fetchone()[0]
            cur.close()
            return count
        finally:
            return_connection(conn)

    def _fetch_batch(self, batch_size):
        """Fetch a batch of reviews with NULL sentiment_score."""
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, text FROM reviews "
                "WHERE sentiment_score IS NULL "
                "AND text IS NOT NULL AND length(text) > 0 "
                "ORDER BY id "
                "LIMIT %s",
                (batch_size,)
            )
            rows = cur.fetchall()
            cur.close()
            return rows
        finally:
            return_connection(conn)

    def _update_batch(self, updates):
        """Write sentiment scores to database. updates = [(score, id), ...]"""
        if not updates or self.dry_run:
            return 0
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.executemany(
                "UPDATE reviews SET sentiment_score = %s WHERE id = %s",
                updates
            )
            updated = cur.rowcount
            conn.commit()
            cur.close()
            return updated
        except Exception:
            conn.rollback()
            raise
        finally:
            return_connection(conn)

    def _format_eta(self, elapsed, processed, total):
        """Calculate and format ETA string."""
        if processed == 0:
            return "calculating..."
        remaining = total - processed
        rate = processed / elapsed
        if rate == 0:
            return "unknown"
        eta_seconds = remaining / rate
        if eta_seconds < 60:
            return "%.0fs" % eta_seconds
        elif eta_seconds < 3600:
            return "%.1fm" % (eta_seconds / 60)
        else:
            return "%.1fh" % (eta_seconds / 3600)

    def run(self):
        """Run the batch sentiment scoring pipeline."""
        self.start_time = time.time()
        total_remaining = self._count_remaining()
        if self.limit > 0:
            total_to_process = min(total_remaining, self.limit)
        else:
            total_to_process = total_remaining

        print("=" * 70)
        print("  BATCH SENTIMENT SCORER - VADER")
        print("=" * 70)
        print("  Reviews with NULL sentiment_score: %s" % "{:,}".format(total_remaining))
        print("  Will process: %s" % "{:,}".format(total_to_process))
        print("  Batch size: %d" % self.batch_size)
        print("  Dry run: %s" % self.dry_run)
        print("=" * 70)
        print()

        if total_to_process == 0:
            print("  Nothing to process. All reviews already scored.")
            return self._build_stats()

        batch_num = 0
        while self.total_processed < total_to_process and not _interrupted:
            batch_num += 1
            remaining = total_to_process - self.total_processed
            current_batch_size = min(self.batch_size, remaining)

            rows = self._fetch_batch(current_batch_size)
            if not rows:
                break

            updates = []
            batch_scored = 0

            for review_id, text in rows:
                try:
                    score = self.score_text(text)
                    updates.append((round(score, 4), review_id))
                    self.score_sum += score
                    batch_scored += 1
                except Exception:
                    self.total_errors += 1

            if updates:
                try:
                    self._update_batch(updates)
                except Exception as e:
                    print("  [ERROR] Batch %d DB write failed: %s" % (batch_num, e))
                    self.total_errors += len(updates)
                    batch_scored = 0

            self.total_processed += len(rows)
            self.total_scored += batch_scored

            elapsed = time.time() - self.start_time
            rate = self.total_processed / elapsed if elapsed > 0 else 0
            eta = self._format_eta(elapsed, self.total_processed, total_to_process)
            avg_score = self.score_sum / self.total_scored if self.total_scored > 0 else 0
            pct = self.total_processed / total_to_process * 100

            print(
                "  Batch %4d: processed %7s/%s (%.1f%%) | "
                "rate: %s/s | avg: %+.3f | errors: %d | ETA: %s" % (
                    batch_num,
                    "{:,}".format(self.total_processed),
                    "{:,}".format(total_to_process),
                    pct,
                    "{:,.0f}".format(rate),
                    avg_score,
                    self.total_errors,
                    eta
                )
            )

        stats = self._build_stats()
        print()
        print("=" * 70)
        if _interrupted:
            print("  INTERRUPTED - partial results saved")
        elif self.dry_run:
            print("  DRY RUN COMPLETE - no changes written to database")
        else:
            print("  SCORING COMPLETE")
        print("=" * 70)
        print("  Processed:  %s" % "{:,}".format(stats["processed"]))
        print("  Scored:     %s" % "{:,}".format(stats["scored"]))
        print("  Errors:     %s" % "{:,}".format(stats["errors"]))
        print("  Avg score:  %+.4f" % stats["avg_score"])
        print("  Runtime:    %.1fs (%d reviews/s)" % (stats["runtime_seconds"], stats["rate"]))
        print("=" * 70)
        return stats

    def _build_stats(self):
        elapsed = time.time() - self.start_time if self.start_time else 0
        return {
            "processed": self.total_processed,
            "scored": self.total_scored,
            "skipped": self.total_skipped,
            "errors": self.total_errors,
            "avg_score": self.score_sum / self.total_scored if self.total_scored > 0 else 0.0,
            "runtime_seconds": round(elapsed, 1),
            "rate": self.total_processed / elapsed if elapsed > 0 else 0,
            "dry_run": self.dry_run,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Batch sentiment scoring for reviews using VADER."
    )
    parser.add_argument(
        "--batch-size", type=int, default=500,
        help="Reviews per batch/commit (default: 500)",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Max reviews to process, 0 = all (default: 0)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Compute scores without writing to database",
    )
    args = parser.parse_args()

    scorer = BatchSentimentScorer(
        batch_size=args.batch_size,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    scorer.run()


if __name__ == "__main__":
    main()
