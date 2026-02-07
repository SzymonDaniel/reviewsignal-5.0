#!/usr/bin/env python3
"""
Yelp Fusion API Scraper for ReviewSignal.ai

Scrapes business data and reviews from the Yelp Fusion API (v3).
Follows the same patterns as modules/real_scraper.py (Google Maps scraper).

API Limits (free tier):
    - 5,000 API calls/day
    - 3 reviews per business (API hard limit, excerpts only)
    - 50 businesses per search request

Features:
    - Rate limiting (max 5 req/s, daily budget tracking)
    - Redis caching (24h TTL for details, 6h for reviews)
    - Retry with exponential backoff on 429/500 errors
    - Structured logging (structlog)
    - Data validation via modules/data_validator.py
    - Auto sentiment scoring for reviews (VADER)
    - Returns data compatible with the ReviewSignal reviews table

Author: ReviewSignal Team
Version: 1.0.0
Date: February 2026
"""

import hashlib
import json
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

import redis
import requests
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger()

# Yelp Fusion API base URL
YELP_API_BASE = "https://api.yelp.com/v3"

# Daily call budget (free tier)
YELP_DAILY_LIMIT = 5000

# Cache TTL constants
CACHE_TTL_DETAILS = 86400   # 24 hours for business details
CACHE_TTL_REVIEWS = 21600   # 6 hours for reviews
CACHE_TTL_SEARCH = 3600     # 1 hour for search results


# ===================================================================
# ENUMS
# ===================================================================

class YelpSortMode(str, Enum):
    """Sort modes for Yelp business search."""
    BEST_MATCH = "best_match"
    RATING = "rating"
    REVIEW_COUNT = "review_count"
    DISTANCE = "distance"


class YelpPriceLevel(str, Enum):
    """Yelp price levels ($, $$, $$$, $$$$)."""
    INEXPENSIVE = "$"
    MODERATE = "$$"
    PRICEY = "$$$"
    ULTRA_HIGH_END = "$$$$"


# ===================================================================
# DATACLASSES
# ===================================================================

@dataclass
class YelpBusiness:
    """Data class for a Yelp business."""

    id: str
    name: str
    address: str
    city: str
    state: str
    country: str
    zip_code: str
    rating: float
    review_count: int
    categories: List[str]
    latitude: float
    longitude: float
    phone: str
    url: str
    price: Optional[str] = None
    image_url: Optional[str] = None
    is_closed: bool = False
    data_quality_score: float = 0.0
    scraped_at: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

    @property
    def price_level(self) -> Optional[int]:
        """Convert Yelp price string to numeric level (1-4)."""
        if self.price is None:
            return None
        return len(self.price)  # $ -> 1, $$ -> 2, $$$ -> 3, $$$$ -> 4


@dataclass
class YelpReview:
    """Data class for a Yelp review."""

    id: str
    text: str
    rating: int
    time_created: str
    user_name: str
    user_image_url: Optional[str] = None
    url: Optional[str] = None
    sentiment_score: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

    def to_review_table_dict(
        self,
        location_id: str,
        yelp_business_id: str,
    ) -> Dict:
        """Convert to a dict matching the ReviewSignal reviews table schema.

        Args:
            location_id: The ReviewSignal location_id this review belongs to.
            yelp_business_id: The Yelp business ID for reference.

        Returns:
            Dict ready for insertion into the reviews table.
        """
        # Generate a deterministic review_id from the Yelp review ID
        review_id = f"yelp_{self.id}"

        # Parse time_created (Yelp format: "2026-01-15 12:34:56")
        review_time = None
        if self.time_created:
            try:
                review_time = datetime.strptime(
                    self.time_created, "%Y-%m-%d %H:%M:%S"
                )
            except ValueError:
                pass

        return {
            "review_id": review_id,
            "location_id": location_id,
            "author_name": self.user_name or "Anonymous",
            "rating": self.rating,
            "text": self.text or "",
            "language": "en",  # Yelp API returns English reviews by default
            "sentiment_score": self.sentiment_score,
            "sentiment_label": _sentiment_label(self.sentiment_score),
            "review_time": review_time,
            "source": "yelp",
        }


