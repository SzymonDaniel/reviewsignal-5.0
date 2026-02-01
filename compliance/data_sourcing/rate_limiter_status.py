#!/usr/bin/env python3
"""
Rate Limiter Status Module
Provides visibility into current rate limiting status across all APIs
"""

import redis
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import json


class RateLimiterStatus:
    """
    Monitors and reports rate limiting status
    Works with Redis-based rate limiters
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """Initialize with Redis connection"""
        self.redis_client = redis.from_url(redis_url, decode_responses=True)

    def get_google_maps_status(self) -> Dict[str, Any]:
        """
        Get Google Maps API rate limit status

        Returns current usage for:
        - Requests per second (50/s limit)
        - Daily quota (depends on plan)
        """
        # Check Redis keys for rate limiting
        # Assuming rate limiter uses keys like: rate_limit:google_maps:second:TIMESTAMP
        now = datetime.utcnow()
        second_key = f"rate_limit:google_maps:second:{int(now.timestamp())}"
        minute_key = f"rate_limit:google_maps:minute:{int(now.timestamp() // 60)}"
        hour_key = f"rate_limit:google_maps:hour:{int(now.timestamp() // 3600)}"
        day_key = f"rate_limit:google_maps:day:{now.strftime('%Y-%m-%d')}"

        # Get current counts
        try:
            current_second = int(self.redis_client.get(second_key) or 0)
            current_minute = int(self.redis_client.get(minute_key) or 0)
            current_hour = int(self.redis_client.get(hour_key) or 0)
            current_day = int(self.redis_client.get(day_key) or 0)
        except Exception:
            current_second = 0
            current_minute = 0
            current_hour = 0
            current_day = 0

        # Limits (configurable)
        limit_per_second = 50
        limit_per_minute = 3000
        limit_per_hour = 180000
        limit_per_day = 4000000  # Adjust based on your plan

        return {
            "service": "google_maps",
            "status": "healthy" if current_second < limit_per_second * 0.9 else "warning",
            "limits": {
                "per_second": {
                    "current": current_second,
                    "limit": limit_per_second,
                    "percentage": round((current_second / limit_per_second) * 100, 1),
                    "available": limit_per_second - current_second,
                },
                "per_minute": {
                    "current": current_minute,
                    "limit": limit_per_minute,
                    "percentage": round((current_minute / limit_per_minute) * 100, 1),
                },
                "per_hour": {
                    "current": current_hour,
                    "limit": limit_per_hour,
                    "percentage": round((current_hour / limit_per_hour) * 100, 1),
                },
                "per_day": {
                    "current": current_day,
                    "limit": limit_per_day,
                    "percentage": round((current_day / limit_per_day) * 100, 1),
                    "available": limit_per_day - current_day,
                },
            },
            "last_reset": {
                "second": now.replace(microsecond=0).isoformat(),
                "minute": now.replace(second=0, microsecond=0).isoformat(),
                "hour": now.replace(minute=0, second=0, microsecond=0).isoformat(),
                "day": now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
            },
            "timestamp": now.isoformat(),
        }

    def get_apollo_status(self) -> Dict[str, Any]:
        """Get Apollo API rate limit status"""
        # Apollo has monthly limits (4,000 credits/month)
        now = datetime.utcnow()
        month_key = f"rate_limit:apollo:month:{now.strftime('%Y-%m')}"

        try:
            current_month = int(self.redis_client.get(month_key) or 0)
        except Exception:
            current_month = 0

        limit_per_month = 4000  # Based on Pro plan

        return {
            "service": "apollo",
            "status": "healthy" if current_month < limit_per_month * 0.9 else "warning",
            "limits": {
                "per_month": {
                    "current": current_month,
                    "limit": limit_per_month,
                    "percentage": round((current_month / limit_per_month) * 100, 1),
                    "available": limit_per_month - current_month,
                },
            },
            "last_reset": {
                "month": now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat(),
            },
            "timestamp": now.isoformat(),
        }

    def get_all_status(self) -> Dict[str, Any]:
        """Get comprehensive rate limit status for all services"""
        return {
            "overall_status": "healthy",  # Can be: healthy, warning, critical
            "services": {
                "google_maps": self.get_google_maps_status(),
                "apollo": self.get_apollo_status(),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    def is_healthy(self) -> bool:
        """Check if all rate limiters are healthy (< 90% usage)"""
        status = self.get_all_status()

        for service_name, service_data in status["services"].items():
            if service_data["status"] != "healthy":
                return False

        return True

    def get_next_reset_time(self, service: str = "google_maps") -> Optional[datetime]:
        """Get when the next rate limit reset occurs"""
        now = datetime.utcnow()

        if service == "google_maps":
            # Next second
            return (now + timedelta(seconds=1)).replace(microsecond=0)
        elif service == "apollo":
            # Next month
            if now.month == 12:
                return datetime(now.year + 1, 1, 1)
            else:
                return datetime(now.year, now.month + 1, 1)

        return None


# Global instance
rate_limiter_status = RateLimiterStatus()


# Convenience functions
def get_rate_limit_status() -> Dict[str, Any]:
    """Quick helper to get all rate limit status"""
    return rate_limiter_status.get_all_status()


def is_rate_limit_healthy() -> bool:
    """Quick helper to check if rate limits are healthy"""
    return rate_limiter_status.is_healthy()
