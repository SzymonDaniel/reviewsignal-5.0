#!/usr/bin/env python3
"""
ENTERPRISE UTILITIES - Production-Grade Patterns
ReviewSignal 5.0.8 - Enterprise Features

Provides:
- Circuit Breaker pattern for external API resilience
- Retry logic with exponential backoff
- Connection pooling utilities
- Health check utilities
- Rate limiting
- Distributed locking (Redis-based)

Author: ReviewSignal Team
Version: 5.0.8
Date: February 2026
"""

import time
import functools
import threading
import asyncio
from typing import Callable, Optional, Any, Dict, List, TypeVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import structlog
import redis
from contextlib import contextmanager

logger = structlog.get_logger(__name__)

T = TypeVar('T')


# ═══════════════════════════════════════════════════════════════════════════════
# CIRCUIT BREAKER PATTERN
# ═══════════════════════════════════════════════════════════════════════════════

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for Circuit Breaker"""
    failure_threshold: int = 5       # Failures before opening
    success_threshold: int = 3       # Successes to close from half-open
    timeout_seconds: float = 60.0    # Time before half-open
    excluded_exceptions: tuple = ()  # Don't count these as failures


class CircuitBreaker:
    """
    Circuit Breaker pattern implementation.

    Prevents cascading failures by failing fast when a service is down.

    Usage:
        breaker = CircuitBreaker("external_api")

        @breaker
        def call_external_api():
            return requests.get("https://api.example.com")

        # Or use context manager:
        with breaker:
            response = requests.get("https://api.example.com")
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._lock = threading.RLock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if timeout elapsed
                if self._last_failure_time:
                    elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
                    if elapsed >= self.config.timeout_seconds:
                        self._state = CircuitState.HALF_OPEN
                        self._success_count = 0
                        logger.info(
                            "circuit_breaker_half_open",
                            name=self.name
                        )
            return self._state

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator usage"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return self._execute(func, *args, **kwargs)
        return wrapper

    def __enter__(self):
        """Context manager entry"""
        if self.state == CircuitState.OPEN:
            raise CircuitOpenError(f"Circuit '{self.name}' is OPEN")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type is None:
            self._on_success()
        elif not isinstance(exc_val, self.config.excluded_exceptions):
            self._on_failure(exc_val)
        return False  # Don't suppress exceptions

    def _execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        if self.state == CircuitState.OPEN:
            raise CircuitOpenError(f"Circuit '{self.name}' is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.excluded_exceptions:
            raise
        except Exception as e:
            self._on_failure(e)
            raise

    def _on_success(self):
        """Handle successful call"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info(
                        "circuit_breaker_closed",
                        name=self.name
                    )
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def _on_failure(self, exception: Exception):
        """Handle failed call"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.utcnow()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    "circuit_breaker_reopened",
                    name=self.name,
                    exception=str(exception)
                )
            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "circuit_breaker_opened",
                    name=self.name,
                    failures=self._failure_count,
                    exception=str(exception)
                )

    def reset(self):
        """Manually reset the circuit breaker"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            logger.info("circuit_breaker_reset", name=self.name)

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None
            }


class CircuitOpenError(Exception):
    """Raised when circuit is open"""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# RETRY WITH EXPONENTIAL BACKOFF
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RetryConfig:
    """Configuration for retry logic"""
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True  # Add randomness to prevent thundering herd
    retryable_exceptions: tuple = (Exception,)


def retry(
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None
) -> Callable:
    """
    Retry decorator with exponential backoff.

    Usage:
        @retry(RetryConfig(max_attempts=5))
        def flaky_api_call():
            return requests.get("https://api.example.com")

        # With custom callback:
        @retry(on_retry=lambda e, n: logger.warning(f"Retry {n}: {e}"))
        def another_call():
            pass
    """
    config = config or RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e

                    if attempt == config.max_attempts:
                        logger.error(
                            "retry_exhausted",
                            function=func.__name__,
                            attempts=attempt,
                            exception=str(e)
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay_seconds * (config.exponential_base ** (attempt - 1)),
                        config.max_delay_seconds
                    )

                    # Add jitter
                    if config.jitter:
                        import random
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        "retry_attempt",
                        function=func.__name__,
                        attempt=attempt,
                        max_attempts=config.max_attempts,
                        delay_seconds=delay,
                        exception=str(e)
                    )

                    if on_retry:
                        on_retry(e, attempt)

                    time.sleep(delay)

            raise last_exception

        return wrapper
    return decorator


async def async_retry(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    **kwargs
) -> T:
    """Async version of retry logic"""
    config = config or RetryConfig()
    last_exception = None

    for attempt in range(1, config.max_attempts + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except config.retryable_exceptions as e:
            last_exception = e

            if attempt == config.max_attempts:
                raise

            delay = min(
                config.base_delay_seconds * (config.exponential_base ** (attempt - 1)),
                config.max_delay_seconds
            )

            if config.jitter:
                import random
                delay = delay * (0.5 + random.random())

            await asyncio.sleep(delay)

    raise last_exception


# ═══════════════════════════════════════════════════════════════════════════════
# CONNECTION POOL MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class ConnectionPoolManager:
    """
    Manages database connection pools for enterprise scalability.

    Usage:
        pool_manager = ConnectionPoolManager()

        with pool_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM locations")
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        min_connections: int = 5,
        max_connections: int = 20
    ):
        if self._initialized:
            return

        import os
        from psycopg2 import pool as pg_pool

        self.min_connections = min_connections
        self.max_connections = max_connections

        # Get credentials from environment
        self._db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'reviewsignal'),
            'user': os.getenv('DB_USER', 'reviewsignal'),
            'password': os.getenv('DB_PASS'),
        }

        # Create connection pool
        try:
            self._pool = pg_pool.ThreadedConnectionPool(
                minconn=min_connections,
                maxconn=max_connections,
                **self._db_config
            )
            self._initialized = True
            logger.info(
                "connection_pool_created",
                min=min_connections,
                max=max_connections
            )
        except Exception as e:
            logger.error("connection_pool_failed", error=str(e))
            raise

    @contextmanager
    def get_connection(self):
        """Get connection from pool with automatic return"""
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
        finally:
            if conn:
                self._pool.putconn(conn)

    def close_all(self):
        """Close all connections in pool"""
        self._pool.closeall()
        logger.info("connection_pool_closed")

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        return {
            "min_connections": self.min_connections,
            "max_connections": self.max_connections,
            "db_host": self._db_config['host'],
            "db_name": self._db_config['database'],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# DISTRIBUTED LOCK (Redis-based)
# ═══════════════════════════════════════════════════════════════════════════════

class DistributedLock:
    """
    Redis-based distributed lock for multi-instance deployments.

    Usage:
        lock = DistributedLock("critical_section")

        with lock:
            # Only one process can execute this at a time
            perform_critical_operation()

        # Or async:
        async with lock:
            await perform_critical_operation()
    """

    def __init__(
        self,
        name: str,
        redis_url: str = "redis://localhost:6379/0",
        timeout_seconds: int = 30,
        blocking_timeout: int = 10
    ):
        self.name = f"lock:{name}"
        self.timeout = timeout_seconds
        self.blocking_timeout = blocking_timeout
        self._redis = redis.from_url(redis_url)
        self._lock = None

    def __enter__(self):
        self._lock = self._redis.lock(
            self.name,
            timeout=self.timeout,
            blocking_timeout=self.blocking_timeout
        )
        acquired = self._lock.acquire()
        if not acquired:
            raise LockAcquisitionError(f"Could not acquire lock: {self.name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._lock:
            try:
                self._lock.release()
            except redis.exceptions.LockError:
                pass  # Lock already released or expired
        return False

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)


class LockAcquisitionError(Exception):
    """Raised when lock cannot be acquired"""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class HealthStatus:
    """Health check result"""
    service: str
    status: str  # healthy, degraded, unhealthy
    latency_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class HealthChecker:
    """
    Comprehensive health checker for all system components.

    Usage:
        checker = HealthChecker()
        checker.add_check("postgres", check_postgres)
        checker.add_check("redis", check_redis)

        status = checker.check_all()
    """

    def __init__(self):
        self._checks: Dict[str, Callable[[], HealthStatus]] = {}

    def add_check(self, name: str, check_func: Callable[[], HealthStatus]):
        """Add a health check"""
        self._checks[name] = check_func

    def check(self, name: str) -> HealthStatus:
        """Run single health check"""
        if name not in self._checks:
            return HealthStatus(
                service=name,
                status="unknown",
                latency_ms=0,
                details={"error": "Check not found"}
            )

        start = time.time()
        try:
            result = self._checks[name]()
            result.latency_ms = (time.time() - start) * 1000
            return result
        except Exception as e:
            return HealthStatus(
                service=name,
                status="unhealthy",
                latency_ms=(time.time() - start) * 1000,
                details={"error": str(e)}
            )

    def check_all(self) -> Dict[str, HealthStatus]:
        """Run all health checks"""
        results = {}
        for name in self._checks:
            results[name] = self.check(name)
        return results

    def is_healthy(self) -> bool:
        """Check if all services are healthy"""
        results = self.check_all()
        return all(r.status == "healthy" for r in results.values())


# Pre-built health checks
def check_postgres() -> HealthStatus:
    """Check PostgreSQL connectivity"""
    import psycopg2
    import os

    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'reviewsignal'),
            user=os.getenv('DB_USER', 'reviewsignal'),
            password=os.getenv('DB_PASS'),
            connect_timeout=5
        )
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()

        return HealthStatus(
            service="postgres",
            status="healthy",
            latency_ms=0
        )
    except Exception as e:
        return HealthStatus(
            service="postgres",
            status="unhealthy",
            latency_ms=0,
            details={"error": str(e)}
        )


