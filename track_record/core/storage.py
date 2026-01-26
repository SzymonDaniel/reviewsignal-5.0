"""
Time Series Storage Interface for ReviewSignal Track Record System

Abstraction layer for storing and retrieving signals.
Supports multiple backends: Memory, TimescaleDB, PostgreSQL, S3.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict, Any
import json
from collections import defaultdict
import threading

from track_record.core.signal_types import Signal, SignalStatus


logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def store_signal(self, signal: Signal) -> None:
        """Store a new signal."""
        pass
    
    @abstractmethod
    def update_signal(self, signal: Signal) -> None:
        """Update an existing signal."""
        pass
    
    @abstractmethod
    def get_signal(self, signal_id: str) -> Optional[Signal]:
        """Get a signal by ID."""
        pass
    
    @abstractmethod
    def get_signals_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        status: Optional[SignalStatus] = None,
    ) -> List[Signal]:
        """Get signals within a date range."""
        pass
    
    @abstractmethod
    def get_all_signals(self, start_date: Optional[datetime] = None) -> List[Signal]:
        """Get all signals, optionally filtered by start date."""
        pass
    
    @abstractmethod
    def delete_signal(self, signal_id: str) -> bool:
        """Delete a signal. Returns True if deleted."""
        pass


class MemoryStorageBackend(StorageBackend):
    """
    In-memory storage backend for development and testing.
    
    Note: Data is not persisted across restarts.
    """
    
    def __init__(self):
        self._signals: Dict[str, Signal] = {}
        self._lock = threading.RLock()
    
    def store_signal(self, signal: Signal) -> None:
        with self._lock:
            self._signals[signal.signal_id] = signal
    
    def update_signal(self, signal: Signal) -> None:
        with self._lock:
            if signal.signal_id in self._signals:
                signal.updated_at = datetime.utcnow()
                self._signals[signal.signal_id] = signal
    
    def get_signal(self, signal_id: str) -> Optional[Signal]:
        with self._lock:
            return self._signals.get(signal_id)
    
    def get_signals_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        status: Optional[SignalStatus] = None,
    ) -> List[Signal]:
        with self._lock:
            signals = [
                s for s in self._signals.values()
                if start_date <= s.created_at <= end_date
            ]
            if status:
                signals = [s for s in signals if s.status == status]
            return sorted(signals, key=lambda s: s.created_at)
    
    def get_all_signals(self, start_date: Optional[datetime] = None) -> List[Signal]:
        with self._lock:
            signals = list(self._signals.values())
            if start_date:
                signals = [s for s in signals if s.created_at >= start_date]
            return sorted(signals, key=lambda s: s.created_at)
    
    def delete_signal(self, signal_id: str) -> bool:
        with self._lock:
            if signal_id in self._signals:
                del self._signals[signal_id]
                return True
            return False


class TimescaleDBStorageBackend(StorageBackend):
    """
    TimescaleDB storage backend for production time-series data.
    
    Optimized for:
    - High-volume signal ingestion
    - Time-based queries and aggregations
    - Compression and retention policies
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 5432)
        self.database = config.get("database", "reviewsignal")
        self.user = config.get("user", "postgres")
        self.password = config.get("password", "")
        
        self._pool = None
        self._init_connection_pool()
        self._ensure_tables()
    
    def _init_connection_pool(self):
        """Initialize database connection pool."""
        try:
            import psycopg2.pool
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=5,
                maxconn=20,
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
            )
            logger.info("TimescaleDB connection pool initialized")
        except ImportError:
            logger.warning("psycopg2 not installed. Using memory backend fallback.")
            self._pool = None
        except Exception as e:
            logger.error(f"Failed to initialize TimescaleDB connection: {e}")
            self._pool = None
    
    def _ensure_tables(self):
        """Ensure required tables exist."""
        if not self._pool:
            return
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS signals (
            signal_id VARCHAR(36) PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ,
            closed_at TIMESTAMPTZ,
            signal_type VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL,
            source VARCHAR(30) NOT NULL,
            brand VARCHAR(100) NOT NULL,
            ticker VARCHAR(10),
            confidence FLOAT,
            sentiment_score FLOAT,
            sentiment_magnitude FLOAT,
            review_velocity FLOAT,
            anomaly_score FLOAT,
            echo_coefficient FLOAT,
            price_at_signal FLOAT,
            target_price FLOAT,
            stop_loss FLOAT,
            price_at_close FLOAT,
            return_pct FLOAT,
            return_abs FLOAT,
            holding_period_days INTEGER,
            location_ids JSONB,
            metadata JSONB,
            tags JSONB,
            notes TEXT
        );
        
        -- Convert to hypertable for time-series optimization
        SELECT create_hypertable('signals', 'created_at', if_not_exists => TRUE);
        
        -- Create indexes for common queries
        CREATE INDEX IF NOT EXISTS idx_signals_brand ON signals (brand);
        CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals (ticker);
        CREATE INDEX IF NOT EXISTS idx_signals_status ON signals (status);
        CREATE INDEX IF NOT EXISTS idx_signals_created ON signals (created_at DESC);
        """
        
        conn = None
        try:
            conn = self._pool.getconn()
            with conn.cursor() as cur:
                cur.execute(create_table_sql)
            conn.commit()
            logger.info("TimescaleDB tables ensured")
        except Exception as e:
            logger.error(f"Failed to ensure tables: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                self._pool.putconn(conn)
    
    def store_signal(self, signal: Signal) -> None:
        if not self._pool:
            return
        
        sql = """
        INSERT INTO signals (
            signal_id, created_at, updated_at, expires_at, closed_at,
            signal_type, status, source, brand, ticker,
            confidence, sentiment_score, sentiment_magnitude,
            review_velocity, anomaly_score, echo_coefficient,
            price_at_signal, target_price, stop_loss, price_at_close,
            return_pct, return_abs, holding_period_days,
            location_ids, metadata, tags, notes
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s
        )
        """
        
        conn = None
        try:
            conn = self._pool.getconn()
            with conn.cursor() as cur:
                cur.execute(sql, (
                    signal.signal_id,
                    signal.created_at,
                    signal.updated_at,
                    signal.expires_at,
                    signal.closed_at,
                    signal.signal_type.value,
                    signal.status.value,
                    signal.source.value,
                    signal.brand,
                    signal.ticker,
                    signal.confidence,
                    signal.sentiment_score,
                    signal.sentiment_magnitude,
                    signal.review_velocity,
                    signal.anomaly_score,
                    signal.echo_coefficient,
                    signal.price_at_signal,
                    signal.target_price,
                    signal.stop_loss,
                    signal.price_at_close,
                    signal.return_pct,
                    signal.return_abs,
                    signal.holding_period_days,
                    json.dumps(signal.location_ids),
                    json.dumps(signal.metadata),
                    json.dumps(signal.tags),
                    signal.notes,
                ))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to store signal: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                self._pool.putconn(conn)
    
    def update_signal(self, signal: Signal) -> None:
        if not self._pool:
            return
        
        sql = """
        UPDATE signals SET
            updated_at = %s,
            closed_at = %s,
            status = %s,
            price_at_close = %s,
            return_pct = %s,
            return_abs = %s,
            holding_period_days = %s,
            notes = %s
        WHERE signal_id = %s
        """
        
        conn = None
        try:
            conn = self._pool.getconn()
            with conn.cursor() as cur:
                cur.execute(sql, (
                    datetime.utcnow(),
                    signal.closed_at,
                    signal.status.value,
                    signal.price_at_close,
                    signal.return_pct,
                    signal.return_abs,
                    signal.holding_period_days,
                    signal.notes,
                    signal.signal_id,
                ))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to update signal: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                self._pool.putconn(conn)
    
    def get_signal(self, signal_id: str) -> Optional[Signal]:
        if not self._pool:
            return None
        
        sql = "SELECT * FROM signals WHERE signal_id = %s"
        
        conn = None
        try:
            conn = self._pool.getconn()
            with conn.cursor() as cur:
                cur.execute(sql, (signal_id,))
                row = cur.fetchone()
                if row:
                    return self._row_to_signal(row, cur.description)
        except Exception as e:
            logger.error(f"Failed to get signal: {e}")
        finally:
            if conn:
                self._pool.putconn(conn)
        return None
    
    def get_signals_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        status: Optional[SignalStatus] = None,
    ) -> List[Signal]:
        if not self._pool:
            return []
        
        if status:
            sql = """
            SELECT * FROM signals 
            WHERE created_at >= %s AND created_at <= %s AND status = %s
            ORDER BY created_at
            """
            params = (start_date, end_date, status.value)
        else:
            sql = """
            SELECT * FROM signals 
            WHERE created_at >= %s AND created_at <= %s
            ORDER BY created_at
            """
            params = (start_date, end_date)
        
        signals = []
        conn = None
        try:
            conn = self._pool.getconn()
            with conn.cursor() as cur:
                cur.execute(sql, params)
                for row in cur.fetchall():
                    signals.append(self._row_to_signal(row, cur.description))
        except Exception as e:
            logger.error(f"Failed to get signals by date range: {e}")
        finally:
            if conn:
                self._pool.putconn(conn)
        return signals
    
    def get_all_signals(self, start_date: Optional[datetime] = None) -> List[Signal]:
        if not self._pool:
            return []
        
        if start_date:
            sql = "SELECT * FROM signals WHERE created_at >= %s ORDER BY created_at"
            params = (start_date,)
        else:
            sql = "SELECT * FROM signals ORDER BY created_at"
            params = ()
        
        signals = []
        conn = None
        try:
            conn = self._pool.getconn()
            with conn.cursor() as cur:
                cur.execute(sql, params)
                for row in cur.fetchall():
                    signals.append(self._row_to_signal(row, cur.description))
        except Exception as e:
            logger.error(f"Failed to get all signals: {e}")
        finally:
            if conn:
                self._pool.putconn(conn)
        return signals
    
    def delete_signal(self, signal_id: str) -> bool:
        if not self._pool:
            return False
        
        sql = "DELETE FROM signals WHERE signal_id = %s"
        
        conn = None
        try:
            conn = self._pool.getconn()
            with conn.cursor() as cur:
                cur.execute(sql, (signal_id,))
                deleted = cur.rowcount > 0
            conn.commit()
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete signal: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                self._pool.putconn(conn)
    
    def _row_to_signal(self, row: tuple, description) -> Signal:
        """Convert database row to Signal object."""
        columns = [col.name for col in description]
        data = dict(zip(columns, row))
        
        # Parse JSON fields
        if isinstance(data.get('location_ids'), str):
            data['location_ids'] = json.loads(data['location_ids'])
        if isinstance(data.get('metadata'), str):
            data['metadata'] = json.loads(data['metadata'])
        if isinstance(data.get('tags'), str):
            data['tags'] = json.loads(data['tags'])
        
        return Signal.from_dict(data)


class TimeSeriesStorage:
    """
    Main storage interface that delegates to appropriate backend.
    """
    
    def __init__(self, backend: str = "memory", config: Optional[Dict[str, Any]] = None):
        self.backend_type = backend
        self.config = config or {}
        self._backend = self._init_backend()
    
    def _init_backend(self) -> StorageBackend:
        """Initialize the appropriate storage backend."""
        if self.backend_type == "memory":
            return MemoryStorageBackend()
        elif self.backend_type == "timescaledb":
            return TimescaleDBStorageBackend(self.config)
        else:
            logger.warning(f"Unknown backend {self.backend_type}, using memory")
            return MemoryStorageBackend()
    
    def store_signal(self, signal: Signal) -> None:
        self._backend.store_signal(signal)
    
    def update_signal(self, signal: Signal) -> None:
        self._backend.update_signal(signal)
    
    def get_signal(self, signal_id: str) -> Optional[Signal]:
        return self._backend.get_signal(signal_id)
    
    def get_signals_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        status: Optional[SignalStatus] = None,
    ) -> List[Signal]:
        return self._backend.get_signals_by_date_range(start_date, end_date, status)
    
    def get_all_signals(self, start_date: Optional[datetime] = None) -> List[Signal]:
        return self._backend.get_all_signals(start_date)
    
    def delete_signal(self, signal_id: str) -> bool:
        return self._backend.delete_signal(signal_id)
