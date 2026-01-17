#!/usr/bin/env python3
"""
ReviewSignal Configuration - FULL PRODUCTION VERSION
Global coverage: USA, Canada, Europe, Asia, Australia
58 chains, 111 cities

Author: ReviewSignal Team
Version: 5.0
Date: January 2026
"""

import os
from typing import List, Dict

# ═══════════════════════════════════════════════════════════════
# DATABASE CONFIGURATION
# ═══════════════════════════════════════════════════════════════

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'reviewsignal')
DB_USER = os.getenv('DB_USER', 'reviewsignal')
DB_PASS = os.getenv('DB_PASS', 'reviewsignal2026')

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ═══════════════════════════════════════════════════════════════
# REDIS CONFIGURATION
# ═══════════════════════════════════════════════════════════════

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CACHE_TTL = 86400  # 24 hours

# ═══════════════════════════════════════════════════════════════
# API KEYS
# ═══════════════════════════════════════════════════════════════

GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
STRIPE_API_KEY = os.getenv('STRIPE_API_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-jwt-key-min-32-chars')

# ═══════════════════════════════════════════════════════════════
# SCRAPING CONFIGURATION
# ═══════════════════════════════════════════════════════════════

SCRAPE_DELAY_MIN = 1.0  # seconds
SCRAPE_DELAY_MAX = 3.0  # seconds
MAX_RETRIES = 3
TIMEOUT = 30  # seconds
MAX_LOCATIONS_PER_CITY = 10
HEADLESS = True
RATE_LIMIT = 50  # requests per second

# ═══════════════════════════════════════════════════════════════
# 58 GLOBAL CHAINS - Restaurant & Retail
# ═══════════════════════════════════════════════════════════════

CHAINS: List[str] = [
    # ☕ Coffee & Bakery
    "Starbucks",
    "Dunkin'",
    "Tim Hortons",
    "Costa Coffee",
    "Pret A Manger",
    "Panera Bread",
    
    # 🍔 Fast Food - Burgers
    "McDonald's",
    "Burger King",
    "Wendy's",
    "Five Guys",
    "Shake Shack",
    "In-N-Out Burger",
    "Carl's Jr.",
    "Jack in the Box",
    "Whataburger",
    
    # 🍕 Pizza
    "Domino's Pizza",
    "Pizza Hut",
    "Papa John's",
    "Little Caesars",
    
    # 🌮 Mexican
    "Chipotle",
    "Taco Bell",
    "Qdoba",
    "Del Taco",
    
    # 🍗 Chicken
    "Chick-fil-A",
    "KFC",
    "Popeyes",
    "Wingstop",
    "Raising Cane's",
    
    # 🥪 Sandwiches & Subs
    "Subway",
    "Jersey Mike's",
    "Jimmy John's",
    "Firehouse Subs",
    
    # 🍜 Asian
    "Panda Express",
    "P.F. Chang's",
    
    # 🍽️ Casual Dining
    "Applebee's",
    "Chili's",
    "TGI Friday's",
    "Olive Garden",
    "Red Lobster",
    "Outback Steakhouse",
    "Buffalo Wild Wings",
    "Denny's",
    "IHOP",
    "Cracker Barrel",
    "Cheesecake Factory",
    
    # 🍦 Desserts & Treats
    "Dairy Queen",
    "Baskin-Robbins",
    "Cold Stone Creamery",
    "Krispy Kreme",
    
    # 🛒 Retail & Convenience
    "Walmart",
    "Target",
    "Costco",
    "7-Eleven",
    "Walgreens",
    "CVS",
    
    # 🇪🇺 European Chains
    "Vapiano",
    "Nordsee",
    "PAUL",
    "Le Pain Quotidien",
]

# ═══════════════════════════════════════════════════════════════
# 111 GLOBAL CITIES
# ═══════════════════════════════════════════════════════════════

# 🇺🇸 USA - 30 cities
USA_CITIES: List[str] = [
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
    "Fort Worth, TX, USA",
    "Columbus, OH, USA",
    "Charlotte, NC, USA",
    "San Francisco, CA, USA",
    "Indianapolis, IN, USA",
    "Seattle, WA, USA",
    "Denver, CO, USA",
    "Washington, DC, USA",
    "Boston, MA, USA",
    "Nashville, TN, USA",
    "Detroit, MI, USA",
    "Portland, OR, USA",
    "Las Vegas, NV, USA",
    "Miami, FL, USA",
    "Atlanta, GA, USA",
    "Minneapolis, MN, USA",
    "New Orleans, LA, USA",
    "Cleveland, OH, USA",
]