def check_redis() -> HealthStatus:
    """Check Redis connectivity"""
    import os

    try:
        r = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
        r.ping()

        return HealthStatus(
            service="redis",
            status="healthy",
            latency_ms=0
        )
    except Exception as e:
        return HealthStatus(
            service="redis",
            status="unhealthy",
            latency_ms=0,
            details={"error": str(e)}
        )


# ═══════════════════════════════════════════════════════════════════════════════
# RATE LIMITER
# ═══════════════════════════════════════════════════════════════════════════════

class RateLimiter:
    """
    Token bucket rate limiter with Redis backend.

    Usage:
        limiter = RateLimiter("api_calls", rate=100, per_seconds=60)

        if limiter.allow():
            process_request()
        else:
            return TooManyRequests()
    """

    def __init__(
        self,
        name: str,
        rate: int = 100,
        per_seconds: int = 60,
        redis_url: str = "redis://localhost:6379/0"
    ):
        self.name = f"ratelimit:{name}"
        self.rate = rate
        self.per_seconds = per_seconds
        self._redis = redis.from_url(redis_url)

    def allow(self, tokens: int = 1) -> bool:
        """Check if request is allowed"""
        now = time.time()
        key = f"{self.name}:{int(now // self.per_seconds)}"

        pipe = self._redis.pipeline()
        pipe.incr(key, tokens)
        pipe.expire(key, self.per_seconds + 1)
        results = pipe.execute()

        current = results[0]
        return current <= self.rate

    def get_remaining(self) -> int:
        """Get remaining tokens"""
        now = time.time()
        key = f"{self.name}:{int(now // self.per_seconds)}"

        current = self._redis.get(key)
        if current is None:
            return self.rate

        return max(0, self.rate - int(current))

    def reset(self):
        """Reset rate limiter"""
        now = time.time()
        key = f"{self.name}:{int(now // self.per_seconds)}"
        self._redis.delete(key)


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Circuit Breaker
    'CircuitBreaker',
    'CircuitBreakerConfig',
    'CircuitState',
    'CircuitOpenError',

    # Retry
    'retry',
    'async_retry',
    'RetryConfig',

    # Connection Pool
    'ConnectionPoolManager',

    # Distributed Lock
    'DistributedLock',
    'LockAcquisitionError',

    # Health Check
    'HealthChecker',
    'HealthStatus',
    'check_postgres',
    'check_redis',

    # Rate Limiter
    'RateLimiter',
]
