#!/usr/bin/env python3
"""
Generate synthetic demo reviews for locations without reviews.
This is for DEMO purposes only - real production needs Google Maps API.

Usage: python scripts/generate_demo_reviews.py --count 10000
"""

import psycopg2
import random
import argparse
from datetime import datetime, timedelta
import sys

# Database config (use socket for peer auth)
DB_CONFIG = {
    "dbname": "reviewsignal",
    "user": "postgres"
}

# Review templates by rating
POSITIVE_TEMPLATES = [
    "Great service and friendly staff! Highly recommend.",
    "Excellent experience, will definitely come back.",
    "Best {chain} location I've visited. Clean and efficient.",
    "Really impressed with the quality. Five stars!",
    "Amazing food and great atmosphere. Love this place!",
    "Fast service, great prices. What more could you ask for?",
    "The staff here are always so helpful and kind.",
    "Consistently good quality. My go-to {chain}.",
]

NEUTRAL_TEMPLATES = [
    "Average experience. Nothing special but nothing bad either.",
    "Decent enough. Gets the job done.",
    "Standard {chain} experience. As expected.",
    "Okay service. Could be better, could be worse.",
    "It's fine. Not the best but acceptable.",
]

NEGATIVE_TEMPLATES = [
    "Disappointing visit. Long wait times.",
    "Not impressed. Quality has gone down.",
    "Service was slow and staff seemed uninterested.",
    "Expected better from {chain}. Won't return.",
    "Poor experience. Not recommended.",
]

NAMES = [
    "John Smith", "Sarah Johnson", "Michael Brown", "Emily Davis",
    "David Wilson", "Lisa Anderson", "James Taylor", "Jennifer Martinez",
    "Robert Garcia", "Maria Rodriguez", "William Lee", "Jessica White",
    "Thomas Harris", "Amanda Clark", "Daniel Lewis", "Stephanie Walker",
    "Andrew Hall", "Michelle Allen", "Christopher Young", "Ashley King"
]


def get_random_review(chain_name: str, rating: int) -> tuple:
    """Generate random review text and author"""
    if rating >= 4:
        template = random.choice(POSITIVE_TEMPLATES)
    elif rating == 3:
        template = random.choice(NEUTRAL_TEMPLATES)
    else:
        template = random.choice(NEGATIVE_TEMPLATES)

    text = template.format(chain=chain_name)
    author = random.choice(NAMES)

    # Random date in last 6 months
    days_ago = random.randint(1, 180)
    review_date = datetime.now() - timedelta(days=days_ago)

    return text, author, review_date


def generate_reviews(count: int = 10000) -> int:
    """Generate synthetic reviews for locations without reviews"""

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Get locations without reviews
    cursor.execute("""
        SELECT l.id, l.chain_name, l.rating
        FROM locations l
        LEFT JOIN reviews r ON l.id = r.location_id
        WHERE r.id IS NULL
        LIMIT %s
    """, (count,))

    locations = cursor.fetchall()
    print(f"Found {len(locations)} locations without reviews")

    reviews_created = 0

    for loc_id, chain_name, avg_rating in locations:
        # Generate 1-5 reviews per location
        num_reviews = random.randint(1, 5)

        for _ in range(num_reviews):
            # Rating based on location's average with some variance
            if avg_rating:
                base_rating = float(avg_rating)
                rating = max(1, min(5, round(base_rating + random.uniform(-1, 1))))
            else:
                rating = random.choices([5, 4, 3, 2, 1], weights=[35, 30, 20, 10, 5])[0]

            text, author, review_date = get_random_review(chain_name, rating)

            # Calculate sentiment score
            sentiment = (rating - 3) / 2  # Maps 1-5 to -1 to 1

            cursor.execute("""
                INSERT INTO reviews (location_id, author_name, rating, text, time_posted,
                                    source, sentiment_score, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (loc_id, author, rating, text, review_date, 'synthetic', sentiment))

            reviews_created += 1

            if reviews_created % 1000 == 0:
                conn.commit()
                print(f"Created {reviews_created} reviews...")

    conn.commit()
    cursor.close()
    conn.close()

    return reviews_created


def main():
    parser = argparse.ArgumentParser(description='Generate demo reviews')
    parser.add_argument('--count', type=int, default=10000, help='Number of locations to process')
    args = parser.parse_args()

    print(f"Generating synthetic reviews for up to {args.count} locations...")
    print("NOTE: These are DEMO reviews. For production, use Google Maps API.\n")

    total = generate_reviews(args.count)
    print(f"\nDone! Created {total} synthetic reviews.")


if __name__ == "__main__":
    main()