# 🇨🇦 Canada - 10 cities
CANADA_CITIES: List[str] = [
    "Toronto, ON, Canada",
    "Montreal, QC, Canada",
    "Vancouver, BC, Canada",
    "Calgary, AB, Canada",
    "Edmonton, AB, Canada",
    "Ottawa, ON, Canada",
    "Winnipeg, MB, Canada",
    "Quebec City, QC, Canada",
    "Hamilton, ON, Canada",
    "Victoria, BC, Canada",
]

# 🇬🇧 United Kingdom - 10 cities
UK_CITIES: List[str] = [
    "London, UK",
    "Birmingham, UK",
    "Manchester, UK",
    "Glasgow, UK",
    "Liverpool, UK",
    "Bristol, UK",
    "Sheffield, UK",
    "Leeds, UK",
    "Edinburgh, UK",
    "Cardiff, UK",
]

# 🇩🇪 Germany - 10 cities
GERMANY_CITIES: List[str] = [
    "Berlin, Germany",
    "Munich, Germany",
    "Hamburg, Germany",
    "Frankfurt, Germany",
    "Cologne, Germany",
    "Düsseldorf, Germany",
    "Stuttgart, Germany",
    "Dortmund, Germany",
    "Essen, Germany",
    "Leipzig, Germany",
]

# 🇫🇷 France - 8 cities
FRANCE_CITIES: List[str] = [
    "Paris, France",
    "Marseille, France",
    "Lyon, France",
    "Toulouse, France",
    "Nice, France",
    "Nantes, France",
    "Strasbourg, France",
    "Bordeaux, France",
]

# 🇪🇸 Spain - 6 cities
SPAIN_CITIES: List[str] = [
    "Madrid, Spain",
    "Barcelona, Spain",
    "Valencia, Spain",
    "Seville, Spain",
    "Bilbao, Spain",
    "Malaga, Spain",
]

# 🇮🇹 Italy - 6 cities
ITALY_CITIES: List[str] = [
    "Rome, Italy",
    "Milan, Italy",
    "Naples, Italy",
    "Turin, Italy",
    "Florence, Italy",
    "Venice, Italy",
]

# 🇳🇱🇧🇪🇦🇹🇨🇭 Benelux + Alps - 8 cities
BENELUX_ALPS_CITIES: List[str] = [
    "Amsterdam, Netherlands",
    "Rotterdam, Netherlands",
    "Brussels, Belgium",
    "Antwerp, Belgium",
    "Vienna, Austria",
    "Zurich, Switzerland",
    "Geneva, Switzerland",
    "Luxembourg City, Luxembourg",
]

# 🇵🇱🇨🇿🇸🇪 Other EU - 10 cities
OTHER_EU_CITIES: List[str] = [
    "Warsaw, Poland",
    "Krakow, Poland",
    "Prague, Czech Republic",
    "Stockholm, Sweden",
    "Copenhagen, Denmark",
    "Oslo, Norway",
    "Helsinki, Finland",
    "Dublin, Ireland",
    "Lisbon, Portugal",
    "Athens, Greece",
]

# 🇦🇺🇳🇿 Oceania - 7 cities
OCEANIA_CITIES: List[str] = [
    "Sydney, Australia",
    "Melbourne, Australia",
    "Brisbane, Australia",
    "Perth, Australia",
    "Adelaide, Australia",
    "Auckland, New Zealand",
    "Wellington, New Zealand",
]

# 🇯🇵🇰🇷🇸🇬 Asia - 10 cities
ASIA_CITIES: List[str] = [
    "Tokyo, Japan",
    "Osaka, Japan",
    "Seoul, South Korea",
    "Busan, South Korea",
    "Singapore",
    "Hong Kong",
    "Taipei, Taiwan",
    "Bangkok, Thailand",
    "Kuala Lumpur, Malaysia",
    "Jakarta, Indonesia",
]

# Combined list of all 111 cities
ALL_CITIES: List[str] = (
    USA_CITIES +
    CANADA_CITIES +
    UK_CITIES +
    GERMANY_CITIES +
    FRANCE_CITIES +
    SPAIN_CITIES +
    ITALY_CITIES +
    BENELUX_ALPS_CITIES +
    OTHER_EU_CITIES +
    OCEANIA_CITIES +
    ASIA_CITIES
)

# City to country mapping
CITY_COUNTRY_MAP: Dict[str, str] = {}
for city in USA_CITIES:
    CITY_COUNTRY_MAP[city] = "USA"
