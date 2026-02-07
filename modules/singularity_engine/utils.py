# ═══════════════════════════════════════════════════════════════════════════════
# SINGULARITY ENGINE - Utility Functions
# Shared helper functions used across all modules
# ═══════════════════════════════════════════════════════════════════════════════

import uuid
import math
from datetime import datetime, timedelta
from typing import List, Iterator, TypeVar, Optional, Tuple, Dict, Any
import numpy as np
from scipy import stats
import structlog

logger = structlog.get_logger(__name__)

T = TypeVar('T')


# ═══════════════════════════════════════════════════════════════════════════════
# ID GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_id(prefix: str = "sing") -> str:
    """Generate unique ID with prefix"""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def generate_analysis_id() -> str:
    """Generate unique analysis ID"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    unique = uuid.uuid4().hex[:6]
    return f"analysis_{timestamp}_{unique}"


# ═══════════════════════════════════════════════════════════════════════════════
# SENTIMENT & NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_sentiment(rating: float, min_rating: float = 1.0, max_rating: float = 5.0) -> float:
    """
    Convert rating (1-5) to sentiment (-1 to 1)

    Examples:
        rating=5.0 → sentiment=1.0  (perfect)
        rating=3.0 → sentiment=0.0  (neutral)
        rating=1.0 → sentiment=-1.0 (terrible)
    """
    mid = (max_rating + min_rating) / 2
    range_half = (max_rating - min_rating) / 2
    if range_half == 0:
        return 0.0
    return (rating - mid) / range_half


def denormalize_sentiment(sentiment: float, min_rating: float = 1.0, max_rating: float = 5.0) -> float:
    """
    Convert sentiment (-1 to 1) back to rating (1-5)
    """
    mid = (max_rating + min_rating) / 2
    range_half = (max_rating - min_rating) / 2
    return sentiment * range_half + mid


def normalize_to_unit(value: float, min_val: float, max_val: float) -> float:
    """Normalize value to 0-1 range"""
    if max_val == min_val:
        return 0.5
    return (value - min_val) / (max_val - min_val)


# ═══════════════════════════════════════════════════════════════════════════════
# STATISTICAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def safe_mean(values: List[float]) -> float:
    """Calculate mean, return 0 if empty"""
    if not values:
        return 0.0
    return float(np.mean(values))


def safe_std(values: List[float]) -> float:
    """Calculate standard deviation, return 0 if empty or single value"""
    if len(values) < 2:
        return 0.0
    return float(np.std(values, ddof=1))


def calculate_z_score(value: float, mean: float, std: float) -> float:
    """Calculate z-score for a value"""
    if std == 0:
        return 0.0
    return (value - mean) / std


def calculate_z_scores(values: np.ndarray) -> np.ndarray:
    """Calculate z-scores for array of values"""
    mean = np.mean(values)
    std = np.std(values)
    if std == 0:
        return np.zeros_like(values)
    return (values - mean) / std


def is_anomaly(z_score: float, threshold: float = 2.0) -> bool:
    """Determine if z-score indicates an anomaly"""
    return abs(z_score) > threshold


def calculate_trend(values: List[float]) -> Tuple[str, float, float]:
    """
    Calculate trend direction using linear regression

    Returns:
        (direction, slope, p_value)
        direction: "up", "down", or "stable"
    """
    if len(values) < 3:
        return "stable", 0.0, 1.0

    x = np.arange(len(values))
    y = np.array(values)

    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

    # Determine direction based on statistical significance
    if p_value > 0.05:
        return "stable", float(slope), float(p_value)

    threshold = np.std(values) * 0.1 if np.std(values) > 0 else 0.01
    if slope > threshold:
        return "up", float(slope), float(p_value)
    elif slope < -threshold:
        return "down", float(slope), float(p_value)
    else:
        return "stable", float(slope), float(p_value)


def calculate_correlation(values_a: List[float], values_b: List[float]) -> Tuple[float, float]:
    """
    Calculate Pearson correlation coefficient

    Returns:
        (correlation, p_value)
    """
    if len(values_a) != len(values_b) or len(values_a) < 3:
        return 0.0, 1.0

    try:
        correlation, p_value = stats.pearsonr(values_a, values_b)
        return float(correlation), float(p_value)
    except Exception:
        return 0.0, 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH PROCESSING
# ═══════════════════════════════════════════════════════════════════════════════

def batch_iterator(items: List[T], batch_size: int) -> Iterator[List[T]]:
    """Yield successive batches from list"""
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


def sample_items(items: List[T], max_items: int, seed: int = 42) -> List[T]:
    """Randomly sample items if list is too large"""
    if len(items) <= max_items:
        return items
    np.random.seed(seed)
    indices = np.random.choice(len(items), size=max_items, replace=False)
    return [items[i] for i in indices]


# ═══════════════════════════════════════════════════════════════════════════════
# TIME HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_day_of_week_name(date: datetime) -> str:
    """Get day of week name from datetime"""
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    return days[date.weekday()]


def get_season(date: datetime) -> str:
    """Get meteorological season from datetime"""
    month = date.month
    if month in [3, 4, 5]:
        return "Spring"
    elif month in [6, 7, 8]:
        return "Summer"
    elif month in [9, 10, 11]:
        return "Fall"
    else:
        return "Winter"


def get_quarter(date: datetime) -> str:
    """Get fiscal quarter from datetime"""
    month = date.month
    if month in [1, 2, 3]:
        return "Q1"
    elif month in [4, 5, 6]:
        return "Q2"
    elif month in [7, 8, 9]:
        return "Q3"
    else:
        return "Q4"


def get_lunar_phase(date: datetime) -> str:
    """
    Get approximate lunar phase (simplified calculation)
    Returns: new, waxing, full, waning
    """
    # Reference new moon: January 6, 2000
    reference = datetime(2000, 1, 6)
    days_since = (date - reference).days
    lunar_cycle = 29.53  # days

    phase = (days_since % lunar_cycle) / lunar_cycle

    if phase < 0.125:
        return "new"
    elif phase < 0.375:
        return "waxing"
    elif phase < 0.625:
        return "full"
    elif phase < 0.875:
        return "waning"
    else:
        return "new"


def days_from_event(review_date: datetime, event_date: datetime) -> int:
    """Calculate days from event (negative = before, positive = after)"""
    return (review_date - event_date).days


def find_nearest_event(
    review_date: datetime,
    event_dates: List[datetime],
    max_distance_days: int = 30
) -> Optional[Tuple[datetime, int]]:
    """
    Find nearest event to a review date

    Returns:
        (event_date, days_from_event) or None if no event within max_distance
    """
    if not event_dates:
        return None

    min_distance = float('inf')
    nearest_event = None

    for event_date in event_dates:
        distance = abs((review_date - event_date).days)
        if distance < min_distance:
            min_distance = distance
            nearest_event = event_date

    if min_distance <= max_distance_days and nearest_event:
        days = days_from_event(review_date, nearest_event)
        return (nearest_event, days)

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# GEOGRAPHIC HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great circle distance between two points on Earth (in kilometers)
    """
    R = 6371.0  # Earth's radius in kilometers

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# ═══════════════════════════════════════════════════════════════════════════════
# TEXT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text with ellipsis"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def extract_keywords(text: str, top_n: int = 5) -> List[str]:
    """
    Simple keyword extraction using word frequency
    (For production, consider using RAKE, YAKE, or KeyBERT)
    """
    # Simple word frequency approach
    import re
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())

    # Remove common stop words
    stop_words = {
        'the', 'and', 'was', 'for', 'are', 'but', 'not', 'you', 'all',
        'can', 'her', 'had', 'one', 'our', 'out', 'has', 'have', 'been',
        'they', 'this', 'that', 'with', 'from', 'will', 'there', 'their',
        'what', 'about', 'which', 'when', 'make', 'like', 'time', 'just',
        'know', 'take', 'people', 'into', 'year', 'your', 'good', 'some',
        'could', 'them', 'other', 'than', 'then', 'now', 'look', 'only',
        'come', 'its', 'over', 'think', 'also', 'back', 'after', 'use',
        'two', 'how', 'work', 'first', 'well', 'way', 'even', 'new',
        'want', 'because', 'any', 'these', 'give', 'day', 'most', 'very'
    }

    filtered = [w for w in words if w not in stop_words]

    # Count frequencies
    freq = {}
    for word in filtered:
        freq[word] = freq.get(word, 0) + 1

    # Sort by frequency
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)

    return [word for word, count in sorted_words[:top_n]]


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIDENCE SCORING
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_confidence_level(confidence_score: float) -> str:
    """
    Convert numeric confidence to level

    Args:
        confidence_score: 0-1 float

    Returns:
        "low", "medium", "high", or "very_high"
    """
    if confidence_score >= 0.85:
        return "very_high"
    elif confidence_score >= 0.70:
        return "high"
    elif confidence_score >= 0.50:
        return "medium"
    else:
        return "low"


