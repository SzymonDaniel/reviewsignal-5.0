"""
Benchmark Comparison for ReviewSignal Track Record System

Compare strategy performance against market benchmarks:
- S&P 500 (SPY)
- Sector ETFs (XLY Consumer Discretionary, etc.)
- Custom benchmarks
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import math

from track_record.performance.returns import ReturnSeries, ReturnCalculator


logger = logging.getLogger(__name__)


# Default benchmark tickers
BENCHMARKS = {
    "SPY": "S&P 500 ETF",
    "QQQ": "NASDAQ-100 ETF",
    "XLY": "Consumer Discretionary Select Sector",
    "XLP": "Consumer Staples Select Sector",
    "XLF": "Financial Select Sector",
    "XLV": "Health Care Select Sector",
    "XLK": "Technology Select Sector",
    "XLE": "Energy Select Sector",
    "XLRE": "Real Estate Select Sector",
    "IWM": "Russell 2000 Small Cap",
    "EFA": "MSCI EAFE International",
    "EEM": "MSCI Emerging Markets",
}


@dataclass
class BenchmarkResult:
    """
    Comparison results against a single benchmark.
    """
    benchmark_ticker: str = ""
    benchmark_name: str = ""
    
    # Period
    start_date: datetime = field(default_factory=datetime.utcnow)
    end_date: datetime = field(default_factory=datetime.utcnow)
    
    # Strategy performance
    strategy_return: float = 0.0      # Total return %
    strategy_volatility: float = 0.0  # Annualized volatility
    strategy_sharpe: float = 0.0      # Sharpe ratio
    
    # Benchmark performance
    benchmark_return: float = 0.0     # Total return %
    benchmark_volatility: float = 0.0 # Annualized volatility
    benchmark_sharpe: float = 0.0     # Sharpe ratio
    
    # Relative metrics
    excess_return: float = 0.0        # Strategy - Benchmark return
    alpha: float = 0.0                # Jensen's alpha
    beta: float = 0.0                 # Portfolio beta
    correlation: float = 0.0          # Correlation coefficient
    tracking_error: float = 0.0       # Tracking error
    information_ratio: float = 0.0    # Information ratio
    
    # Outperformance
    outperformed: bool = False        # Did strategy beat benchmark?
    outperformance_pct: float = 0.0   # By how much?
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark": {
                "ticker": self.benchmark_ticker,
                "name": self.benchmark_name,
            },
            "period": {
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat(),
            },
            "strategy": {
                "return": round(self.strategy_return, 2),
                "volatility": round(self.strategy_volatility, 2),
                "sharpe": round(self.strategy_sharpe, 2),
            },
            "benchmark": {
                "return": round(self.benchmark_return, 2),
                "volatility": round(self.benchmark_volatility, 2),
                "sharpe": round(self.benchmark_sharpe, 2),
            },
            "relative": {
                "excess_return": round(self.excess_return, 2),
                "alpha": round(self.alpha, 4),
                "beta": round(self.beta, 2),
                "correlation": round(self.correlation, 2),
                "tracking_error": round(self.tracking_error, 2),
                "information_ratio": round(self.information_ratio, 2),
            },
            "outperformed": self.outperformed,
            "outperformance_pct": round(self.outperformance_pct, 2),
        }
    
    def summary(self) -> str:
        """Generate text summary."""
        status = "OUTPERFORMED \u2714" if self.outperformed else "UNDERPERFORMED \u2718"
        return f"""
Benchmark Comparison: {self.benchmark_name} ({self.benchmark_ticker})
{'=' * 60}

                    Strategy      Benchmark     Difference
Return:             {self.strategy_return:+8.2f}%    {self.benchmark_return:+8.2f}%    {self.excess_return:+8.2f}%
Volatility:         {self.strategy_volatility:8.2f}%    {self.benchmark_volatility:8.2f}%
Sharpe Ratio:       {self.strategy_sharpe:8.2f}     {self.benchmark_sharpe:8.2f}

Relative Metrics:
  Alpha:            {self.alpha:+.4f}
  Beta:             {self.beta:.2f}
  Correlation:      {self.correlation:.2f}
  Information Ratio: {self.information_ratio:.2f}