def _sentiment_label(score: Optional[float]) -> Optional[str]:
    """Convert sentiment score to label."""
    if score is None:
        return None
    if score >= 0.05:
        return "positive"
    if score <= -0.05:
        return "negative"
    return "neutral"


# ===================================================================
# RATE LIMITER (with daily budget tracking)
# ===================================================================

class YelpRateLimiter:
    """Thread-safe rate limiter with daily budget tracking.

    Enforces both per-second rate limits and a daily API call budget.
    """

    def __init__(
        self,
        calls_per_second: int = 5,
        daily_limit: int = YELP_DAILY_LIMIT,
    ):
        self.calls_per_second = calls_per_second
        self.daily_limit = daily_limit
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0.0
        self.lock = threading.Lock()
        self.call_count = 0
        self.daily_count = 0
        self.day_start = datetime.utcnow().date()

    def wait(self) -> None:
        """Wait if necessary to respect rate limit. Raises if daily budget exceeded."""
        with self.lock:
            today = datetime.utcnow().date()
            if today != self.day_start:
                self.daily_count = 0
                self.day_start = today

            if self.daily_count >= self.daily_limit:
                raise YelpDailyLimitExceeded(
                    f"Yelp daily API limit reached: {self.daily_count}/{self.daily_limit}"
                )

            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)

            self.last_call = time.time()
            self.call_count += 1
            self.daily_count += 1

    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        return {
            "calls_per_second": self.calls_per_second,
            "total_calls": self.call_count,
            "daily_calls": self.daily_count,
            "daily_limit": self.daily_limit,
            "daily_remaining": max(0, self.daily_limit - self.daily_count),
        }


# ===================================================================
# CACHE MANAGER (Yelp-specific keys)
# ===================================================================

class YelpCacheManager:
    """Redis cache manager for Yelp data."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.hits = 0
        self.misses = 0

    def _key(self, prefix: str, identifier: str) -> str:
        """Generate a namespaced cache key."""
        return f"yelp:{prefix}:{identifier}"

    def get(self, prefix: str, identifier: str) -> Optional[Dict]:
        """Get cached data."""
        key = self._key(prefix, identifier)
        try:
            data = self.redis.get(key)
            if data:
                self.hits += 1
                return json.loads(data)
            self.misses += 1
            return None
        except redis.RedisError as e:
            logger.error("yelp_cache_get_error", error=str(e), key=key)
            return None

    def set(self, prefix: str, identifier: str, data: Dict, ttl: int) -> bool:
        """Cache data with TTL."""
        key = self._key(prefix, identifier)
        try:
            self.redis.setex(key, ttl, json.dumps(data, default=str))
            return True
        except redis.RedisError as e:
            logger.error("yelp_cache_set_error", error=str(e), key=key)
            return False

    def delete(self, prefix: str, identifier: str) -> bool:
        """Delete cached data."""
        key = self._key(prefix, identifier)
        try:
            self.redis.delete(key)
            return True
        except redis.RedisError as e:
            logger.error("yelp_cache_delete_error", error=str(e), key=key)
            return False

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total": total,
            "hit_rate_percent": round(hit_rate, 2),
        }


# ===================================================================
# DATA QUALITY CALCULATOR
# ===================================================================

class YelpDataQualityCalculator:
    """Calculate data quality score (0-100) for Yelp businesses."""

    WEIGHTS = {
        "has_rating": 20,
        "has_reviews": 20,
        "is_open": 15,
        "has_phone": 10,
        "has_categories": 10,
        "has_address": 10,
        "has_price": 5,
        "has_image": 5,
        "review_count_bonus": 5,
    }

    @staticmethod
    def calculate(business_data: Dict) -> float:
        """Calculate quality score (0-100) for a Yelp business."""
        score = 0
        w = YelpDataQualityCalculator.WEIGHTS

        if business_data.get("rating") and business_data["rating"] > 0:
            score += w["has_rating"]

        review_count = business_data.get("review_count", 0)
        if review_count > 0:
            score += w["has_reviews"]
        if review_count > 100:
            score += w["review_count_bonus"]
        elif review_count > 50:
            score += w["review_count_bonus"] * 0.5

        if not business_data.get("is_closed", True):
            score += w["is_open"]

        if business_data.get("phone") or business_data.get("display_phone"):
            score += w["has_phone"]

        if business_data.get("categories"):
            score += w["has_categories"]

        location = business_data.get("location", {})
        if location.get("address1"):
            score += w["has_address"]

        if business_data.get("price"):
            score += w["has_price"]

        if business_data.get("image_url"):
            score += w["has_image"]

        return min(score, 100)


# ===================================================================
# CUSTOM EXCEPTIONS
# ===================================================================

class YelpAPIError(Exception):
    """Base Yelp API error."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class YelpDailyLimitExceeded(YelpAPIError):
    """Daily API call limit exceeded."""
    pass


