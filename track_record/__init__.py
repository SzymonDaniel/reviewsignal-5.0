"""
Track Record + Backtesting Module for ReviewSignal

This module provides comprehensive signal tracking, performance measurement,
and backtesting capabilities for hedge fund clients.

Author: Simon
Version: 1.0.0
Date: 2026-01-26
"""

from .core.signal_logger import SignalLogger, Signal, SignalType
from .core.performance_calc import PerformanceCalculator
from .core.benchmark_compare import BenchmarkComparator
from .core.sharpe_ratio import SharpeCalculator
from .core.drawdown_analyzer import DrawdownAnalyzer

__version__ = "1.0.0"
__all__ = [
    "SignalLogger",
    "Signal",
    "SignalType",
    "PerformanceCalculator",
    "BenchmarkComparator",
    "SharpeCalculator",
    "DrawdownAnalyzer",
]
