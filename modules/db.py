"""
Shared database connection pool for ReviewSignal.

Provides a singleton ThreadedConnectionPool for all services.
All DB credentials come from environment variables only.
"""

import os
import threading
from typing import Optional

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import structlog

logger = structlog.get_logger()

_pool: Optional[pool.ThreadedConnectionPool] = None
_pool_lock = threading.Lock()


def _get_db_config() -> dict:
    """Build DB config from environment variables."""
    db_pass = os.getenv("DB_PASS")
    if not db_pass:
        raise RuntimeError("DB_PASS environment variable must be set")

    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "dbname": os.getenv("DB_NAME", "reviewsignal"),
        "user": os.getenv("DB_USER", "reviewsignal"),
        "password": db_pass,
    }


def get_pool(minconn: int = 2, maxconn: int = 20) -> pool.ThreadedConnectionPool:
    """Get or create the singleton connection pool."""
    global _pool
    if _pool is None or _pool.closed:
        with _pool_lock:
            if _pool is None or _pool.closed:
                config = _get_db_config()
                _pool = pool.ThreadedConnectionPool(minconn, maxconn, **config)
                logger.info("db_pool_created", minconn=minconn, maxconn=maxconn)
    return _pool


def get_connection():
    """Get a connection from the pool."""
    return get_pool().getconn()


def return_connection(conn) -> None:
    """Return a connection to the pool."""
    try:
        get_pool().putconn(conn)
    except Exception:
        pass


def close_pool() -> None:
    """Close the connection pool (for shutdown)."""
    global _pool
    if _pool is not None and not _pool.closed:
        _pool.closeall()
        logger.info("db_pool_closed")
        _pool = None
