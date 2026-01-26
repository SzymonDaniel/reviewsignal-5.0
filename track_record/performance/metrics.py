"""
Performance Metrics for ReviewSignal Track Record System

Comprehensive risk-adjusted performance metrics:
- Sharpe Ratio
- Sortino Ratio
- Calmar Ratio
- Information Ratio
- Treynor Ratio
- Alpha & Beta
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from track_record.core.signal_types import Signal, SignalStatus
from track_record.performance.returns import ReturnCalculator, ReturnSeries
from track_record.performance.drawdown import DrawdownAnalyzer


logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """
    Container for all performance metrics.
    """
    # Time period
    start_date: datetime = field(default_factory=datetime.utcnow)
    end_date: datetime = field(default_factory=datetime.utcnow)
    trading_days: int = 0
    
    # Return metrics
    total_return: float = 0.0              # Total return %
    annualized_return: float = 0.0         # Annualized return %
    average_return: float = 0.0            # Average per-signal return %
    excess_return: float = 0.0             # Return above risk-free rate
    
    # Risk metrics
    volatility: float = 0.0                # Annualized volatility
    downside_volatility: float = 0.0       # Downside deviation
    max_drawdown: float = 0.0              # Maximum drawdown %
    avg_drawdown: float = 0.0              # Average drawdown %
    var_95: float = 0.0                    # Value at Risk (95%)
    cvar_95: float = 0.0                   # Conditional VaR (95%)
    
    # Risk-adjusted metrics
    sharpe_ratio: float = 0.0              # Sharpe ratio
    sortino_ratio: float = 0.0             # Sortino ratio
    calmar_ratio: float = 0.0              # Calmar ratio
    information_ratio: float = 0.0         # Information ratio
    treynor_ratio: float = 0.0             # Treynor ratio
    
    # Win/Loss metrics
    total_signals: int = 0
    winning_signals: int = 0
    losing_signals: int = 0
    win_rate: float = 0.0                  # Win rate %
    profit_factor: float = 0.0             # Gross profit / Gross loss
    expectancy: float = 0.0                # Expected return per trade
    win_loss_ratio: float = 0.0            # Avg win / Avg loss
    
    # Benchmark comparison
    alpha: float = 0.0                     # Jensen's alpha
    beta: float = 0.0                      # Portfolio beta
    correlation: float = 0.0               # Correlation with benchmark
    tracking_error: float = 0.0            # Tracking error vs benchmark
    
    # Additional
    avg_holding_period: float = 0.0        # Average days held
    signals_per_month: float = 0.0         # Trading frequency
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "period": {
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat(),
                "trading_days": self.trading_days,
            },
            "returns": {
                "total_return": round(self.total_return, 2),
                "annualized_return": round(self.annualized_return, 2),
                "average_return": round(self.average_return, 2),
                "excess_return": round(self.excess_return, 2),
            },
            "risk": {
                "volatility": round(self.volatility, 2),
                "downside_volatility": round(self.downside_volatility, 2),
                "max_drawdown": round(self.max_drawdown, 2),
                "avg_drawdown": round(self.avg_drawdown, 2),
                "var_95": round(self.var_95, 2),
                "cvar_95": round(self.cvar_95, 2),
            },
            "risk_adjusted": {
                "sharpe_ratio": round(self.sharpe_ratio, 2),
                "sortino_ratio": round(self.sortino_ratio, 2),
                "calmar_ratio": round(self.calmar_ratio, 2),
                "information_ratio": round(self.information_ratio, 2),
                "treynor_ratio": round(self.treynor_ratio, 2),
            },
            "win_loss": {
                "total_signals": self.total_signals,
                "winning_signals": self.winning_signals,
                "losing_signals": self.losing_signals,
                "win_rate": round(self.win_rate, 2),
                "profit_factor": round(self.profit_factor, 2),
                "expectancy": round(self.expectancy, 2),
                "win_loss_ratio": round(self.win_loss_ratio, 2),
            },
            "benchmark": {
                "alpha": round(self.alpha, 4),
                "beta": round(self.beta, 2),
                "correlation": round(self.correlation, 2),
                "tracking_error": round(self.tracking_error, 2),
            },
            "activity": {
                "avg_holding_period": round(self.avg_holding_period, 1),
                "signals_per_month": round(self.signals_per_month, 1),
            },
        }
    
    def summary(self) -> str:
        """Generate text summary."""
        return f"""
