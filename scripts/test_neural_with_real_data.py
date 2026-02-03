#!/usr/bin/env python3
"""
TEST NEURAL CORE WITH REAL DATA
Loads actual reviews from PostgreSQL and tests all Neural Core features.

Author: ReviewSignal Team
Date: February 2026
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import numpy as np
from datetime import datetime
from sqlalchemy import create_engine, text


def print_header(text: str):
    print("\n" + "━"*70)
    print(f"  {text}")
    print("━"*70)


def print_result(label: str, value: str):
    print(f"  {label}: {value}")


def load_real_reviews(limit: int = 100):
    """Load real reviews from database"""
    from config import DATABASE_URL
    engine = create_engine(DATABASE_URL)

    sql = """
        SELECT
            r.id,
            r.text,
            r.rating,
            r.location_id,
            l.name as location_name,
            l.chain_name
        FROM reviews r
        JOIN locations l ON r.location_id::text = l.id::text
        WHERE r.text IS NOT NULL
        AND r.text != ''
        AND LENGTH(r.text) > 20
        ORDER BY r.created_at DESC
        LIMIT :limit
    """

    with engine.connect() as conn:
        result = conn.execute(text(sql), {"limit": limit})
        rows = result.fetchall()

    reviews = []
    for row in rows:
        reviews.append({
            "id": row[0],
            "text": row[1],
            "rating": float(row[2]) if row[2] else 3.0,
            "location_id": str(row[3]),
            "location_name": row[4],
            "chain_name": row[5]
        })

    return reviews


def load_location_stats():
    """Load location statistics from database"""
    from config import DATABASE_URL
    engine = create_engine(DATABASE_URL)

    sql = """
        SELECT
            l.id,
            l.name,
            l.chain_name,
            l.rating,
            l.review_count,
            COUNT(r.id) as actual_reviews,
            AVG(r.rating) as avg_review_rating
        FROM locations l
        LEFT JOIN reviews r ON r.location_id::text = l.id::text
        WHERE l.rating IS NOT NULL
        GROUP BY l.id, l.name, l.chain_name, l.rating, l.review_count
        HAVING COUNT(r.id) > 0
        ORDER BY COUNT(r.id) DESC
        LIMIT 50
    """

    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = result.fetchall()

    locations = []
    for row in rows:
        locations.append({
            "id": str(row[0]),
            "name": row[1],
            "chain_name": row[2],
            "rating": float(row[3]) if row[3] else 3.0,
            "review_count": int(row[4]) if row[4] else 0,
            "actual_reviews": int(row[5]),
            "avg_review_rating": float(row[6]) if row[6] else None
        })

    return locations


def main():
    print("\n" + "="*70)
    print("  NEURAL CORE TEST - REAL DATA FROM DATABASE")
    print("  ReviewSignal 5.1.0")
    print("="*70)

    # Initialize Neural Core
    print_header("INITIALIZATION")
    from modules.neural_core import get_neural_core
    core = get_neural_core()
    print_result("Neural Core", "Initialized")

    # Load real data
    print_header("LOADING REAL DATA FROM DATABASE")

    reviews = load_real_reviews(100)
    print_result("Reviews loaded", f"{len(reviews)}")

    locations = load_location_stats()
    print_result("Locations with reviews", f"{len(locations)}")

    if not reviews:
        print("\n  ERROR: No reviews found in database!")
        return

    # Show sample reviews
    print_header("SAMPLE REVIEWS")
    for i, r in enumerate(reviews[:5]):
        text_preview = r["text"][:80] + "..." if len(r["text"]) > 80 else r["text"]
        print(f"  [{i+1}] Rating: {r['rating']} | {r['location_name']}")
        print(f"      \"{text_preview}\"")
        print()

    # Test 1: Embeddings on real reviews
    print_header("TEST 1: EMBEDDINGS ON REAL REVIEWS")
    start = time.time()

    review_texts = [r["text"] for r in reviews[:20]]
    embeddings = core.embed_batch(review_texts)

    elapsed = time.time() - start
    print_result("Reviews embedded", f"{len(review_texts)}")
    print_result("Embedding shape", f"{embeddings.shape}")
    print_result("Time", f"{elapsed:.2f}s ({elapsed/len(review_texts)*1000:.0f}ms per review)")

    # Test 2: Semantic similarity between reviews
    print_header("TEST 2: SEMANTIC SIMILARITY")

    # Find most similar reviews
    positive_reviews = [r for r in reviews if r["rating"] >= 4][:10]
    negative_reviews = [r for r in reviews if r["rating"] <= 2][:10]

    if positive_reviews and negative_reviews:
        pos_text = positive_reviews[0]["text"]
        neg_text = negative_reviews[0]["text"]

        sim_pos_neg = core.similarity(pos_text, neg_text)
        print_result("Positive vs Negative", f"{sim_pos_neg:.4f}")

        if len(positive_reviews) > 1:
            sim_pos_pos = core.similarity(pos_text, positive_reviews[1]["text"])
            print_result("Positive vs Positive", f"{sim_pos_pos:.4f}")

        print()
        print(f"  Positive: \"{pos_text[:60]}...\"")
        print(f"  Negative: \"{neg_text[:60]}...\"")

    # Test 3: Find similar reviews
    print_header("TEST 3: SEMANTIC SEARCH")

    query = "terrible food cold service"
    candidates = [r["text"] for r in reviews[:50]]

    similar = core.find_similar(query, candidates, top_k=5)
    print_result("Query", f"\"{query}\"")
    print()
    print("  Top matches:")
    for match in similar:
        text_preview = match["text"][:60] + "..." if len(match["text"]) > 60 else match["text"]
        print(f"    [{match['rank']}] Score: {match['score']:.4f}")
        print(f"        \"{text_preview}\"")

    # Test 4: Incremental statistics for locations
    print_header("TEST 4: INCREMENTAL STATISTICS FOR REAL LOCATIONS")

    # Update stats for top locations
    for loc in locations[:10]:
        loc_id = f"loc_{loc['id']}"

        # Add historical ratings
        if loc["avg_review_rating"]:
            for _ in range(min(loc["actual_reviews"], 20)):
                rating = np.random.normal(loc["avg_review_rating"], 0.5)
                rating = max(1, min(5, rating))
                core.update_stats(loc_id, rating, "location")

    # Show stats for top 5
    print("  Location Statistics:")
    for loc in locations[:5]:
        loc_id = f"loc_{loc['id']}"
        stats = core.get_stats(loc_id)
        if stats:
            print(f"    {loc['name'][:30]}")
            print(f"      Mean: {stats.mean:.2f}, Std: {stats.std:.2f}, Trend: {stats.trend_direction}")

    # Test 5: Anomaly detection on real data
    print_header("TEST 5: ANOMALY DETECTION")

    anomalies_found = []
    for loc in locations[:20]:
        loc_id = f"loc_{loc['id']}"

        # Check if current rating is anomalous vs historical
        if loc["avg_review_rating"]:
            # Test with a low rating
            prediction = core.check_anomaly(loc_id, 1.5)
            if prediction.is_anomaly:
                anomalies_found.append({
                    "location": loc["name"],
                    "test_rating": 1.5,
                    "avg_rating": loc["avg_review_rating"],
                    "score": prediction.anomaly_score
                })

    print_result("Locations tested", "20")
    print_result("Anomalies detected (rating=1.5)", f"{len(anomalies_found)}")

    if anomalies_found:
        print()
        print("  Top anomalies:")
        for a in sorted(anomalies_found, key=lambda x: x["score"], reverse=True)[:3]:
            print(f"    {a['location'][:30]}: score={a['score']:.4f} (avg={a['avg_rating']:.2f})")

    # Test 6: Full review analysis
    print_header("TEST 6: FULL REVIEW ANALYSIS")

    if reviews:
        review = reviews[0]
        analysis = core.analyze_review(
            review["text"],
            review["rating"],
            review["location_id"]
        )

        print_result("Review", f"\"{review['text'][:50]}...\"")
        print_result("Rating", f"{review['rating']}")
        print_result("Embedding computed", f"{analysis['embedding_computed']}")
        print_result("From cache", f"{analysis['embedding_from_cache']}")
        print_result("Is anomaly", f"{analysis['anomaly']['is_anomaly']}")
        print_result("Anomaly score", f"{analysis['anomaly']['anomaly_score']:.4f}")

    # Test 7: Chain/Brand analysis
    print_header("TEST 7: BRAND ANALYSIS (Echo-Neural Bridge)")

    from modules.echo_neural_bridge import EchoNeuralBridge
    bridge = EchoNeuralBridge()

    # Find reviews by chain
    chains = {}
    for r in reviews:
        chain = r.get("chain_name") or "Unknown"
        if chain not in chains:
            chains[chain] = []
        chains[chain].append(r)

    # Analyze top chains
    print("  Brand Analysis:")
    for chain, chain_reviews in sorted(chains.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
        if len(chain_reviews) >= 3:
            analysis = bridge.analyze_brand_reviews(chain, chain_reviews)
            print(f"    {chain}:")
            print(f"      Reviews: {analysis['total_reviews']}, Avg: {analysis['avg_rating']:.2f}")
            print(f"      Coherence: {analysis['semantic_coherence']:.4f}, Anomaly rate: {analysis['anomaly_rate']:.1%}")

    # Summary
    print_header("SUMMARY")
    health = core.health_check()

    print_result("Status", health["status"])
    print_result("Cache hit rate", f"{health['cache']['hit_rate']:.1%}")
    print_result("Stats tracked", f"{health['stats_tracked']}")
    print_result("Isolation Forest", "Ready" if health['isolation_forest']['has_model'] else "Needs data")

    print("\n" + "="*70)
    print("  ALL TESTS WITH REAL DATA COMPLETE!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
