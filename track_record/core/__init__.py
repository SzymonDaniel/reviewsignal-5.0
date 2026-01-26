"""
Core infrastructure for Track Record module.

Components:
- SignalLogger: Real-time signal logging
- SignalTypes: Signal type definitions and enums
- Storage: Time-series data storage interface
"""

from track_record.core.signal_logger import SignalLogger
from track_record.core.signal_types import Signal, SignalType, SignalStatus
from track_record.core.storage import TimeSeriesStorage

__all__ = [
    "SignalLogger",
    "Signal",
    "SignalType",
    "SignalStatus",
    "TimeSeriesStorage",
]
