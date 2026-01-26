"""
Performance Calculation Module for ReviewSignal Track Record

Comprehensive performance metrics for hedge fund reporting.

Components:
- Returns: Return calculations (absolute, percentage, log)
- Metrics: Risk-adjusted metrics (Sharpe, Sortino, Calmar)
- Drawdown: Drawdown analysis and reporting
- Benchmark: Comparison against market benchmarks
"""

from track_record.performance.returns import ReturnCalculator, ReturnSeries
from track_record.performance.metrics import PerformanceTracker, PerformanceMetrics
from track_record.performance.drawdown import DrawdownAnalyzer, DrawdownMetrics
from track_record.performance.benchmark import BenchmarkComparer, BenchmarkResult

__all__ = [
    "ReturnCalculator",
    "ReturnSeries",
    "PerformanceTracker",
    "PerformanceMetrics",
    "DrawdownAnalyzer",
    "DrawdownMetrics",
    "BenchmarkComparer",
    "BenchmarkResult",
]