class YelpRateLimitError(YelpAPIError):
    """Per-second rate limit hit (HTTP 429)."""
    pass


class YelpAuthError(YelpAPIError):
    """Authentication error (invalid API key)."""
    pass


# ===================================================================
# MAIN SCRAPER CLASS
# ===================================================================

class YelpScraper:
    """Production-ready Yelp Fusion API scraper.

    Scrapes business data and reviews from Yelp for hedge fund intelligence.
    Follows the same patterns as GoogleMapsRealScraper.

    Usage:
        scraper = YelpScraper(api_key=os.getenv("YELP_API_KEY"))
        businesses = scraper.search_businesses("Starbucks", "New York, NY")
        details = scraper.get_business_details(businesses[0].id)
        reviews = scraper.get_business_reviews(businesses[0].id)
    """

    def __init__(
        self,
        api_key: str,
        redis_url: Optional[str] = None,
        rate_limit: int = 5,
        daily_limit: int = YELP_DAILY_LIMIT,
        max_workers: int = 3,
        request_timeout: int = 30,
    ):
        """Initialize the Yelp scraper.

        Args:
            api_key: Yelp Fusion API key.
            redis_url: Redis connection URL for caching (optional).
            rate_limit: Max requests per second (default: 5).
            daily_limit: Max API calls per day (default: 5000).
            max_workers: Max parallel workers for batch operations (default: 3).
            request_timeout: HTTP request timeout in seconds (default: 30).
        """
        if not api_key:
            raise ValueError("YELP_API_KEY is required")

        self._api_key = api_key
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        })
        self._timeout = request_timeout
        self.rate_limiter = YelpRateLimiter(rate_limit, daily_limit)
        self.max_workers = max_workers
        self.quality_calculator = YelpDataQualityCalculator()

        # Setup cache if Redis available
        self.cache: Optional[YelpCacheManager] = None
        if redis_url:
            try:
                redis_client = redis.from_url(redis_url)
                redis_client.ping()
                self.cache = YelpCacheManager(redis_client)
                logger.info("yelp_redis_connected", url=redis_url)
            except redis.RedisError as e:
                logger.warning("yelp_redis_connection_failed", error=str(e))

        # Lazy-loaded sentiment analyzer
        self._sentiment_analyzer = None

        logger.info(
            "yelp_scraper_initialized",
            rate_limit=rate_limit,
            daily_limit=daily_limit,
            cache_enabled=self.cache is not None,
            max_workers=max_workers,
        )

    # -----------------------------------------------------------------
    # SENTIMENT ANALYSIS
    # -----------------------------------------------------------------

    def _get_sentiment_analyzer(self):
        """Lazy-load VADER sentiment analyzer."""
        if self._sentiment_analyzer is None:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            self._sentiment_analyzer = SentimentIntensityAnalyzer()
        return self._sentiment_analyzer

    def _score_sentiment(self, text: str) -> Optional[float]:
        """Score the sentiment of review text using VADER.

        Args:
            text: Review text.

        Returns:
            Compound sentiment score (-1 to 1), or None on failure.
        """
        if not text or len(text.strip()) < 3:
            return None
        try:
            analyzer = self._get_sentiment_analyzer()
            return round(analyzer.polarity_scores(text)["compound"], 4)
        except Exception:
            return None

    # -----------------------------------------------------------------
    # LOW-LEVEL API CALLS
    # -----------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type(YelpRateLimitError),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _api_get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a GET request to the Yelp Fusion API.

        Handles rate limiting, retries on 429/5xx, and structured error logging.

        Args:
            endpoint: API endpoint path (e.g., "/businesses/search").
            params: Query parameters.

        Returns:
            Parsed JSON response dict.

        Raises:
            YelpAuthError: On 401/403 responses.
            YelpRateLimitError: On 429 responses (triggers retry).
            YelpAPIError: On other HTTP errors.
            YelpDailyLimitExceeded: When daily budget is exceeded.
        """
        self.rate_limiter.wait()

        url = f"{YELP_API_BASE}{endpoint}"

        try:
            resp = self._session.get(url, params=params, timeout=self._timeout)
        except requests.exceptions.RequestException as e:
            logger.error("yelp_request_error", endpoint=endpoint, error=str(e))
            raise YelpAPIError(f"Request failed: {e}")

        if resp.status_code == 200:
            return resp.json()

        # Handle error responses
        error_body = ""
        try:
            error_data = resp.json()
            error_body = error_data.get("error", {}).get("description", resp.text[:200])
        except Exception:
            error_body = resp.text[:200]

        if resp.status_code in (401, 403):
            raise YelpAuthError(
                f"Authentication failed: {error_body}",
                status_code=resp.status_code,
            )
        if resp.status_code == 429:
            logger.warning("yelp_rate_limited", endpoint=endpoint)
            raise YelpRateLimitError(
                "Yelp API rate limited (429)",
                status_code=429,
            )
        if resp.status_code >= 500:
            logger.warning(
                "yelp_server_error",
                endpoint=endpoint,
                status_code=resp.status_code,
                body=error_body,
            )
            raise YelpRateLimitError(
                f"Yelp server error ({resp.status_code}): {error_body}",
                status_code=resp.status_code,
            )

        raise YelpAPIError(
            f"Yelp API error ({resp.status_code}): {error_body}",
            status_code=resp.status_code,
        )

    # -----------------------------------------------------------------
    # PUBLIC METHODS
    # -----------------------------------------------------------------

    def search_businesses(
        self,
        term: str,
        location: str,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = YelpSortMode.BEST_MATCH,
        radius: Optional[int] = None,
        categories: Optional[str] = None,
    ) -> List[YelpBusiness]:
        """Search for businesses by term and location.

        Args:
            term: Search term (e.g., "Starbucks", "coffee").
            location: Location string (e.g., "New York, NY").
            limit: Number of results to return (max 50, default 50).
            offset: Offset for pagination (default 0).
            sort_by: Sort mode (default: best_match).
            radius: Search radius in meters (max 40000).
            categories: Comma-separated category aliases (e.g., "restaurants,coffee").

        Returns:
            List of YelpBusiness objects.
        """
        # Check cache
        cache_key = f"search:{term}:{location}:{limit}:{offset}:{sort_by}"
        if self.cache:
            cached = self.cache.get("search", cache_key)
            if cached:
                logger.debug("yelp_search_cache_hit", term=term, location=location)
                return [YelpBusiness(**b) for b in cached]

        params: Dict = {
            "term": term,
            "location": location,
            "limit": min(limit, 50),
            "offset": offset,
            "sort_by": sort_by,
        }
        if radius is not None:
            params["radius"] = min(radius, 40000)
        if categories is not None:
            params["categories"] = categories

        try:
            data = self._api_get("/businesses/search", params=params)
        except YelpAPIError as e:
            logger.error(
                "yelp_search_error",
                term=term,
                location=location,
                error=str(e),
            )
            return []

        businesses = []
        for biz in data.get("businesses", []):
            parsed = self._parse_business(biz)
            if parsed:
                businesses.append(parsed)

        logger.info(
            "yelp_search_complete",
            term=term,
            location=location,
            total_api=data.get("total", 0),
            returned=len(businesses),
        )

        # Cache the results
        if self.cache and businesses:
            self.cache.set(
                "search",
                cache_key,
                [b.to_dict() for b in businesses],
                CACHE_TTL_SEARCH,
            )

        return businesses

    def get_business_details(self, business_id: str) -> Optional[YelpBusiness]:
        """Get full details for a single business.

        Args:
            business_id: Yelp business ID (e.g., "north-india-restaurant-san-francisco").

        Returns:
            YelpBusiness object or None.
        """
        if not business_id:
            return None

        # Check cache
        if self.cache:
            cached = self.cache.get("details", business_id)
            if cached:
                logger.debug("yelp_details_cache_hit", business_id=business_id)
                return YelpBusiness(**cached)

        try:
            data = self._api_get(f"/businesses/{business_id}")
        except YelpAPIError as e:
            logger.error(
                "yelp_details_error",
                business_id=business_id,
                error=str(e),
            )
            return None

        business = self._parse_business(data)
        if business and self.cache:
            self.cache.set("details", business_id, business.to_dict(), CACHE_TTL_DETAILS)

        return business

    def get_business_reviews(self, business_id: str) -> List[YelpReview]:
        """Get reviews for a business (up to 3, Yelp API hard limit).

        Args:
            business_id: Yelp business ID.

        Returns:
            List of YelpReview objects (max 3).
        """
        if not business_id:
            return []

        # Check cache
        if self.cache:
            cached = self.cache.get("reviews", business_id)
            if cached:
                logger.debug("yelp_reviews_cache_hit", business_id=business_id)
                return [YelpReview(**r) for r in cached]

        try:
            data = self._api_get(f"/businesses/{business_id}/reviews")
        except YelpAPIError as e:
            logger.error(
                "yelp_reviews_error",
                business_id=business_id,
                error=str(e),
            )
            return []

        reviews = []
        for raw in data.get("reviews", []):
            review = self._parse_review(raw)
            if review:
                reviews.append(review)

        logger.debug(
            "yelp_reviews_fetched",
            business_id=business_id,
            count=len(reviews),
        )

        # Cache the results
        if self.cache and reviews:
            self.cache.set(
                "reviews",
                business_id,
                [r.to_dict() for r in reviews],
                CACHE_TTL_REVIEWS,
            )

        return reviews

    def match_business(
        self,
        name: str,
        address: str,
        city: str,
        state: str,
        country: str,
    ) -> Optional[str]:
        """Match a business by name + address to get its Yelp business ID.

        Uses Yelp's Business Match endpoint, which is useful for matching
        our existing Google Maps locations to their Yelp equivalents.

        Args:
            name: Business name.
            address: Street address.
            city: City name.
            state: State/province code.
            country: ISO 3166-1 alpha-2 country code.

        Returns:
            Yelp business ID string, or None if no match found.
        """
        if not name or not city or not country:
            return None

        # Check cache
        cache_key = f"{name}:{address}:{city}:{country}"
        if self.cache:
            cached = self.cache.get("match", cache_key)
            if cached:
                return cached.get("business_id")

        params: Dict = {
            "name": name,
            "city": city,
            "country": country,
        }
        if address:
            params["address1"] = address
        if state:
            params["state"] = state

        try:
            data = self._api_get("/businesses/matches", params=params)
        except YelpAPIError as e:
            logger.warning(
                "yelp_match_error",
                name=name,
                city=city,
                error=str(e),
            )
            return None

        matches = data.get("businesses", [])
        if not matches:
            logger.debug("yelp_match_no_result", name=name, city=city)
            if self.cache:
                self.cache.set("match", cache_key, {"business_id": None}, CACHE_TTL_DETAILS)
            return None

        business_id = matches[0].get("id")
        logger.debug("yelp_match_found", name=name, city=city, business_id=business_id)

        if self.cache and business_id:
            self.cache.set("match", cache_key, {"business_id": business_id}, CACHE_TTL_DETAILS)

        return business_id

    def scrape_chain(
        self,
        chain_name: str,
        cities: List[str],
        max_per_city: int = 50,
        fetch_reviews: bool = True,
    ) -> List[Dict]:
        """Scrape all locations of a chain across multiple cities.

        For each city, searches for the chain, fetches business details,
        and optionally fetches reviews (up to 3 per business).

        Args:
            chain_name: Chain name (e.g., "Starbucks", "McDonald's").
            cities: List of city+location strings (e.g., ["New York, NY", "London, UK"]).
            max_per_city: Maximum businesses per city (default: 50).
            fetch_reviews: Whether to also fetch reviews (default: True).

        Returns:
            List of dicts, each containing business data and optionally reviews.
        """
        all_results: List[Dict] = []

        logger.info(
            "yelp_chain_scrape_started",
            chain=chain_name,
            cities=len(cities),
            max_per_city=max_per_city,
            fetch_reviews=fetch_reviews,
        )

        for city in cities:
            try:
                businesses = self.search_businesses(
                    term=chain_name,
                    location=city,
                    limit=min(max_per_city, 50),
                )

                for biz in businesses[:max_per_city]:
                    result = biz.to_dict()

                    # Optionally fetch detailed info
                    detailed = self.get_business_details(biz.id)
                    if detailed:
                        result = detailed.to_dict()

                    # Optionally fetch reviews
                    if fetch_reviews:
                        reviews = self.get_business_reviews(biz.id)
                        result["reviews"] = [r.to_dict() for r in reviews]
                    else:
                        result["reviews"] = []

                    all_results.append(result)

                logger.info(
                    "yelp_city_scraped",
                    chain=chain_name,
                    city=city,
                    locations=len(businesses[:max_per_city]),
                )

            except YelpDailyLimitExceeded:
                logger.error(
                    "yelp_daily_limit_exceeded_during_chain_scrape",
                    chain=chain_name,
                    city=city,
                    results_so_far=len(all_results),
                )
                break
            except Exception as e:
                logger.error(
                    "yelp_city_scrape_error",
                    chain=chain_name,
                    city=city,
                    error=str(e),
                )
                continue

        logger.info(
            "yelp_chain_scrape_complete",
            chain=chain_name,
            total_locations=len(all_results),
        )

        return all_results

    def match_existing_locations(
        self,
        locations: List[Dict],
    ) -> List[Dict]:
        """Match existing Google Maps locations to their Yelp equivalents.

        Takes a list of location dicts (from the ReviewSignal locations table)
        and attempts to find matching Yelp business IDs using name + address
        or name + city matching.

        Args:
            locations: List of location dicts with keys:
                name, address, city, country, latitude, longitude.

        Returns:
            List of dicts with added 'yelp_business_id' field.
            Only locations where a match was found are returned.
        """
        matched: List[Dict] = []

        logger.info(
            "yelp_match_existing_started",
            total_locations=len(locations),
        )

        for loc in locations:
            name = loc.get("name", "")
            address = loc.get("address", "")
            city = loc.get("city", "")
            country = loc.get("country", "")

            # Try to extract state from address for US locations
            state = ""
            if country in ("US", "USA", "United States"):
                state = self._extract_us_state(address)

            # Normalize country to ISO 2-letter code
            country_code = self._normalize_country_for_yelp(country)

            try:
                yelp_id = self.match_business(
                    name=name,
                    address=self._extract_street_address(address),
                    city=city,
                    state=state,
                    country=country_code,
                )

                if yelp_id:
                    result = dict(loc)
                    result["yelp_business_id"] = yelp_id
                    matched.append(result)
                    logger.debug(
                        "yelp_location_matched",
                        name=name,
                        city=city,
                        yelp_id=yelp_id,
                    )

            except YelpDailyLimitExceeded:
                logger.error(
                    "yelp_daily_limit_during_matching",
                    matched_so_far=len(matched),
                )
                break
            except Exception as e:
                logger.warning(
                    "yelp_match_location_error",
                    name=name,
                    city=city,
                    error=str(e),
                )
                continue

        logger.info(
            "yelp_match_existing_complete",
            total_locations=len(locations),
            matched=len(matched),
            match_rate=round(len(matched) / len(locations) * 100, 1)
            if locations
            else 0,
        )

        return matched

    def batch_get_details_and_reviews(
        self,
        business_ids: List[str],
    ) -> List[Dict]:
        """Batch fetch details and reviews for multiple businesses using thread pool.

        Args:
            business_ids: List of Yelp business IDs.

        Returns:
            List of dicts with business details and reviews.
        """
        results: List[Dict] = []

        def _fetch_one(biz_id: str) -> Optional[Dict]:
            details = self.get_business_details(biz_id)
            if not details:
                return None
            result = details.to_dict()
            reviews = self.get_business_reviews(biz_id)
            result["reviews"] = [r.to_dict() for r in reviews]
            return result

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_id = {
                executor.submit(_fetch_one, biz_id): biz_id
                for biz_id in business_ids
            }

            for future in as_completed(future_to_id):
                biz_id = future_to_id[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(
                        "yelp_batch_fetch_error",
                        business_id=biz_id,
                        error=str(e),
                    )

        return results

    def get_stats(self) -> Dict:
        """Get scraper statistics."""
        stats = {
            "rate_limiter": self.rate_limiter.get_stats(),
            "cache_enabled": self.cache is not None,
        }
        if self.cache:
            stats["cache"] = self.cache.get_stats()
        return stats

    # -----------------------------------------------------------------
    # PRIVATE HELPERS
    # -----------------------------------------------------------------

    def _parse_business(self, raw: Dict) -> Optional[YelpBusiness]:
        """Parse raw Yelp API business data into a YelpBusiness object.

        Args:
            raw: Raw business dict from Yelp API.

        Returns:
            YelpBusiness or None on parse failure.
        """
        try:
            location = raw.get("location", {})
            coordinates = raw.get("coordinates", {})
            categories_raw = raw.get("categories", [])

            # Extract display categories
            category_names = [
                c.get("title", c.get("alias", ""))
                for c in categories_raw
                if isinstance(c, dict)
            ]

            # Build full address string
            address_parts = [
                location.get("address1", ""),
                location.get("address2", ""),
                location.get("address3", ""),
            ]
            address = ", ".join(p for p in address_parts if p)

            quality_score = YelpDataQualityCalculator.calculate(raw)

            return YelpBusiness(
                id=raw.get("id", ""),
                name=raw.get("name", ""),
                address=address,
                city=location.get("city", ""),
                state=location.get("state", ""),
                country=location.get("country", ""),
                zip_code=location.get("zip_code", ""),
                rating=raw.get("rating", 0.0),
                review_count=raw.get("review_count", 0),
                categories=category_names,
                latitude=coordinates.get("latitude", 0.0),
                longitude=coordinates.get("longitude", 0.0),
                phone=raw.get("display_phone", raw.get("phone", "")),
                url=raw.get("url", ""),
                price=raw.get("price"),
                image_url=raw.get("image_url"),
                is_closed=raw.get("is_closed", False),
                data_quality_score=quality_score,
                scraped_at=datetime.utcnow().isoformat(),
            )
        except Exception as e:
            logger.error("yelp_parse_business_error", error=str(e))
            return None

    def _parse_review(self, raw: Dict) -> Optional[YelpReview]:
        """Parse raw Yelp API review data into a YelpReview object.

        Args:
            raw: Raw review dict from Yelp API.

        Returns:
            YelpReview or None on parse failure.
        """
        try:
            user = raw.get("user", {})
            text = raw.get("text", "")

            review = YelpReview(
                id=raw.get("id", ""),
                text=text,
                rating=raw.get("rating", 0),
                time_created=raw.get("time_created", ""),
                user_name=user.get("name", "Anonymous"),
                user_image_url=user.get("image_url"),
                url=raw.get("url"),
                sentiment_score=self._score_sentiment(text),
            )
            return review
        except Exception as e:
            logger.warning("yelp_parse_review_error", error=str(e))
            return None

    @staticmethod
    def _extract_us_state(address: str) -> str:
        """Extract US state code from an address string.

        Looks for 2-letter state codes in common address patterns.

        Args:
            address: Full address string.

        Returns:
            2-letter state code or empty string.
        """
        if not address:
            return ""
        import re

        # Pattern: ", NY 10001" or ", NY, USA" or ", CA "
        match = re.search(r",\s*([A-Z]{2})\s+\d{5}", address)
        if match:
            return match.group(1)
        match = re.search(r",\s*([A-Z]{2}),", address)
        if match:
            return match.group(1)
        match = re.search(r",\s*([A-Z]{2})\s*$", address)
        if match:
            return match.group(1)
        return ""

    @staticmethod
    def _extract_street_address(address: str) -> str:
        """Extract just the street address (first line) from a full address.

        Args:
            address: Full comma-separated address.

        Returns:
            First part of the address (street address).
        """
        if not address:
            return ""
        parts = address.split(",")
        return parts[0].strip()

    @staticmethod
    def _normalize_country_for_yelp(country: str) -> str:
        """Normalize country to ISO 3166-1 alpha-2 code for Yelp API.

        The Yelp API requires 2-letter country codes.

        Args:
            country: Country name or code.

        Returns:
            2-letter ISO country code.
        """
        if not country:
            return "US"

        # Already a 2-letter code
        if len(country) == 2:
            return country.upper()

        # Common mappings
        mapping = {
            "united states": "US",
            "usa": "US",
            "united kingdom": "GB",
            "uk": "GB",
            "canada": "CA",
            "germany": "DE",
            "france": "FR",
            "spain": "ES",
            "italy": "IT",
            "netherlands": "NL",
            "belgium": "BE",
            "austria": "AT",
            "switzerland": "CH",
            "australia": "AU",
            "new zealand": "NZ",
            "japan": "JP",
            "south korea": "KR",
            "singapore": "SG",
            "hong kong": "HK",
            "taiwan": "TW",
            "thailand": "TH",
            "malaysia": "MY",
            "indonesia": "ID",
            "mexico": "MX",
            "brazil": "BR",
            "india": "IN",
            "poland": "PL",
            "czech republic": "CZ",
            "sweden": "SE",
            "denmark": "DK",
            "norway": "NO",
            "finland": "FI",
            "ireland": "IE",
            "portugal": "PT",
            "greece": "GR",
        }

        return mapping.get(country.strip().lower(), country[:2].upper())

    def close(self) -> None:
        """Close the HTTP session and release resources."""
        self._session.close()
        logger.info("yelp_scraper_closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# ===================================================================
# CLI / MAIN
# ===================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv

    # Load .env from project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(project_root, ".env"))

    yelp_key = os.getenv("YELP_API_KEY")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    if not yelp_key or yelp_key == "REPLACE_WITH_YOUR_YELP_API_KEY":
        print("ERROR: Set YELP_API_KEY in .env file first.")
        print("  Get your key at: https://www.yelp.com/developers/v3/manage_app")
        exit(1)

    print("\n" + "=" * 60)
    print("REVIEWSIGNAL - YELP SCRAPER TEST RUN")
    print("=" * 60)

    with YelpScraper(api_key=yelp_key, redis_url=redis_url) as scraper:
        # Search for Starbucks in New York
        businesses = scraper.search_businesses("Starbucks", "New York, NY", limit=5)

        print(f"\nFound {len(businesses)} Starbucks locations in New York:\n")
        for biz in businesses:
            print(
                f"  * {biz.name}: {biz.rating}* ({biz.review_count} reviews) "
                f"- {biz.address}, {biz.city}"
            )

            # Get reviews for first business
            if biz == businesses[0]:
                reviews = scraper.get_business_reviews(biz.id)
                if reviews:
                    print(f"\n    Reviews for {biz.name}:")
                    for rev in reviews:
                        sentiment = f" (sentiment: {rev.sentiment_score})" if rev.sentiment_score else ""
                        print(
                            f"      - {rev.rating}* by {rev.user_name}: "
                            f'"{rev.text[:80]}..."{sentiment}'
                        )

        print(f"\n{'=' * 60}")
        print(f"Stats: {scraper.get_stats()}")
        print("=" * 60)
