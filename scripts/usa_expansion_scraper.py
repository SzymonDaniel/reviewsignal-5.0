#!/usr/bin/env python3
"""
USA EXPANSION SCRAPER - Masowe pobieranie lokalizacji USA
System 5.0 - Casual Dining, Drugstores, Grocery

Cel: 10,000+ nowych lokalizacji w USA
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from modules.real_scraper import GoogleMapsRealScraper
import psycopg2
from psycopg2.extras import RealDictCursor
import structlog
from typing import List, Dict
import time
from datetime import datetime

logger = structlog.get_logger()

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "reviewsignal",
    "user": "reviewsignal",
    "password": os.getenv("DB_PASS")
}

# Top 50 miast USA dla maksymalnego pokrycia
USA_CITIES = [
    "New York, NY, USA", "Los Angeles, CA, USA", "Chicago, IL, USA",
    "Houston, TX, USA", "Phoenix, AZ, USA", "Philadelphia, PA, USA",
    "San Antonio, TX, USA", "San Diego, CA, USA", "Dallas, TX, USA",
    "San Jose, CA, USA", "Austin, TX, USA", "Jacksonville, FL, USA",
    "Fort Worth, TX, USA", "Columbus, OH, USA", "Charlotte, NC, USA",
    "San Francisco, CA, USA", "Indianapolis, IN, USA", "Seattle, WA, USA",
    "Denver, CO, USA", "Washington, DC, USA", "Boston, MA, USA",
    "El Paso, TX, USA", "Nashville, TN, USA", "Detroit, MI, USA",
    "Oklahoma City, OK, USA", "Portland, OR, USA", "Las Vegas, NV, USA",
    "Memphis, TN, USA", "Louisville, KY, USA", "Baltimore, MD, USA",
    "Milwaukee, WI, USA", "Albuquerque, NM, USA", "Tucson, AZ, USA",
    "Fresno, CA, USA", "Mesa, AZ, USA", "Sacramento, CA, USA",
    "Atlanta, GA, USA", "Kansas City, MO, USA", "Colorado Springs, CO, USA",
    "Omaha, NE, USA", "Raleigh, NC, USA", "Miami, FL, USA",
    "Long Beach, CA, USA", "Virginia Beach, VA, USA", "Oakland, CA, USA",
    "Minneapolis, MN, USA", "Tulsa, OK, USA", "Tampa, FL, USA",
    "Arlington, TX, USA", "New Orleans, LA, USA"
]

# CASUAL DINING CHAINS (14 sieci)
CASUAL_DINING_CHAINS = [
    "Applebee's", "Buffalo Wild Wings", "Chili's Grill & Bar",
    "Chipotle Mexican Grill", "Cracker Barrel", "Denny's",
    "IHOP", "Olive Garden", "Outback Steakhouse",
    "Red Lobster", "TGI Friday's", "Texas Roadhouse",
    "The Cheesecake Factory", "Panera Bread"
]

# DRUGSTORES & PHARMACY
DRUGSTORE_CHAINS = [
    "CVS Pharmacy", "Walgreens", "Rite Aid", "Duane Reade"
]

# GROCERY STORES (USA specific)
GROCERY_CHAINS = [
    "Whole Foods Market", "Trader Joe's", "Kroger",
    "Safeway", "Publix", "H-E-B", "Wegmans"
]

# ═══════════════════════════════════════════════════════════════
# DATABASE FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def get_db_connection():
    """Get PostgreSQL connection"""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

def get_or_create_chain(conn, chain_name: str, category: str) -> int:
    """Get chain_id or create new chain"""
    with conn.cursor() as cur:
        # Try to find existing
        cur.execute(
            "SELECT id FROM chains WHERE name = %s",
            (chain_name,)
        )
        result = cur.fetchone()

        if result:
            return result['id']

        # Create new
        cur.execute(
            """
            INSERT INTO chains (name, category, search_query)
            VALUES (%s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET category = EXCLUDED.category
            RETURNING id
            """,
            (chain_name, category, chain_name)
        )
        conn.commit()
        return cur.fetchone()['id']

def save_location_to_db(conn, place_data: Dict, chain_id: int):
    """Save location to database"""
    with conn.cursor() as cur:
        # Check if already exists
        cur.execute(
            "SELECT id FROM locations WHERE place_id = %s",
            (place_data['place_id'],)
        )
        if cur.fetchone():
            logger.info("location_exists", place_id=place_data['place_id'])
            return

        # Insert new location
        cur.execute(
            """
            INSERT INTO locations (
                chain_id, place_id, name, address, city, country,
                latitude, longitude, rating, review_count, chain_name,
                phone, website, opening_hours, business_status,
                data_quality_score, source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (place_id) DO NOTHING
            """,
            (
                chain_id,
                place_data['place_id'],
                place_data['name'],
                place_data['address'],
                place_data['city'],
                place_data['country'],
                place_data['latitude'],
                place_data['longitude'],
                place_data['rating'],
                place_data['review_count'],
                place_data['chain'],
                place_data.get('phone'),
                place_data.get('website'),
                str(place_data.get('opening_hours', {})),
                place_data['business_status'],
                place_data['data_quality_score'],
                'google_maps'
            )
        )
        conn.commit()
        logger.info(
            "location_saved",
            chain=place_data['chain'],
            city=place_data['city'],
            name=place_data['name']
        )

# ═══════════════════════════════════════════════════════════════
# SCRAPING FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def scrape_chain_category(
    scraper: GoogleMapsRealScraper,
    chains: List[str],
    category: str,
    cities: List[str],
    max_per_city: int = 5
):
    """Scrape entire category of chains"""
    conn = get_db_connection()
    total_scraped = 0

    logger.info(
        "category_scrape_started",
        category=category,
        chains=len(chains),
        cities=len(cities)
    )

    for chain_name in chains:
        logger.info("chain_started", chain=chain_name)

        # Get or create chain
        chain_id = get_or_create_chain(conn, chain_name, category)

        # Scrape cities
        for city in cities:
            try:
                places = scraper.search_places(chain_name, city)
                places = places[:max_per_city]

                for place in places:
                    try:
                        # Get detailed data
                        detailed = scraper.get_place_details(place.place_id)
                        if detailed:
                            save_location_to_db(conn, detailed.to_dict(), chain_id)
                            total_scraped += 1

                            # Rate limiting progress report
                            if total_scraped % 50 == 0:
                                logger.info(
                                    "progress_update",
                                    total_scraped=total_scraped,
                                    current_chain=chain_name,
                                    current_city=city
                                )
                    except Exception as e:
                        logger.error(
                            "place_save_error",
                            place_id=place.place_id,
                            error=str(e)
                        )
                        continue

                # Small delay between cities
                time.sleep(0.5)

            except Exception as e:
                logger.error(
                    "city_scrape_error",
                    chain=chain_name,
                    city=city,
                    error=str(e)
                )
                continue

        logger.info(
            "chain_completed",
            chain=chain_name,
            total_locations=total_scraped
        )

    conn.close()

    logger.info(
        "category_scrape_completed",
        category=category,
        total_locations=total_scraped
    )

    return total_scraped

# ═══════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════

def main():
    """Main scraping orchestrator"""
    start_time = datetime.now()

    logger.info(
        "usa_expansion_started",
        target="10,000+ locations",
        cities=len(USA_CITIES),
        timestamp=start_time.isoformat()
    )

    # Initialize scraper
    scraper = GoogleMapsRealScraper(
        api_key=GOOGLE_MAPS_API_KEY,
        redis_url="redis://localhost:6379/0",
        rate_limit=50,  # 50 requests/second
        max_workers=5
    )

    total_locations = 0

    # 1. CASUAL DINING (Priorytet #1)
    logger.info("=== PHASE 1: CASUAL DINING ===")
    casual_dining_count = scrape_chain_category(
        scraper=scraper,
        chains=CASUAL_DINING_CHAINS,
        category="casual_dining",
        cities=USA_CITIES,
        max_per_city=5  # 14 chains × 50 cities × 5 = ~3,500 locations
    )
    total_locations += casual_dining_count

    # 2. DRUGSTORES & PHARMACY (Priorytet #2)
    logger.info("=== PHASE 2: DRUGSTORES & PHARMACY ===")
    drugstore_count = scrape_chain_category(
        scraper=scraper,
        chains=DRUGSTORE_CHAINS,
        category="drugstore",
        cities=USA_CITIES,
        max_per_city=10  # 4 chains × 50 cities × 10 = ~2,000 locations
    )
    total_locations += drugstore_count

    # 3. GROCERY STORES (Priorytet #3)
    logger.info("=== PHASE 3: GROCERY STORES ===")
    grocery_count = scrape_chain_category(
        scraper=scraper,
        chains=GROCERY_CHAINS,
        category="grocery",
        cities=USA_CITIES,
        max_per_city=8  # 7 chains × 50 cities × 8 = ~2,800 locations
    )
    total_locations += grocery_count

    # FINAL REPORT
    duration = datetime.now() - start_time

    logger.info(
        "usa_expansion_completed",
        total_locations=total_locations,
        casual_dining=casual_dining_count,
        drugstores=drugstore_count,
        grocery=grocery_count,
        duration_minutes=duration.total_seconds() / 60,
        timestamp=datetime.now().isoformat()
    )

    print("\n" + "="*70)
    print("USA EXPANSION SCRAPING COMPLETED!")
    print("="*70)
    print(f"Total New Locations: {total_locations:,}")
    print(f"  - Casual Dining:   {casual_dining_count:,}")
    print(f"  - Drugstores:      {drugstore_count:,}")
    print(f"  - Grocery:         {grocery_count:,}")
    print(f"Duration: {duration.total_seconds() / 60:.1f} minutes")
    print("="*70)

if __name__ == "__main__":
    main()
