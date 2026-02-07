#!/usr/bin/env python3
"""
Daily Scraper - Automated daily review collection
Designed for cron execution (runs at 3:00 UTC daily)

Strategy:
- Scrape 3-5 random chains daily
- Focus on 5-10 major cities
- Target: 500-1000 new reviews per day
- Rotate chains to ensure even coverage
"""
import os
import sys
import psycopg2
import random
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/home/info_betsim/reviewsignal-5.0')

from modules.real_scraper import GoogleMapsRealScraper

# Configuration
API_KEY = 'AIzaSyDZYIYVfDYVV8KMtQdbKJEnYufhwswI3Wk'

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'reviewsignal',
    'user': 'reviewsignal',
    'password': 'reviewsignal2026'
}

# City pool (rotate through these)
ALL_CITIES = [
    "New York, NY, USA",
    "Los Angeles, CA, USA",
    "Chicago, IL, USA",
    "Houston, TX, USA",
    "Phoenix, AZ, USA",
    "Philadelphia, PA, USA",
    "San Antonio, TX, USA",
    "San Diego, CA, USA",
    "Dallas, TX, USA",
    "San Jose, CA, USA",
    "Austin, TX, USA",
    "Jacksonville, FL, USA",
    "San Francisco, CA, USA",
    "Columbus, OH, USA",
    "Indianapolis, IN, USA",
    "Seattle, WA, USA",
    "Denver, CO, USA",
    "Boston, MA, USA",
    "Miami, FL, USA",
    "Atlanta, GA, USA"
]

# All available chains with search queries
ALL_CHAINS = [
    # Fast Food
    ("Starbucks", "Starbucks", 5),
    ("McDonald's", "McDonald's", 5),
    ("KFC", "KFC", 3),
    ("Pizza Hut", "Pizza Hut", 3),
    ("Burger King", "Burger King", 3),
    ("Subway", "Subway", 3),
    ("Domino's", "Domino's Pizza", 3),
    ("Dunkin'", "Dunkin'", 3),
    ("Taco Bell", "Taco Bell", 3),
    ("Chipotle", "Chipotle", 3),

    # Drugstores
    ("CVS", "CVS Pharmacy", 3),
    ("Walgreens", "Walgreens", 3),
    ("Sephora", "Sephora", 2),

    # Clothing
    ("H&M", "H&M", 2),
    ("Zara", "Zara", 2),
    ("Gap", "Gap", 2),
    ("Old Navy", "Old Navy", 2),

    # Hotels
    ("Marriott", "Marriott", 2),
    ("Hilton", "Hilton", 2),
    ("Holiday Inn", "Holiday Inn", 2),
]