for city in CANADA_CITIES:
    CITY_COUNTRY_MAP[city] = "Canada"
for city in UK_CITIES:
    CITY_COUNTRY_MAP[city] = "UK"
for city in GERMANY_CITIES:
    CITY_COUNTRY_MAP[city] = "Germany"
for city in FRANCE_CITIES:
    CITY_COUNTRY_MAP[city] = "France"
for city in SPAIN_CITIES:
    CITY_COUNTRY_MAP[city] = "Spain"
for city in ITALY_CITIES:
    CITY_COUNTRY_MAP[city] = "Italy"
for city in BENELUX_ALPS_CITIES:
    country = city.split(", ")[-1]
    CITY_COUNTRY_MAP[city] = country
for city in OTHER_EU_CITIES:
    country = city.split(", ")[-1]
    CITY_COUNTRY_MAP[city] = country
for city in OCEANIA_CITIES:
    country = city.split(", ")[-1] if ", " in city else city
    CITY_COUNTRY_MAP[city] = country
for city in ASIA_CITIES:
    country = city.split(", ")[-1] if ", " in city else city
    CITY_COUNTRY_MAP[city] = country

# ═══════════════════════════════════════════════════════════════
# TARGET COMPANIES - Hedge Funds & PE Firms
# ═══════════════════════════════════════════════════════════════

TIER_1_COMPANIES: List[str] = [
    # Top Hedge Funds
    "Citadel",
    "Bridgewater Associates",
    "Renaissance Technologies",
    "Two Sigma",
    "D.E. Shaw",
    "Millennium Management",
    "Point72",
    "AQR Capital",
    "Man Group",
    "Baupost Group",
    "Elliott Management",
    
    # Top Private Equity
    "Blackstone",
    "KKR",
    "Carlyle Group",
    "Apollo Global",
    "TPG Capital",
    "Warburg Pincus",
    "Advent International",
    "Bain Capital",
    
    # Major Banks (Alt Data divisions)
    "Goldman Sachs",
    "Morgan Stanley",
    "JP Morgan",
    "BlackRock",
    "Vanguard",
    "Fidelity",
    "State Street",
]

TIER_2_COMPANIES: List[str] = [
    "Viking Global",
    "Lone Pine Capital",
    "Tiger Global",
    "Coatue Management",
    "Third Point",
    "Pershing Square",
    "Greenlight Capital",
    "Och-Ziff",
    "Canyon Capital",
    "Cerberus Capital",
    "Fortress Investment",
    "Oaktree Capital",
    "PIMCO",
    "Wellington Management",
    "Capital Group",
]

# ═══════════════════════════════════════════════════════════════
# PRICING TIERS (EUR)
# ═══════════════════════════════════════════════════════════════

PRICING_TIERS: Dict[str, Dict] = {
    "trial": {
        "name": "Trial",
        "price_eur": 0,
        "duration_days": 14,
        "api_calls_limit": 100,
        "reports_limit": 5,
        "cities_limit": 1,
    },
    "starter": {
        "name": "Starter",
        "price_eur": 2500,
        "interval": "month",
        "api_calls_limit": 1000,
        "reports_limit": 50,
        "cities_limit": 5,
    },
    "pro": {
        "name": "Pro",
        "price_eur": 5000,
        "interval": "month",
        "api_calls_limit": 10000,
        "reports_limit": 500,
        "cities_limit": 30,
    },
    "enterprise": {
        "name": "Enterprise",
        "price_eur": 10000,
        "interval": "month",
        "api_calls_limit": -1,  # Unlimited
        "reports_limit": -1,   # Unlimited
        "cities_limit": -1,    # All cities
    },
}

# ═══════════════════════════════════════════════════════════════
# STATISTICS
# ═══════════════════════════════════════════════════════════════

print(f"""
═══════════════════════════════════════════════════════════════
🚀 REVIEWSIGNAL CONFIGURATION LOADED
═══════════════════════════════════════════════════════════════
   Chains:              {len(CHAINS)}
   Cities:              {len(ALL_CITIES)}
   Max locations/city:  {MAX_LOCATIONS_PER_CITY}
   Potential coverage:  {len(CHAINS) * len(ALL_CITIES) * MAX_LOCATIONS_PER_CITY:,} locations
   
   Tier 1 Targets:      {len(TIER_1_COMPANIES)} companies
   Tier 2 Targets:      {len(TIER_2_COMPANIES)} companies
═══════════════════════════════════════════════════════════════
""")
