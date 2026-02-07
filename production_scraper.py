#!/usr/bin/env python3
"""
Production Scraper - Continuous Google Maps Scraping with PostgreSQL Integration
Runs 24/7, scrapes locations and reviews, saves to database
"""

import asyncio
from psycopg2.extras import RealDictCursor
import time
import structlog
from datetime import datetime
from typing import List, Dict
import os

from modules.real_scraper import GoogleMapsRealScraper
from modules.db import get_connection, return_connection
from modules.data_validator import LocationValidator, ReviewValidator
from config import GOOGLE_MAPS_API_KEY, REDIS_URL, CHAINS, ALL_CITIES
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = structlog.get_logger()


class ProductionScraper:
    """Production scraper with PostgreSQL integration"""

    def __init__(self):
        self.scraper = GoogleMapsRealScraper(
            api_key=GOOGLE_MAPS_API_KEY,
            redis_url=REDIS_URL,
            rate_limit=50,
            max_workers=5
        )

        self.stats = {
            "locations_added": 0,
            "locations_validation_failed": 0,
            "reviews_added": 0,
            "reviews_validation_failed": 0,
            "errors": 0,
            "start_time": datetime.now()
        }
        self._sentiment_analyzer = SentimentIntensityAnalyzer()

    def get_db_connection(self):
        """Get PostgreSQL connection from shared pool."""
        return get_connection()

    def return_db_connection(self, conn) -> None:
        """Return connection to shared pool."""
        return_connection(conn)

    def save_location(self, place) -> bool:
        """Save location to database with validation gate"""
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()

            # Handle both dict and object
            place_id = place.place_id if hasattr(place, 'place_id') else place['place_id']
            name = place.name if hasattr(place, 'name') else place['name']
            address = place.address if hasattr(place, 'address') else place['address']
            city = place.city if hasattr(place, 'city') else place['city']
            country = place.country if hasattr(place, 'country') else place['country']
            latitude = place.latitude if hasattr(place, 'latitude') else place['latitude']
            longitude = place.longitude if hasattr(place, 'longitude') else place['longitude']
            rating = place.rating if hasattr(place, 'rating') else place['rating']
            review_count = place.review_count if hasattr(place, 'review_count') else place['review_count']
            chain = place.chain if hasattr(place, 'chain') else place['chain']
            phone = place.phone if hasattr(place, 'phone') else place.get('phone')
            website = place.website if hasattr(place, 'website') else place.get('website')
            business_status = place.business_status if hasattr(place, 'business_status') else place.get('business_status', 'OPERATIONAL')

            # --- VALIDATION GATE ---
            loc_dict = {
                "name": name, "place_id": place_id, "address": address,
                "city": city, "country": country,
                "latitude": latitude, "longitude": longitude,
                "rating": rating,
            }
            valid, issues = LocationValidator.validate(loc_dict)
            if not valid:
                self.stats["locations_validation_failed"] += 1
                logger.warning("location_validation_failed", place_id=place_id, name=name, issues=issues)
                cur.close()
                self.return_db_connection(conn)
                return False
            # Apply auto-fixed country back
            country = loc_dict.get("country", country)

            # Check if location exists
            cur.execute(
                "SELECT id FROM locations WHERE place_id = %s",
                (place_id,)
            )
            existing = cur.fetchone()

            if existing:
                # Update existing
                cur.execute("""
                    UPDATE locations SET
                        rating = %s,
                        review_count = %s,
                        updated_at = NOW()
                    WHERE place_id = %s
                """, (rating, review_count, place_id))
                logger.info(f"   ↻ Updated: {name}")
            else:
                # Insert new
                cur.execute("""
                    INSERT INTO locations (
                        place_id, name, address, city, country,
                        latitude, longitude, rating, review_count,
                        chain_name, phone, website, business_status,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        NOW(), NOW()
                    )
                """, (
                    place_id, name, address, city, country,
                    latitude, longitude, rating, review_count,
                    chain, phone, website, business_status
                ))
                self.stats["locations_added"] += 1
                logger.info(f"   ✅ Saved: {name} ({rating}★, {review_count} reviews)")

            conn.commit()
            cur.close()
            self.return_db_connection(conn)
            return True

        except Exception as e:
            logger.error(f"   ❌ DB Error: {e}")
            self.stats["errors"] += 1
            return False

    def save_reviews(self, place_id: str, location_id: int, reviews: List) -> int:
        """Save reviews to database"""
        if not reviews:
            return 0

        saved = 0
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()

            for review in reviews:
                try:
                    # Handle both dict and object
                    author_name = review.get('author_name') if isinstance(review, dict) else review.author_name
                    rating = review.get('rating') if isinstance(review, dict) else review.rating
                    text = review.get('text', '') if isinstance(review, dict) else review.text
                    time = review.get('time') if isinstance(review, dict) else review.time
                    language = review.get('language', 'en') if isinstance(review, dict) else review.language

                    # --- REVIEW VALIDATION GATE ---
                    rev_dict = {"text": text, "rating": rating, "author_name": author_name}
                    rev_valid, rev_issues = ReviewValidator.validate(rev_dict)
                    if not rev_valid:
                        self.stats["reviews_validation_failed"] += 1
                        logger.debug("review_validation_failed", place_id=place_id, issues=rev_issues)
                        continue
                    # Apply auto-scored sentiment from validator
                    sentiment_score = rev_dict.get("sentiment_score")

                    # Check if review exists
                    review_hash = f"{place_id}_{author_name}_{time}"

                    cur.execute(
                        "SELECT id FROM reviews WHERE review_hash = %s",
                        (review_hash,)
                    )
                    if cur.fetchone():
                        continue  # Skip existing

                    # Compute sentiment if validator did not set it
                    if sentiment_score is None and text and text.strip():
                        sentiment_score = round(
                            self._sentiment_analyzer.polarity_scores(text)["compound"], 4
                        )

                    # Insert new review with sentiment
                    cur.execute("""
                        INSERT INTO reviews (
                            location_id, place_id, author_name, rating,
                            text, time_posted, language, source,
                            sentiment_score, review_hash, created_at
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, to_timestamp(%s), %s, %s,
                            %s, %s, NOW()
                        )
                    """, (
                        location_id, place_id, author_name, rating,
                        text, time, language, 'google_maps',
                        sentiment_score, review_hash
                    ))
                    saved += 1

                except Exception as e:
                    logger.warning(f"      ⚠️ Review skip: {e}")
                    continue

            conn.commit()
            cur.close()
            self.return_db_connection(conn)

            if saved > 0:
                self.stats["reviews_added"] += saved
                logger.info(f"      📝 Saved {saved} reviews")

            return saved

        except Exception as e:
            logger.error(f"      ❌ Reviews DB Error: {e}")
            return 0

    def scrape_cycle(self):
        """One scraping cycle"""
        logger.info("="*70)
        logger.info("🚀 Starting scrape cycle")
        logger.info("="*70)

        # Sample chains and cities (rotate to cover all)
        import random

        # Focus on top chains with most locations
        priority_chains = [
            "McDonald's", "Starbucks", "Subway", "KFC", "Burger King",
            "Pizza Hut", "Domino's Pizza", "Dunkin'", "Taco Bell", "Chipotle"
        ]

        # Pick 3 random chains
        chains_to_scrape = random.sample(priority_chains, min(3, len(priority_chains)))

        # Pick 5 random cities
        cities_to_scrape = random.sample(ALL_CITIES, min(5, len(ALL_CITIES)))

        logger.info(f"🎯 Chains: {', '.join(chains_to_scrape)}")
        logger.info(f"🌍 Cities: {', '.join([c if isinstance(c, str) else c.get('city', '') for c in cities_to_scrape[:3]])}...")
        logger.info("")

        for chain in chains_to_scrape:
            logger.info(f"🔵 Scraping: {chain}")

            try:
                places = self.scraper.scrape_chain(
                    chain_name=chain,
                    cities=cities_to_scrape,
                    max_per_city=10  # 10 per city = 50 locations per chain per cycle
                )

                for place in places:
                    # Save location
                    if self.save_location(place):
                        # Get location ID for reviews
                        place_id = place.place_id if hasattr(place, 'place_id') else place['place_id']
                        reviews = place.reviews if hasattr(place, 'reviews') else place.get('reviews', [])

                        conn = self.get_db_connection()
                        cur = conn.cursor()
                        cur.execute(
                            "SELECT id FROM locations WHERE place_id = %s",
                            (place_id,)
                        )
                        result = cur.fetchone()
                        if result:
                            location_id = result[0]
                            cur.close()
                            self.return_db_connection(conn)

                            # Save reviews if available
                            if reviews:
                                self.save_reviews(place_id, location_id, reviews)
                        else:
                            cur.close()
                            self.return_db_connection(conn)

                logger.info(f"   ✓ Completed: {chain} ({len(places)} locations)")
                logger.info("")

            except Exception as e:
                logger.error(f"   ❌ Error scraping {chain}: {e}")
                self.stats["errors"] += 1
                continue

        # === REVIEW BACKFILL PHASE ===
        # Scrape reviews for existing locations that have none
        logger.info("📥 Review backfill: fetching uncovered locations...")
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT l.id, l.place_id, l.name
                FROM locations l
                LEFT JOIN reviews r ON r.location_id = l.id
                WHERE r.id IS NULL
                AND l.place_id LIKE 'ChIJ%%'
                ORDER BY CASE WHEN l.chain_id IS NOT NULL THEN 0 ELSE 1 END, l.id
                LIMIT 50
            """)
            uncovered = cur.fetchall()
            cur.close()
            self.return_db_connection(conn)

            backfill_count = 0
            for loc_id, place_id, loc_name in uncovered:
                try:
                    details = self.scraper.get_place_details(place_id)
                    if details and details.reviews:
                        self.save_reviews(place_id, loc_id, details.reviews)
                        backfill_count += len(details.reviews)
                    time.sleep(0.5)  # Rate limit
                except Exception as e:
                    logger.debug(f"Backfill error for {place_id}: {e}")

            if backfill_count > 0:
                logger.info(f"   📥 Backfill: {backfill_count} reviews for {len(uncovered)} locations")
        except Exception as e:
            logger.error(f"   Backfill error: {e}")

        # Print stats
        runtime = (datetime.now() - self.stats["start_time"]).total_seconds() / 60

        # Review source breakdown (all reviews in DB)
        source_stats = {}
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT source, COUNT(*) FROM reviews "
                "GROUP BY source ORDER BY COUNT(*) DESC"
            )
            source_stats = {row[0]: row[1] for row in cur.fetchall()}
            cur.close()
            self.return_db_connection(conn)
        except Exception:
            pass

        logger.info("="*70)
        logger.info(f"📊 Cycle complete!")
        logger.info(f"   Locations added: {self.stats['locations_added']}")
        logger.info(f"   Locations validation failed: {self.stats['locations_validation_failed']}")
        logger.info(f"   Reviews added: {self.stats['reviews_added']}")
        logger.info(f"   Reviews validation failed: {self.stats['reviews_validation_failed']}")
        logger.info(f"   Errors: {self.stats['errors']}")
        logger.info(f"   Runtime: {runtime:.1f} minutes")
        if source_stats:
            total_reviews = sum(source_stats.values())
            logger.info(f"   Total reviews in DB: {total_reviews:,}")
            for source, count in source_stats.items():
                logger.info(f"     {source}: {count:,}")
        logger.info("="*70)
        logger.info("")

    def run(self):
        """Run continuous scraping"""
        logger.info("""
╔══════════════════════════════════════════════════════════════════════╗
║                  PRODUCTION SCRAPER v1.0                             ║
║              Google Maps → PostgreSQL Integration                    ║
╚══════════════════════════════════════════════════════════════════════╝
        """)

        cycle = 0
        while True:
            cycle += 1
            logger.info(f"🔄 CYCLE #{cycle}")

            try:
                self.scrape_cycle()

                # Wait 30 minutes between cycles
                logger.info("⏸️  Waiting 30 minutes before next cycle...")
                logger.info("")
                time.sleep(1800)  # 30 minutes

            except KeyboardInterrupt:
                logger.info("\n👋 Shutting down gracefully...")
                break
            except Exception as e:
                logger.error(f"❌ Cycle error: {e}")
                logger.info("⏸️  Waiting 5 minutes before retry...")
                time.sleep(300)  # 5 minutes on error


if __name__ == "__main__":
    scraper = ProductionScraper()
    scraper.run()