def get_chain_last_scraped():
    """Get timestamp of last scrape for each chain"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        cur.execute("""
            SELECT l.chain_name, MAX(r.created_at) as last_scrape
            FROM locations l
            LEFT JOIN reviews r ON l.id = r.location_id
            WHERE r.source = 'google_maps'
            GROUP BY l.chain_name
        """)

        results = {row[0]: row[1] for row in cur.fetchall()}
        cur.close()
        conn.close()
        return results
    except Exception as e:
        print(f"⚠️ Could not fetch last scraped times: {e}")
        return {}

def select_daily_chains(num_chains=4):
    """Select chains that need scraping (prioritize least recently scraped)"""
    last_scraped = get_chain_last_scraped()

    # Sort chains by last scraped time (None = never scraped, highest priority)
    chain_priority = []
    for chain_name, search_query, max_per_city in ALL_CHAINS:
        last_time = last_scraped.get(chain_name)
        priority = 0 if last_time is None else (datetime.now() - last_time).days
        chain_priority.append((priority, chain_name, search_query, max_per_city))

    # Sort by priority (descending) and take top N
    chain_priority.sort(reverse=True, key=lambda x: x[0])

    selected = [(name, query, max_loc) for _, name, query, max_loc in chain_priority[:num_chains]]
    return selected

def save_to_database(places, chain_name):
    """Save scraped places and reviews to PostgreSQL"""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        locations_added = 0
        reviews_added = 0

        for place in places:
            # Check if location exists
            cur.execute("""
                SELECT id FROM locations
                WHERE place_id = %s
            """, (place['place_id'],))

            location_result = cur.fetchone()

            if location_result:
                location_id = location_result[0]
            else:
                # Insert location
                cur.execute("""
                    INSERT INTO locations (
                        chain_name, name, address, city, country,
                        latitude, longitude, rating, review_count,
                        place_id, phone, website, business_status,
                        data_quality_score, source, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) RETURNING id
                """, (
                    chain_name,
                    place['name'],
                    place['address'],
                    place.get('city', ''),
                    place.get('country', 'USA'),
                    place['latitude'],
                    place['longitude'],
                    place['rating'],
                    place['review_count'],
                    place['place_id'],
                    place.get('phone'),
                    place.get('website'),
                    place.get('business_status', 'OPERATIONAL'),
                    place.get('data_quality_score', 0),
                    'google_maps',
                    datetime.now()
                ))
                location_id = cur.fetchone()[0]
                locations_added += 1

            # Insert reviews
            for review in place.get('reviews', []):
                # Convert Unix timestamp to datetime
                review_time = datetime.fromtimestamp(review['time']) if 'time' in review else datetime.now()

                # Check if review exists
                cur.execute("""
                    SELECT id FROM reviews
                    WHERE location_id = %s
                    AND author_name = %s
                    AND time_posted = %s
                """, (location_id, review['author_name'], review_time))

                if not cur.fetchone():
                    cur.execute("""
                        INSERT INTO reviews (
                            location_id, place_id, author_name,
                            rating, text, time_posted,
                            language, source, created_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        location_id,
                        place['place_id'],
                        review['author_name'],
                        review['rating'],
                        review.get('text', ''),
                        review_time,
                        review.get('language', 'en'),
                        'google_maps',
                        datetime.now()
                    ))
                    reviews_added += 1

        conn.commit()
        cur.close()

        return locations_added, reviews_added

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Database error: {e}")
        return 0, 0
    finally:
        if conn:
            conn.close()

def main():
    """Main daily scraping routine"""
    print("="*80)
    print("📅 DAILY SCRAPER - Automated Review Collection")
    print("="*80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Select 4 chains to scrape today (prioritize least recently scraped)
    daily_chains = select_daily_chains(num_chains=4)
    print(f"Chains selected: {', '.join([c[0] for c in daily_chains])}")

    # Select 8 random cities
    daily_cities = random.sample(ALL_CITIES, 8)
    print(f"Cities selected: {len(daily_cities)} cities")
    print("-"*80)

    scraper = GoogleMapsRealScraper(api_key=API_KEY)

    total_locations = 0
    total_reviews = 0

    for chain_name, search_query, max_per_city in daily_chains:
        print(f"\n📍 Scraping: {chain_name} (query: '{search_query}')")
        print("-"*80)

        try:
            # Scrape selected cities for this chain
            places = scraper.scrape_chain(
                chain_name=search_query,
                cities=daily_cities,
                max_per_city=max_per_city
            )

            if places:
                # Save to database
                locs_added, revs_added = save_to_database(places, chain_name)
                total_locations += locs_added
                total_reviews += revs_added

                place_reviews = sum(len(p['reviews']) for p in places)
                print(f"✅ {chain_name}: {len(places)} locations, {place_reviews} reviews scraped")
                print(f"   → Saved: {locs_added} new locations, {revs_added} new reviews")
            else:
                print(f"⚠️ {chain_name}: No locations found")

        except Exception as e:
            print(f"❌ {chain_name} failed: {e}")
            continue

    print("\n" + "="*80)
    print("✅ DAILY SCRAPER COMPLETE")
    print("="*80)
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total new locations: {total_locations}")
    print(f"Total new reviews: {total_reviews}")
    print("="*80)

if __name__ == "__main__":
    main()