def combine_confidences(confidences: List[float], method: str = "harmonic") -> float:
    """
    Combine multiple confidence scores

    Methods:
        - "mean": arithmetic mean
        - "harmonic": harmonic mean (penalizes low values)
        - "geometric": geometric mean
        - "min": minimum value
    """
    if not confidences:
        return 0.0

    confidences = [max(0.001, c) for c in confidences]  # Avoid zeros

    if method == "mean":
        return float(np.mean(confidences))
    elif method == "harmonic":
        return float(stats.hmean(confidences))
    elif method == "geometric":
        return float(stats.gmean(confidences))
    elif method == "min":
        return float(min(confidences))
    else:
        return float(np.mean(confidences))


# ═══════════════════════════════════════════════════════════════════════════════
# TIMING UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

class Timer:
    """Context manager for timing code blocks"""

    def __init__(self, name: str = "operation"):
        self.name = name
        self.start_time = None
        self.elapsed_ms = 0

    def __enter__(self):
        self.start_time = datetime.utcnow()
        return self

    def __exit__(self, *args):
        elapsed = datetime.utcnow() - self.start_time
        self.elapsed_ms = int(elapsed.total_seconds() * 1000)
        logger.debug(f"timer_{self.name}", elapsed_ms=self.elapsed_ms)


# ═══════════════════════════════════════════════════════════════════════════════
# CACHING UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

class SimpleCache:
    """Simple in-memory cache with TTL"""

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = timedelta(seconds=ttl_seconds)
        self._cache: Dict[str, Tuple[Any, datetime]] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]
        if datetime.utcnow() - timestamp > self.ttl:
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: Any) -> None:
        """Set value in cache"""
        self._cache[key] = (value, datetime.utcnow())

    def clear(self) -> None:
        """Clear all cached values"""
        self._cache.clear()

    def cleanup(self) -> int:
        """Remove expired entries, return count removed"""
        now = datetime.utcnow()
        expired = [k for k, (v, ts) in self._cache.items() if now - ts > self.ttl]
        for key in expired:
            del self._cache[key]
        return len(expired)
