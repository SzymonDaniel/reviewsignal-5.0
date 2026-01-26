"""
Signal Logger for ReviewSignal Track Record System

Real-time logging of all trading signals with full audit trail.
Supports multiple storage backends and ensures data integrity.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from uuid import uuid4
import json
import threading
from collections import defaultdict

from track_record.core.signal_types import (
    Signal, SignalType, SignalStatus, SignalSource, SignalBatch
)
from track_record.core.storage import TimeSeriesStorage


logger = logging.getLogger(__name__)


class SignalLogger:
    """
    Professional-grade signal logging system.
    
    Features:
    - Real-time signal logging with microsecond precision
    - Multiple storage backend support (TimescaleDB, PostgreSQL, S3)
    - Automatic price fetching integration
    - Signal lifecycle management
    - Audit trail and compliance logging
    - Batch processing for high-throughput scenarios
    
    Usage:
        logger = SignalLogger(storage_backend="timescaledb")
        
        signal = logger.log_signal(
            brand="SBUX",
            ticker="SBUX",
            signal_type=SignalType.BUY,
            confidence=0.85,
            sentiment_score=0.72
        )
        
        # Later, close the signal
        logger.close_signal(signal.signal_id, current_price=102.50)
    """
    
    def __init__(
        self,
        storage_backend: str = "memory",
        storage_config: Optional[Dict[str, Any]] = None,
        price_fetcher: Optional[Callable[[str], float]] = None,
        auto_fetch_prices: bool = True,
        default_expiry_days: int = 30,
    ):
        """
        Initialize the SignalLogger.
        
        Args:
            storage_backend: Storage backend type ("memory", "timescaledb", "postgresql", "s3")
            storage_config: Backend-specific configuration
            price_fetcher: Optional function to fetch current stock prices
            auto_fetch_prices: Whether to automatically fetch prices on signal creation
            default_expiry_days: Default signal expiry period in days
        """
        self.storage_backend = storage_backend
        self.storage_config = storage_config or {}
        self.price_fetcher = price_fetcher
        self.auto_fetch_prices = auto_fetch_prices
        self.default_expiry_days = default_expiry_days
        
        # Initialize storage
        self._storage = self._init_storage()
        
        # In-memory caches
        self._active_signals: Dict[str, Signal] = {}
        self._signals_by_brand: Dict[str, List[str]] = defaultdict(list)
        self._signals_by_ticker: Dict[str, List[str]] = defaultdict(list)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Callbacks
        self._on_signal_created: List[Callable[[Signal], None]] = []
        self._on_signal_closed: List[Callable[[Signal], None]] = []
        
        # Statistics
        self._stats = {
            "total_signals": 0,
            "active_signals": 0,
            "closed_profitable": 0,
            "closed_loss": 0,
            "closed_neutral": 0,
        }
        
        logger.info(f"SignalLogger initialized with {storage_backend} backend")
    
    def _init_storage(self) -> TimeSeriesStorage:
        """Initialize storage backend."""
        return TimeSeriesStorage(
            backend=self.storage_backend,
            config=self.storage_config
        )
    
    def log_signal(
        self,
        brand: str,
        ticker: Optional[str] = None,
        signal_type: Optional[SignalType] = None,
        confidence: float = 0.0,
        sentiment_score: float = 0.0,
        sentiment_magnitude: float = 0.0,
        review_velocity: float = 0.0,
        anomaly_score: float = 0.0,
        echo_coefficient: float = 0.0,
        source: SignalSource = SignalSource.SENTIMENT_MODEL,
        price_at_signal: Optional[float] = None,
        target_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        location_ids: Optional[List[str]] = None,
        expiry_days: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        notes: str = "",
    ) -> Signal:
        """
        Log a new trading signal.
        
        Args:
            brand: Brand name (e.g., "Starbucks")
            ticker: Stock ticker (e.g., "SBUX"). Auto-resolved if not provided.
            signal_type: Type of signal. Auto-derived from sentiment if not provided.
            confidence: Model confidence score (0-1)
            sentiment_score: Normalized sentiment (-1 to 1)
            sentiment_magnitude: Strength of sentiment (0-1)
            review_velocity: Rate of review change
            anomaly_score: Anomaly detection score
            echo_coefficient: Echo engine butterfly coefficient
            source: Source of the signal
            price_at_signal: Stock price at signal time. Auto-fetched if not provided.
            target_price: Expected target price
            stop_loss: Stop loss level
            location_ids: List of location IDs contributing to signal
            expiry_days: Days until signal expires
            metadata: Additional metadata
            tags: Signal tags for categorization
            notes: Free-form notes
            
        Returns:
            Created Signal object
        """
        with self._lock:
            # Auto-derive signal type if not provided
            if signal_type is None:
                signal_type = SignalType.from_sentiment(sentiment_score, confidence)
            
            # Auto-resolve ticker from brand if not provided
            if ticker is None:
                ticker = self._resolve_ticker(brand)
            
            # Auto-fetch price if enabled and not provided
            if price_at_signal is None and self.auto_fetch_prices and self.price_fetcher:
                try:
                    price_at_signal = self.price_fetcher(ticker)
                except Exception as e:
                    logger.warning(f"Failed to fetch price for {ticker}: {e}")
                    price_at_signal = 0.0
            
            # Calculate expiry
            expiry_days = expiry_days or self.default_expiry_days
            expires_at = datetime.utcnow() + timedelta(days=expiry_days)
            
            # Create signal
            signal = Signal(
                signal_type=signal_type,
                status=SignalStatus.ACTIVE,
                source=source,
                brand=brand,
                ticker=ticker or "",
                location_ids=location_ids or [],
                confidence=confidence,
                sentiment_score=sentiment_score,
                sentiment_magnitude=sentiment_magnitude,
                review_velocity=review_velocity,
                anomaly_score=anomaly_score,
                echo_coefficient=echo_coefficient,
                price_at_signal=price_at_signal or 0.0,
                target_price=target_price,
                stop_loss=stop_loss,
                expires_at=expires_at,
                metadata=metadata or {},
                tags=tags or [],
                notes=notes,
            )
            
            # Store signal
            self._storage.store_signal(signal)
            
            # Update caches
            self._active_signals[signal.signal_id] = signal
            self._signals_by_brand[brand].append(signal.signal_id)
            if ticker:
                self._signals_by_ticker[ticker].append(signal.signal_id)
            
            # Update statistics
            self._stats["total_signals"] += 1
            self._stats["active_signals"] += 1
            
            # Trigger callbacks
            for callback in self._on_signal_created:
                try:
                    callback(signal)
                except Exception as e:
                    logger.error(f"Signal created callback error: {e}")
            
            logger.info(
                f"Signal logged: {signal.signal_id} | {brand} ({ticker}) | "
                f"{signal_type.value} | Confidence: {confidence:.2f}"
            )
            
            return signal
    
    def close_signal(
        self,
        signal_id: str,
        price: Optional[float] = None,
        status: Optional[SignalStatus] = None,
        notes: str = "",
    ) -> Optional[Signal]:
        """
        Close an active signal.
        
        Args:
            signal_id: ID of the signal to close
            price: Closing price. Auto-fetched if not provided.
            status: Override status (auto-calculated based on return if not provided)
            notes: Closing notes
            
        Returns:
            Updated Signal object or None if not found
        """
        with self._lock:
            signal = self._active_signals.get(signal_id)
            
            if not signal:
                # Try to fetch from storage
                signal = self._storage.get_signal(signal_id)
            
            if not signal:
                logger.warning(f"Signal not found: {signal_id}")
                return None
            
            if signal.is_closed:
                logger.warning(f"Signal already closed: {signal_id}")
                return signal
            
            # Auto-fetch price if not provided
            if price is None and self.price_fetcher and signal.ticker:
                try:
                    price = self.price_fetcher(signal.ticker)
                except Exception as e:
                    logger.warning(f"Failed to fetch closing price: {e}")
            
            if price is None:
                logger.error(f"No closing price available for signal: {signal_id}")
                return None
            
            # Close the signal
            signal.close(price, status)
            if notes:
                signal.notes = f"{signal.notes}\n[CLOSE] {notes}".strip()
            
            # Update storage
            self._storage.update_signal(signal)
            
            # Update caches
            if signal_id in self._active_signals:
                del self._active_signals[signal_id]
            
            # Update statistics
            self._stats["active_signals"] -= 1
            if signal.status == SignalStatus.CLOSED_PROFIT:
                self._stats["closed_profitable"] += 1
            elif signal.status == SignalStatus.CLOSED_LOSS:
                self._stats["closed_loss"] += 1
            else:
                self._stats["closed_neutral"] += 1
            
            # Trigger callbacks
            for callback in self._on_signal_closed:
                try:
                    callback(signal)
                except Exception as e:
                    logger.error(f"Signal closed callback error: {e}")
            
            logger.info(
                f"Signal closed: {signal_id} | {signal.brand} | "
                f"Return: {signal.return_pct:.2f}% | Status: {signal.status.value}"
            )
            
            return signal
    
    def get_signal(self, signal_id: str) -> Optional[Signal]:
        """Get a signal by ID."""
        with self._lock:
            if signal_id in self._active_signals:
                return self._active_signals[signal_id]
            return self._storage.get_signal(signal_id)
    
    def get_active_signals(
        self,
        brand: Optional[str] = None,
        ticker: Optional[str] = None,
        signal_type: Optional[SignalType] = None,
    ) -> List[Signal]:
        """Get all active signals with optional filters."""
        with self._lock:
            signals = list(self._active_signals.values())
            
            if brand:
                signals = [s for s in signals if s.brand == brand]
            if ticker:
                signals = [s for s in signals if s.ticker == ticker]
            if signal_type:
                signals = [s for s in signals if s.signal_type == signal_type]
            
            return signals
    
    def get_signals_by_date_range(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        status: Optional[SignalStatus] = None,
    ) -> List[Signal]:
        """Get signals within a date range."""
        end_date = end_date or datetime.utcnow()
        return self._storage.get_signals_by_date_range(start_date, end_date, status)
    
    def log_batch(
        self,
        signals_data: List[Dict[str, Any]],
    ) -> SignalBatch:
        """
        Log multiple signals in a batch.
        
        Args:
            signals_data: List of signal parameter dictionaries
            
        Returns:
            SignalBatch containing all created signals
        """
        batch = SignalBatch()
        
        for data in signals_data:
            signal = self.log_signal(**data)
            batch.add(signal)
        
        logger.info(f"Batch logged: {batch.batch_id} | {len(batch)} signals")
        return batch
    
    def expire_old_signals(self, as_of: Optional[datetime] = None) -> int:
        """
        Expire signals that have passed their expiry date.
        
        Args:
            as_of: Date to check expiry against (defaults to now)
            
        Returns:
            Number of signals expired
        """
        as_of = as_of or datetime.utcnow()
        expired_count = 0
        
        with self._lock:
            for signal_id, signal in list(self._active_signals.items()):
                if signal.expires_at and signal.expires_at < as_of:
                    signal.status = SignalStatus.EXPIRED
                    signal.closed_at = as_of
                    signal.updated_at = datetime.utcnow()
                    
                    self._storage.update_signal(signal)
                    del self._active_signals[signal_id]
                    
                    self._stats["active_signals"] -= 1
                    expired_count += 1
        
        if expired_count > 0:
            logger.info(f"Expired {expired_count} signals")
        
        return expired_count
    
    def on_signal_created(self, callback: Callable[[Signal], None]) -> None:
        """Register a callback for when signals are created."""
        self._on_signal_created.append(callback)
    
    def on_signal_closed(self, callback: Callable[[Signal], None]) -> None:
        """Register a callback for when signals are closed."""
        self._on_signal_closed.append(callback)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get logger statistics."""
        with self._lock:
            return dict(self._stats)
    
    def _resolve_ticker(self, brand: str) -> Optional[str]:
        """
        Resolve stock ticker from brand name.
        
        This uses a built-in mapping for common brands.
        Can be extended with external API lookup.
        """
        BRAND_TICKER_MAP = {
            "starbucks": "SBUX",
            "mcdonald's": "MCD",
            "mcdonalds": "MCD",
            "chipotle": "CMG",
            "domino's": "DPZ",
            "dominos": "DPZ",
            "papa john's": "PZZA",
            "yum! brands": "YUM",
            "yum brands": "YUM",
            "darden": "DRI",
            "hilton": "HLT",
            "marriott": "MAR",
            "hyatt": "H",
            "wyndham": "WH",
            "walmart": "WMT",
            "target": "TGT",
            "costco": "COST",
            "cvs": "CVS",
            "walgreens": "WBA",
            "home depot": "HD",
            "lowe's": "LOW",
            "lowes": "LOW",
            "nike": "NKE",
            "lululemon": "LULU",
            "ulta": "ULTA",
            "sephora": "LVMUY",  # Parent company
            "apple": "AAPL",
            "best buy": "BBY",
        }
        
        return BRAND_TICKER_MAP.get(brand.lower())
    
    def export_to_json(self, filepath: str, start_date: Optional[datetime] = None) -> int:
        """
        Export signals to JSON file.
        
        Args:
            filepath: Output file path
            start_date: Only export signals from this date onwards
            
        Returns:
            Number of signals exported
        """
        signals = self._storage.get_all_signals(start_date=start_date)
        
        data = {
            "exported_at": datetime.utcnow().isoformat(),
            "total_signals": len(signals),
            "signals": [s.to_dict() for s in signals],
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported {len(signals)} signals to {filepath}")
        return len(signals)
