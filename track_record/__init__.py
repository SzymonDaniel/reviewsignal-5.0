"""
Track Record & Backtesting Module for ReviewSignal

Professional-grade performance tracking and backtesting system
for hedge fund and institutional clients.

Usage:
    from track_record import SignalLogger, PerformanceTracker, BacktestEngine
    
    # Log signals
    logger = SignalLogger()
    signal = logger.log_signal(brand="SBUX", signal_type="BUY", confidence=0.85)
    
    # Calculate performance
    tracker = PerformanceTracker()
    metrics = tracker.calculate_metrics(start_date="2025-01-01")
    
    # Run backtests
    engine = BacktestEngine()
    results = engine.run(strategy="sentiment_momentum")

Author: ReviewSignal Team
Version: 1.0.0
"""

from track_record.core.signal_logger import SignalLogger
from track_record.core.signal_types import Signal, SignalType, SignalStatus
from track_record.performance.metrics import PerformanceTracker, PerformanceMetrics
from track_record.backtesting.engine import BacktestEngine, BacktestResult
from track_record.reports.pdf_generator import ReportGenerator

__version__ = "1.0.0"
__author__ = "ReviewSignal Team"
__all__ = [
    "SignalLogger",
    "Signal",
    "SignalType",
    "SignalStatus",
    "PerformanceTracker",
    "PerformanceMetrics",
    "BacktestEngine",
    "BacktestResult",
    "ReportGenerator",
]