Result: {status} by {abs(self.outperformance_pct):.2f}%
        """


class BenchmarkComparer:
    """
    Compare strategy performance against market benchmarks.
    
    Usage:
        comparer = BenchmarkComparer()
        
        # Compare against S&P 500
        result = comparer.compare(
            strategy_returns=return_series,
            benchmark_ticker="SPY",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2026, 1, 1)
        )
        
        print(result.summary())
        
        # Compare against multiple benchmarks
        results = comparer.compare_multiple(
            strategy_returns=return_series,
            benchmarks=["SPY", "XLY", "QQQ"]
        )
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.05,
        trading_days_per_year: int = 252,
        data_provider: Optional[Any] = None,
    ):
        """
        Initialize BenchmarkComparer.
        
        Args:
            risk_free_rate: Annual risk-free rate
            trading_days_per_year: Trading days per year
            data_provider: Optional data provider for fetching benchmark data
        """
        self.risk_free_rate = risk_free_rate
        self.trading_days_per_year = trading_days_per_year
        self.data_provider = data_provider
        
        self.return_calculator = ReturnCalculator(
            risk_free_rate=risk_free_rate,
            trading_days_per_year=trading_days_per_year,
        )
    
    def compare(
        self,
        strategy_returns: ReturnSeries,
        benchmark_ticker: str,
        benchmark_returns: Optional[List[float]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> BenchmarkResult:
        """
        Compare strategy against a benchmark.
        
        Args:
            strategy_returns: Strategy return series
            benchmark_ticker: Benchmark ticker symbol
            benchmark_returns: Optional pre-fetched benchmark returns
            start_date: Start of comparison period
            end_date: End of comparison period
            
        Returns:
            BenchmarkResult with comparison metrics
        """
        result = BenchmarkResult(
            benchmark_ticker=benchmark_ticker,
            benchmark_name=BENCHMARKS.get(benchmark_ticker, benchmark_ticker),
        )
        
        # Determine date range
        if strategy_returns.dates:
            result.start_date = start_date or min(strategy_returns.dates)
            result.end_date = end_date or max(strategy_returns.dates)
        
        # Get benchmark returns if not provided
        if benchmark_returns is None:
            benchmark_returns = self._fetch_benchmark_returns(
                benchmark_ticker,
                result.start_date,
                result.end_date,
                len(strategy_returns)
            )
        
        if not benchmark_returns:
            logger.warning(f"No benchmark data available for {benchmark_ticker}")
            return result
        
        strategy_rets = strategy_returns.returns
        
        # Align lengths
        min_len = min(len(strategy_rets), len(benchmark_returns))
        strategy_rets = strategy_rets[:min_len]
        benchmark_rets = benchmark_returns[:min_len]
        
        if min_len < 2:
            return result
        
        # Calculate strategy metrics
        result.strategy_return = self._calculate_total_return(strategy_rets)
        result.strategy_volatility = self._calculate_volatility(strategy_rets)
        result.strategy_sharpe = self._calculate_sharpe(
            result.strategy_return,
            result.strategy_volatility
        )
        
        # Calculate benchmark metrics
        result.benchmark_return = self._calculate_total_return(benchmark_rets)
        result.benchmark_volatility = self._calculate_volatility(benchmark_rets)
        result.benchmark_sharpe = self._calculate_sharpe(
            result.benchmark_return,
            result.benchmark_volatility
        )
        
        # Calculate relative metrics
        result.excess_return = result.strategy_return - result.benchmark_return
        result.alpha, result.beta = self._calculate_alpha_beta(
            strategy_rets, benchmark_rets
        )
        result.correlation = self._calculate_correlation(
            strategy_rets, benchmark_rets
        )
        result.tracking_error = self._calculate_tracking_error(
            strategy_rets, benchmark_rets
        )
        result.information_ratio = self._calculate_information_ratio(
            strategy_rets, benchmark_rets
        )
        
        # Determine outperformance
        result.outperformed = result.strategy_return > result.benchmark_return
        result.outperformance_pct = result.excess_return
        
        return result
    
    def compare_multiple(
        self,
        strategy_returns: ReturnSeries,
        benchmarks: Optional[List[str]] = None,
    ) -> List[BenchmarkResult]:
        """
        Compare strategy against multiple benchmarks.
        
        Args:
            strategy_returns: Strategy return series
            benchmarks: List of benchmark tickers (defaults to common ones)
            
        Returns:
            List of BenchmarkResult for each comparison
        """
        if benchmarks is None:
            benchmarks = ["SPY", "QQQ", "XLY"]  # Default benchmarks
        
        results = []
        for ticker in benchmarks:
            result = self.compare(strategy_returns, ticker)
            results.append(result)
        
        return results
    
    def rank_vs_benchmarks(
        self,
        strategy_returns: ReturnSeries,
        benchmarks: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Rank strategy performance against multiple benchmarks.
        
        Returns:
            Dictionary with ranking information
        """
        results = self.compare_multiple(strategy_returns, benchmarks)
        
        # Calculate percentile ranking
        all_returns = [r.benchmark_return for r in results]
        strategy_return = results[0].strategy_return if results else 0
        
        returns_below = sum(1 for r in all_returns if r < strategy_return)
        percentile = (returns_below / len(all_returns) * 100) if all_returns else 0
        
        # Count outperformance
        outperformed_count = sum(1 for r in results if r.outperformed)
        
        return {
            "strategy_return": strategy_return,
            "benchmarks_compared": len(results),
            "benchmarks_beaten": outperformed_count,
            "beat_percentage": outperformed_count / len(results) * 100 if results else 0,
            "percentile_rank": percentile,
            "best_vs": max(results, key=lambda r: r.excess_return).benchmark_ticker if results else None,
            "worst_vs": min(results, key=lambda r: r.excess_return).benchmark_ticker if results else None,
            "results": [r.to_dict() for r in results],
        }
    
    def _fetch_benchmark_returns(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        num_periods: int,
    ) -> List[float]:
        """
        Fetch benchmark returns from data provider.
        
        If no data provider, returns simulated data for development.
        """
        if self.data_provider:
            try:
                return self.data_provider.get_returns(ticker, start_date, end_date)
            except Exception as e:
                logger.error(f"Failed to fetch benchmark data: {e}")
        
        # Simulated returns for development/testing
        # In production, this would fetch real data from yfinance, etc.
        import random
        random.seed(42)  # For reproducibility in tests
        
        # Generate realistic-looking returns
        # SPY average daily return ~0.04%, volatility ~1%
        mean = 0.04
        std = 1.0
        
        return [random.gauss(mean, std) for _ in range(num_periods)]
    
    def _calculate_total_return(self, returns: List[float]) -> float:
        """Calculate total return from series."""
        cumulative = 1.0
        for r in returns:
            cumulative *= (1 + r / 100)
        return (cumulative - 1) * 100
    
    def _calculate_volatility(self, returns: List[float]) -> float:
        """Calculate annualized volatility."""
        if len(returns) < 2:
            return 0.0
        
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        daily_vol = math.sqrt(variance)
        
        return daily_vol * math.sqrt(self.trading_days_per_year)
    
    def _calculate_sharpe(self, annual_return: float, volatility: float) -> float:
        """Calculate Sharpe ratio."""
        if volatility == 0:
            return 0.0
        excess = annual_return - (self.risk_free_rate * 100)
        return excess / volatility
    
    def _calculate_alpha_beta(
        self,
        strategy_returns: List[float],
        benchmark_returns: List[float],
    ) -> Tuple[float, float]:
        """Calculate Jensen's Alpha and Beta."""
        if len(strategy_returns) < 2:
            return 0.0, 0.0
        
        mean_s = sum(strategy_returns) / len(strategy_returns)
        mean_b = sum(benchmark_returns) / len(benchmark_returns)
        
        covariance = sum(
            (s - mean_s) * (b - mean_b)
            for s, b in zip(strategy_returns, benchmark_returns)
        ) / (len(strategy_returns) - 1)
        
        variance_b = sum(
            (b - mean_b) ** 2 for b in benchmark_returns
        ) / (len(benchmark_returns) - 1)
        
        if variance_b == 0:
            return 0.0, 0.0
        
        beta = covariance / variance_b
        daily_rf = self.risk_free_rate / self.trading_days_per_year * 100
        alpha = mean_s - daily_rf - beta * (mean_b - daily_rf)
        
        return alpha, beta
    
    def _calculate_correlation(
        self,
        strategy_returns: List[float],
        benchmark_returns: List[float],
    ) -> float:
        """Calculate correlation coefficient."""
        if len(strategy_returns) < 2:
            return 0.0
        
        mean_s = sum(strategy_returns) / len(strategy_returns)
        mean_b = sum(benchmark_returns) / len(benchmark_returns)
        
        numerator = sum(
            (s - mean_s) * (b - mean_b)
            for s, b in zip(strategy_returns, benchmark_returns)
        )
        
        std_s = math.sqrt(sum((s - mean_s) ** 2 for s in strategy_returns))
        std_b = math.sqrt(sum((b - mean_b) ** 2 for b in benchmark_returns))
        
        if std_s == 0 or std_b == 0:
            return 0.0
        
        return numerator / (std_s * std_b)
    
    def _calculate_tracking_error(
        self,
        strategy_returns: List[float],
        benchmark_returns: List[float],
    ) -> float:
        """Calculate tracking error."""
        if len(strategy_returns) < 2:
            return 0.0
        
        diffs = [s - b for s, b in zip(strategy_returns, benchmark_returns)]
        mean_diff = sum(diffs) / len(diffs)
        variance = sum((d - mean_diff) ** 2 for d in diffs) / (len(diffs) - 1)
        
        return math.sqrt(variance) * math.sqrt(self.trading_days_per_year)
    
    def _calculate_information_ratio(
        self,
        strategy_returns: List[float],
        benchmark_returns: List[float],
    ) -> float:
        """Calculate Information Ratio."""
        tracking_error = self._calculate_tracking_error(
            strategy_returns, benchmark_returns
        )
        
        if tracking_error == 0:
            return 0.0
        
        mean_excess = sum(
            s - b for s, b in zip(strategy_returns, benchmark_returns)
        ) / len(strategy_returns)
        
        # Annualize
        annual_excess = mean_excess * self.trading_days_per_year
        
        return annual_excess / tracking_error