===== PERFORMANCE SUMMARY =====
Period: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}

RETURNS
  Total Return:      {self.total_return:+.2f}%
  Annualized Return: {self.annualized_return:+.2f}%
  Win Rate:          {self.win_rate:.1f}%

RISK METRICS
  Sharpe Ratio:      {self.sharpe_ratio:.2f}
  Sortino Ratio:     {self.sortino_ratio:.2f}
  Max Drawdown:      {self.max_drawdown:.2f}%
  Volatility:        {self.volatility:.2f}%

TRADING STATS
  Total Signals:     {self.total_signals}
  Profit Factor:     {self.profit_factor:.2f}
  Avg Holding Days:  {self.avg_holding_period:.1f}
===============================
        """


class PerformanceTracker:
    """
    Calculate comprehensive performance metrics.
    
    Usage:
        tracker = PerformanceTracker()
        metrics = tracker.calculate_metrics(
            signals=closed_signals,
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2026, 1, 1)
        )
        
        print(f"Sharpe Ratio: {metrics.sharpe_ratio}")
        print(metrics.summary())
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.05,
        trading_days_per_year: int = 252,
        benchmark_returns: Optional[List[float]] = None,
    ):
        """
        Initialize PerformanceTracker.
        
        Args:
            risk_free_rate: Annual risk-free rate (e.g., 0.05 for 5%)
            trading_days_per_year: Trading days per year
            benchmark_returns: Optional benchmark return series for comparison
        """
        self.risk_free_rate = risk_free_rate
        self.trading_days_per_year = trading_days_per_year
        self.benchmark_returns = benchmark_returns
        
        self.return_calculator = ReturnCalculator(
            risk_free_rate=risk_free_rate,
            trading_days_per_year=trading_days_per_year,
        )
        self.drawdown_analyzer = DrawdownAnalyzer()
    
    def calculate_metrics(
        self,
        signals: List[Signal],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        benchmark_returns: Optional[List[float]] = None,
    ) -> PerformanceMetrics:
        """
        Calculate all performance metrics.
        
        Args:
            signals: List of signals (both open and closed)
            start_date: Start of analysis period
            end_date: End of analysis period
            benchmark_returns: Optional benchmark returns for comparison
            
        Returns:
            PerformanceMetrics with all calculated values
        """
        metrics = PerformanceMetrics()
        
        # Filter closed signals with returns
        closed_signals = [
            s for s in signals
            if s.is_closed and s.return_pct is not None
        ]
        
        if not closed_signals:
            logger.warning("No closed signals to analyze")
            return metrics
        
        # Determine date range
        signal_dates = [s.closed_at for s in closed_signals if s.closed_at]
        if not signal_dates:
            return metrics
        
        metrics.start_date = start_date or min(signal_dates)
        metrics.end_date = end_date or max(signal_dates)
        metrics.trading_days = (metrics.end_date - metrics.start_date).days
        
        # Calculate returns
        return_series = self.return_calculator.calculate_from_signals(closed_signals)
        returns = return_series.returns
        
        if not returns:
            return metrics
        
        # Basic return metrics
        metrics.total_return = return_series.total_return
        metrics.average_return = return_series.mean_return
        
        # Annualize returns
        if metrics.trading_days > 0:
            annual_factor = self.trading_days_per_year / metrics.trading_days
            metrics.annualized_return = metrics.total_return * annual_factor
        
        # Calculate excess return
        rf_period = self.risk_free_rate * (metrics.trading_days / self.trading_days_per_year)
        metrics.excess_return = metrics.total_return - (rf_period * 100)
        
        # Risk metrics
        metrics.volatility = self._calculate_volatility(returns)
        metrics.downside_volatility = self._calculate_downside_volatility(returns)
        
        # Value at Risk
        metrics.var_95 = self._calculate_var(returns, 0.95)
        metrics.cvar_95 = self._calculate_cvar(returns, 0.95)
        
        # Drawdown
        dd_metrics = self.drawdown_analyzer.analyze(return_series)
        metrics.max_drawdown = dd_metrics.max_drawdown
        metrics.avg_drawdown = dd_metrics.avg_drawdown
        
        # Risk-adjusted metrics
        metrics.sharpe_ratio = self._calculate_sharpe(
            metrics.annualized_return,
            metrics.volatility
        )
        
        metrics.sortino_ratio = self._calculate_sortino(
            metrics.annualized_return,
            metrics.downside_volatility
        )
        
        metrics.calmar_ratio = self._calculate_calmar(
            metrics.annualized_return,
            metrics.max_drawdown
        )
        
        # Win/Loss statistics
        wl_stats = self.return_calculator.calculate_win_loss_stats(closed_signals)
        metrics.total_signals = wl_stats["total_trades"]
        metrics.winning_signals = wl_stats["winning_trades"]
        metrics.losing_signals = wl_stats["losing_trades"]
        metrics.win_rate = wl_stats["win_rate"]
        metrics.profit_factor = wl_stats["profit_factor"]
        metrics.expectancy = wl_stats["expectancy"]
        metrics.win_loss_ratio = wl_stats["win_loss_ratio"]
        metrics.avg_holding_period = wl_stats["avg_holding_days"]
        
        # Trading frequency
        months = metrics.trading_days / 30
        metrics.signals_per_month = metrics.total_signals / months if months > 0 else 0
        
        # Benchmark comparison if provided
        benchmark = benchmark_returns or self.benchmark_returns
        if benchmark and len(benchmark) >= len(returns):
            benchmark_aligned = benchmark[:len(returns)]
            metrics.alpha, metrics.beta = self._calculate_alpha_beta(
                returns, benchmark_aligned
            )
            metrics.correlation = self._calculate_correlation(
                returns, benchmark_aligned
            )
            metrics.tracking_error = self._calculate_tracking_error(
                returns, benchmark_aligned
            )
            metrics.information_ratio = self._calculate_information_ratio(
                returns, benchmark_aligned
            )
            metrics.treynor_ratio = self._calculate_treynor(
                metrics.annualized_return, metrics.beta
            )
        
        return metrics
    
    def _calculate_volatility(self, returns: List[float]) -> float:
        """Calculate annualized volatility."""
        if len(returns) < 2:
            return 0.0
        
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        daily_vol = math.sqrt(variance)
        
        # Annualize
        return daily_vol * math.sqrt(self.trading_days_per_year)
    
    def _calculate_downside_volatility(
        self,
        returns: List[float],
        mar: float = 0.0,  # Minimum Acceptable Return
    ) -> float:
        """Calculate downside deviation (semi-deviation)."""
        downside_returns = [min(0, r - mar) for r in returns]
        
        if len(downside_returns) < 2:
            return 0.0
        
        variance = sum(r ** 2 for r in downside_returns) / (len(downside_returns) - 1)
        daily_downside = math.sqrt(variance)
        
        return daily_downside * math.sqrt(self.trading_days_per_year)
    
    def _calculate_var(self, returns: List[float], confidence: float) -> float:
        """Calculate Value at Risk (historical method)."""
        if not returns:
            return 0.0
        
        sorted_returns = sorted(returns)
        index = int((1 - confidence) * len(sorted_returns))
        return abs(sorted_returns[index]) if index < len(sorted_returns) else 0.0
    
    def _calculate_cvar(self, returns: List[float], confidence: float) -> float:
        """Calculate Conditional VaR (Expected Shortfall)."""
        if not returns:
            return 0.0
        
        sorted_returns = sorted(returns)
        cutoff = int((1 - confidence) * len(sorted_returns))
        tail_returns = sorted_returns[:cutoff + 1]
        
        if not tail_returns:
            return 0.0
        
        return abs(sum(tail_returns) / len(tail_returns))
    
    def _calculate_sharpe(
        self,
        annualized_return: float,
        volatility: float,
    ) -> float:
        """Calculate Sharpe Ratio."""
        if volatility == 0:
            return 0.0
        
        excess_return = annualized_return - (self.risk_free_rate * 100)
        return excess_return / volatility
    
    def _calculate_sortino(
        self,
        annualized_return: float,
        downside_volatility: float,
    ) -> float:
        """Calculate Sortino Ratio."""
        if downside_volatility == 0:
            return 0.0
        
        excess_return = annualized_return - (self.risk_free_rate * 100)
        return excess_return / downside_volatility
    
    def _calculate_calmar(
        self,
        annualized_return: float,
        max_drawdown: float,
    ) -> float:
        """Calculate Calmar Ratio."""
        if max_drawdown == 0:
            return 0.0
        return annualized_return / abs(max_drawdown)
    
    def _calculate_alpha_beta(
        self,
        returns: List[float],
        benchmark_returns: List[float],
    ) -> tuple:
        """Calculate Jensen's Alpha and Beta."""
        if len(returns) != len(benchmark_returns) or len(returns) < 2:
            return 0.0, 0.0
        
        # Calculate means
        mean_r = sum(returns) / len(returns)
        mean_b = sum(benchmark_returns) / len(benchmark_returns)
        
        # Calculate covariance and variance
        covariance = sum(
            (r - mean_r) * (b - mean_b)
            for r, b in zip(returns, benchmark_returns)
        ) / (len(returns) - 1)
        
        variance_b = sum(
            (b - mean_b) ** 2 for b in benchmark_returns
        ) / (len(benchmark_returns) - 1)
        
        if variance_b == 0:
            return 0.0, 0.0
        
        beta = covariance / variance_b
        alpha = mean_r - (self.risk_free_rate / self.trading_days_per_year * 100) - beta * (mean_b - self.risk_free_rate / self.trading_days_per_year * 100)
        
        return alpha, beta
    
    def _calculate_correlation(
        self,
        returns: List[float],
        benchmark_returns: List[float],
    ) -> float:
        """Calculate correlation coefficient."""
        if len(returns) != len(benchmark_returns) or len(returns) < 2:
            return 0.0
        
        mean_r = sum(returns) / len(returns)
        mean_b = sum(benchmark_returns) / len(benchmark_returns)
        
        numerator = sum(
            (r - mean_r) * (b - mean_b)
            for r, b in zip(returns, benchmark_returns)
        )
        
        std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns))
        std_b = math.sqrt(sum((b - mean_b) ** 2 for b in benchmark_returns))
        
        if std_r == 0 or std_b == 0:
            return 0.0
        
        return numerator / (std_r * std_b)
    
    def _calculate_tracking_error(
        self,
        returns: List[float],
        benchmark_returns: List[float],
    ) -> float:
        """Calculate tracking error."""
        if len(returns) != len(benchmark_returns) or len(returns) < 2:
            return 0.0
        
        diffs = [r - b for r, b in zip(returns, benchmark_returns)]
        mean_diff = sum(diffs) / len(diffs)
        variance = sum((d - mean_diff) ** 2 for d in diffs) / (len(diffs) - 1)
        
        return math.sqrt(variance) * math.sqrt(self.trading_days_per_year)
    
    def _calculate_information_ratio(
        self,
        returns: List[float],
        benchmark_returns: List[float],
    ) -> float:
        """Calculate Information Ratio."""
        tracking_error = self._calculate_tracking_error(returns, benchmark_returns)
        
        if tracking_error == 0:
            return 0.0
        
        active_return = sum(returns) - sum(benchmark_returns)
        return (active_return / len(returns)) / (tracking_error / math.sqrt(self.trading_days_per_year))
    
    def _calculate_treynor(
        self,
        annualized_return: float,
        beta: float,
    ) -> float:
        """Calculate Treynor Ratio."""
        if beta == 0:
            return 0.0
        
        excess_return = annualized_return - (self.risk_free_rate * 100)
        return excess_return / beta
