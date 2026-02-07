#!/usr/bin/env python3
"""
REAL DATA SCRAPER - Google Maps API Integration
System 5.0.1 - Scrapes REAL data from Google Maps for hedge fund intelligence

Author: ReviewSignal Team
Version: 5.0.1
Date: January 2026
"""

import googlemaps
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import structlog
import redis
import json
from dataclasses import dataclass, asdict, field
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════

class BusinessStatus(Enum):
    """Google Maps business status enum"""
    OPERATIONAL = "OPERATIONAL"
    CLOSED_TEMPORARILY = "CLOSED_TEMPORARILY"
    CLOSED_PERMANENTLY = "CLOSED_PERMANENTLY"
    UNKNOWN = "UNKNOWN"


# ═══════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════

@dataclass
class ReviewData:
    """Data class for review information"""
    author_name: str
    rating: int
    text: str
    time: int
    relative_time: str
    language: str
    profile_photo_url: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PlaceData:
    """Data class for place information"""
    place_id: str
    name: str
    address: str
    rating: float
    review_count: int
    latitude: float
    longitude: float
    url: str
    phone: Optional[str]
    website: Optional[str]
    business_status: str
    chain: str
    city: str
    country: str
    reviews: List[Dict] = field(default_factory=list)
    opening_hours: Optional[Dict] = None
    price_level: Optional[int] = None
    types: List[str] = field(default_factory=list)
    data_quality_score: float = 0.0
    scraped_at: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════
# HELPER CLASSES
# ═══════════════════════════════════════════════════════════════

class RateLimiter:
    """Thread-safe rate limiter for API calls"""
    
    def __init__(self, calls_per_second: int = 50):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0.0
        self.lock = threading.Lock()
        self.call_count = 0
    
    def wait(self) -> None:
        """Wait if necessary to respect rate limit"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
            self.last_call = time.time()
            self.call_count += 1
    
    def get_stats(self) -> Dict:
        """Get rate limiter statistics"""
        return {
            "calls_per_second": self.calls_per_second,
            "total_calls": self.call_count,
        }


class CacheManager:
    """Redis cache manager for scraped data"""
    
    def __init__(self, redis_client: redis.Redis, default_ttl: int = 86400):
        self.redis = redis_client
        self.default_ttl = default_ttl  # 24 hours
        self.hits = 0
        self.misses = 0
    
    def _generate_key(self, place_id: str) -> str:
        """Generate cache key for place"""
        return f"place:v5:{place_id}"
    
    def get(self, place_id: str) -> Optional[Dict]:
        """Get cached place data"""
        key = self._generate_key(place_id)
        try:
            data = self.redis.get(key)
            if data:
                self.hits += 1
                return json.loads(data)
            self.misses += 1
            return None
        except redis.RedisError as e:
            logger.error("redis_get_error", error=str(e), place_id=place_id)
            return None
    
    def set(self, place_id: str, data: Dict, ttl: int = None) -> bool:
        """Cache place data"""
        key = self._generate_key(place_id)
        ttl = ttl or self.default_ttl
        try:
            self.redis.setex(key, ttl, json.dumps(data, default=str))
            return True
        except redis.RedisError as e:
            logger.error("redis_set_error", error=str(e), place_id=place_id)
            return False
    
    def delete(self, place_id: str) -> bool:
        """Delete cached place data"""
        key = self._generate_key(place_id)
        try:
            self.redis.delete(key)
            return True
        except redis.RedisError as e:
            logger.error("redis_delete_error", error=str(e), place_id=place_id)
            return False
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total": total,
            "hit_rate_percent": round(hit_rate, 2)
        }


class DataQualityCalculator:
    """Calculate data quality score for places"""
    
    WEIGHTS = {
        'has_rating': 20,
        'has_reviews': 20,
        'is_operational': 15,
        'has_phone': 10,
        'has_website': 10,
        'has_hours': 10,
        'has_photos': 5,
        'has_price_level': 5,
        'review_count_bonus': 5
    }
    
    @staticmethod
    def calculate(place_data: Dict) -> float:
        """Calculate quality score (0-100)"""
        score = 0
        weights = DataQualityCalculator.WEIGHTS
        
        # Rating present
        if place_data.get('rating') and place_data['rating'] > 0:
            score += weights['has_rating']
        
        # Has reviews
        review_count = place_data.get('user_ratings_total', 0)
        if review_count > 0:
            score += weights['has_reviews']
        
        # Review count bonus (more reviews = better data)
        if review_count > 100:
            score += weights['review_count_bonus']
        elif review_count > 50:
            score += weights['review_count_bonus'] * 0.5
        
        # Business operational
        if place_data.get('business_status') == 'OPERATIONAL':
            score += weights['is_operational']
        
        # Has phone
        if place_data.get('formatted_phone_number'):
            score += weights['has_phone']
        
        # Has website
        if place_data.get('website'):
            score += weights['has_website']
        
        # Has opening hours
        if place_data.get('opening_hours'):
            score += weights['has_hours']
        
        # Has photos
        if place_data.get('photos') and len(place_data['photos']) > 0:
            score += weights['has_photos']
        
        # Has price level
        if place_data.get('price_level') is not None:
            score += weights['has_price_level']
        
        return min(score, 100)


# ═══════════════════════════════════════════════════════════════
# MAIN SCRAPER CLASS
# ═══════════════════════════════════════════════════════════════

class GoogleMapsRealScraper:
    """
    Production-ready Google Maps scraper.
    Scrapes REAL data from Google Maps API for hedge fund intelligence.
    """
    
    def __init__(
        self,
        api_key: str,
        redis_url: str = None,
        rate_limit: int = 50,
        cache_ttl: int = 86400,
        max_workers: int = 5
    ):
        """
        Initialize scraper.
        
        Args:
            api_key: Google Maps API key
            redis_url: Redis connection URL (optional)
            rate_limit: Max requests per second (default: 50)
            cache_ttl: Cache TTL in seconds (default: 24h)
            max_workers: Max parallel workers (default: 5)
        """
        self.client = googlemaps.Client(key=api_key)
        self.rate_limiter = RateLimiter(rate_limit)
        self.max_workers = max_workers
        self.quality_calculator = DataQualityCalculator()
        
        # Setup cache if Redis available
        self.cache: Optional[CacheManager] = None
        if redis_url:
            try:
                redis_client = redis.from_url(redis_url)
                redis_client.ping()  # Test connection
                self.cache = CacheManager(redis_client, cache_ttl)
                logger.info("redis_connected", url=redis_url)
            except redis.RedisError as e:
                logger.warning("redis_connection_failed", error=str(e))
        
        logger.info(
            "scraper_initialized",
            rate_limit=rate_limit,
            cache_enabled=self.cache is not None,
            max_workers=max_workers
        )
    
    # ─────────────────────────────────────────────────────────────
    # PUBLIC METHODS
    # ─────────────────────────────────────────────────────────────
    
    def search_places(
        self,
        query: str,
        location: str,
        radius: int = 50000
    ) -> List[PlaceData]:
        """
        Search for places matching query in location.
        
        Args:
            query: Search query (e.g., "Starbucks")
            location: Location string (e.g., "New York, NY, USA")
            radius: Search radius in meters (default: 50km)
        
        Returns:
            List of PlaceData objects
        """
        self.rate_limiter.wait()
        
        try:
            # Geocode location first
            geocode_result = self.client.geocode(location)
            if not geocode_result:
                logger.warning("geocode_failed", location=location)
                return []
            
            lat = geocode_result[0]['geometry']['location']['lat']
            lng = geocode_result[0]['geometry']['location']['lng']
            
            # Search for places
            self.rate_limiter.wait()
            places_result = self.client.places_nearby(
                location=(lat, lng),
                radius=radius,
                keyword=query
                # Removed type='restaurant' filter to support all business types
                # (drugstores, clothing stores, etc.)
            )
            
            places = []
            for place in places_result.get('results', []):
                place_data = self._parse_place_data(
                    place,
                    chain=query,
                    city=location.split(',')[0],
                    country=location.split(',')[-1].strip()
                )
                if place_data:
                    places.append(place_data)
            
            # Handle pagination
            while places_result.get('next_page_token'):
                time.sleep(2)  # Required delay for next_page_token
                self.rate_limiter.wait()
                places_result = self.client.places_nearby(
                    page_token=places_result['next_page_token']
                )
                for place in places_result.get('results', []):
                    place_data = self._parse_place_data(
                        place,
                        chain=query,
                        city=location.split(',')[0],
                        country=location.split(',')[-1].strip()
                    )
                    if place_data:
                        places.append(place_data)
            
            logger.info(
                "search_complete",
                query=query,
                location=location,
                results=len(places)
            )
            return places
            
        except Exception as e:
            logger.error("search_error", query=query, location=location, error=str(e))
            return []
    
    def get_place_details(self, place_id: str) -> Optional[PlaceData]:
        """
        Get detailed information about a place.
        
        Args:
            place_id: Google Place ID
        
        Returns:
            PlaceData object or None
        """
        # Check cache first
        if self.cache:
            cached = self.cache.get(place_id)
            if cached:
                logger.debug("cache_hit", place_id=place_id)
                return PlaceData(**cached)
        
        # Fetch from API
        place_data = self._fetch_from_api(place_id)
        if place_data:
            # Cache the result
            if self.cache:
                self.cache.set(place_id, place_data.to_dict())
        
        return place_data
    
    def get_place_reviews(self, place_id: str) -> List[ReviewData]:
        """
        Get reviews for a place.
        
        Args:
            place_id: Google Place ID
        
        Returns:
            List of ReviewData objects
        """
        place_data = self.get_place_details(place_id)
        if not place_data or not place_data.reviews:
            return []
        
        return [
            ReviewData(**review) if isinstance(review, dict) else review
            for review in place_data.reviews
        ]
    
    def scrape_chain(
        self,
        chain_name: str,
        cities: List[str],
        country: str = None,
        max_per_city: int = 10
    ) -> List[Dict]:
        """
        Scrape all locations of a chain across multiple cities.
        
        Args:
            chain_name: Chain name (e.g., "McDonald's")
            cities: List of city names
            country: Country filter (optional)
            max_per_city: Max locations per city (default: 10)
        
        Returns:
            List of PlaceData objects
        """
        all_places = []
        
        logger.info(
            "chain_scrape_started",
            chain=chain_name,
            cities=len(cities),
            max_per_city=max_per_city
        )
        
        for city in cities:
            try:
                places = self.search_places(chain_name, city)
                places = places[:max_per_city]
                
                # Get detailed info for each place
                for place in places:
                    detailed = self.get_place_details(place.place_id)
                    if detailed:
                        all_places.append(detailed)
                
                logger.info(
                    "city_scraped",
                    chain=chain_name,
                    city=city,
                    locations=len(places)
                )
                
            except Exception as e:
                logger.error(
                    "city_scrape_error",
                    chain=chain_name,
                    city=city,
                    error=str(e)
                )
                continue
        
        logger.info(
            "chain_scrape_complete",
            chain=chain_name,
            total_locations=len(all_places)
        )

        return [place.to_dict() for place in all_places]
    
    def scrape_by_coordinates(
        self,
        lat: float,
        lng: float,
        radius: int = 5000,
        query: str = None
    ) -> List[PlaceData]:
        """
        Scrape places by coordinates.
        
        Args:
            lat: Latitude
            lng: Longitude
            radius: Search radius in meters
            query: Search query (optional)
        
        Returns:
            List of PlaceData objects
        """
        self.rate_limiter.wait()
        
        try:
            if query:
                places_result = self.client.places_nearby(
                    location=(lat, lng),
                    radius=radius,
                    keyword=query
                )
            else:
                places_result = self.client.places_nearby(
                    location=(lat, lng),
                    radius=radius,
                    type='restaurant'
                )
            
            places = []
            for place in places_result.get('results', []):
                place_data = self._parse_place_data(
                    place,
                    chain=query or "Unknown",
                    city="Coordinates",
                    country="Unknown"
                )
                if place_data:
                    places.append(place_data)
            
            return places
            
        except Exception as e:
            logger.error("coordinate_scrape_error", lat=lat, lng=lng, error=str(e))
            return []
    
    # ─────────────────────────────────────────────────────────────
    # PRIVATE METHODS
    # ─────────────────────────────────────────────────────────────
    
    def _fetch_from_api(self, place_id: str) -> Optional[PlaceData]:
        """Fetch place details from Google Maps API"""
        self.rate_limiter.wait()
        
        try:
            result = self.client.place(
                place_id,
                fields=[
                    'place_id', 'name', 'formatted_address', 'rating',
                    'user_ratings_total', 'geometry', 'url',
                    'formatted_phone_number', 'website', 'business_status',
                    'opening_hours', 'price_level', 'reviews'
                ]
            )
            
            if not result or 'result' not in result:
                return None
            
            raw_data = result['result']
            
            # Parse reviews
            reviews = self._parse_reviews(raw_data.get('reviews', []))
            
            # Calculate quality score
            quality_score = DataQualityCalculator.calculate(raw_data)
            
            place_data = PlaceData(
                place_id=raw_data.get('place_id', place_id),
                name=raw_data.get('name', ''),
                address=raw_data.get('formatted_address', ''),
                rating=raw_data.get('rating', 0.0),
                review_count=raw_data.get('user_ratings_total', 0),
                latitude=raw_data.get('geometry', {}).get('location', {}).get('lat', 0),
                longitude=raw_data.get('geometry', {}).get('location', {}).get('lng', 0),
                url=raw_data.get('url', ''),
                phone=raw_data.get('formatted_phone_number'),
                website=raw_data.get('website'),
                business_status=raw_data.get('business_status', 'UNKNOWN'),
                chain='',  # Will be set by caller
                city='',   # Will be set by caller
                country='',  # Will be set by caller
                reviews=[r.to_dict() for r in reviews],
                opening_hours=raw_data.get('opening_hours'),
                price_level=raw_data.get('price_level'),
                types=[],
                data_quality_score=quality_score,
                scraped_at=datetime.utcnow().isoformat()
            )
            
            logger.debug(
                "place_fetched",
                place_id=place_id,
                name=place_data.name,
                rating=place_data.rating,
                review_count=place_data.review_count
            )
            
            return place_data
            
        except Exception as e:
            logger.error("api_fetch_error", place_id=place_id, error=str(e))
            return None
    
    def _parse_place_data(
        self,
        raw_data: Dict,
        chain: str,
        city: str,
        country: str
    ) -> Optional[PlaceData]:
        """Parse raw API data into PlaceData object"""
        try:
            quality_score = DataQualityCalculator.calculate(raw_data)
            
            return PlaceData(
                place_id=raw_data.get('place_id', ''),
                name=raw_data.get('name', ''),
                address=raw_data.get('vicinity', raw_data.get('formatted_address', '')),
                rating=raw_data.get('rating', 0.0),
                review_count=raw_data.get('user_ratings_total', 0),
                latitude=raw_data.get('geometry', {}).get('location', {}).get('lat', 0),
                longitude=raw_data.get('geometry', {}).get('location', {}).get('lng', 0),
                url=f"https://maps.google.com/?cid={raw_data.get('place_id', '')}",
                phone=raw_data.get('formatted_phone_number'),
                website=raw_data.get('website'),
                business_status=raw_data.get('business_status', 'OPERATIONAL'),
                chain=chain,
                city=city,
                country=country,
                reviews=[],
                opening_hours=raw_data.get('opening_hours'),
                price_level=raw_data.get('price_level'),
                types=[],
                data_quality_score=quality_score,
                scraped_at=datetime.utcnow().isoformat()
            )
        except Exception as e:
            logger.error("parse_error", error=str(e))
            return None
    
    def _parse_reviews(self, raw_reviews: List[Dict]) -> List[ReviewData]:
        """Parse raw reviews into ReviewData objects"""
        reviews = []
        for raw in raw_reviews:
            try:
                review = ReviewData(
                    author_name=raw.get('author_name', 'Anonymous'),
                    rating=raw.get('rating', 0),
                    text=raw.get('text', ''),
                    time=raw.get('time', 0),
                    relative_time=raw.get('relative_time_description', ''),
                    language=raw.get('language', 'en'),
                    profile_photo_url=raw.get('profile_photo_url')
                )
                reviews.append(review)
            except Exception as e:
                logger.warning("review_parse_error", error=str(e))
                continue
        return reviews
    
    def _batch_scrape(self, place_ids: List[str]) -> List[PlaceData]:
        """Batch scrape multiple places using thread pool"""
        places = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_id = {
                executor.submit(self.get_place_details, pid): pid
                for pid in place_ids
            }
            
            for future in as_completed(future_to_id):
                place_id = future_to_id[future]
                try:
                    place = future.result()
                    if place:
                        places.append(place)
                except Exception as e:
                    logger.error("batch_scrape_error", place_id=place_id, error=str(e))
        
        return places
    
    def get_stats(self) -> Dict:
        """Get scraper statistics"""
        stats = {
            "rate_limiter": self.rate_limiter.get_stats(),
            "cache_enabled": self.cache is not None,
        }
        if self.cache:
            stats["cache"] = self.cache.get_stats()
        return stats


# ═══════════════════════════════════════════════════════════════
# CLI / MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os
    from config import GOOGLE_MAPS_API_KEY, REDIS_URL, CHAINS, ALL_CITIES
    
    # Initialize scraper
    scraper = GoogleMapsRealScraper(
        api_key=GOOGLE_MAPS_API_KEY,
        redis_url=REDIS_URL,
        rate_limit=50,
        max_workers=5
    )
    
    # Example: Scrape Starbucks in New York
    print("\n" + "="*60)
    print("🚀 REVIEWSIGNAL SCRAPER - TEST RUN")
    print("="*60)
    
    places = scraper.scrape_chain(
        chain_name="Starbucks",
        cities=["New York, NY, USA"],
        max_per_city=5
    )
    
    for place in places:
        print(f"  ✓ {place.name}: {place.rating}★ ({place.review_count} reviews)")
    
    print("\n" + "="*60)
    print(f"✅ Scraped {len(places)} locations")
    print(f"📊 Stats: {scraper.get_stats()}")
    print("="*60)
