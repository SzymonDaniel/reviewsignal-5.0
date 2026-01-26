"""
Benchmark Comparator - Compare signal performance against market benchmarks

Compares ReviewSignal performance against:
- S&P 500 (SPY)
- Sector ETFs (XLY for Consumer Discretionary)
- Custom benchmarks
- Risk-free rate

Usage:
    comparator = BenchmarkComparator()
    comparison = comparator.compare_to_benchmark(
        signals=signals,
        benchmark="SPY",
        start_date=start,
        end_date=end
    )
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger

try:
    import yfinance as yf
except ImportError:
    yf = None
    logger.warning("yfinance not installed - benchmark data will be simulated")

from .signal_logger import Signal
from .performance_calc import PerformanceMetrics, PerformanceCalculator


# Standard benchmarks for consumer/retail sector
BENCHMARKS = {
    "SPY": "S&P 500",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "QQQ": "NASDAQ 100",
    "IWM": "Russell 2000",
    "VTI": "Total Stock Market",
    "EAT": "Restaurant Index (Brinker)",
    "MCD": "McDonald's (Direct Comp)",
    "SBUX": "Starbucks (Direct Comp)",
}


@dataclass
class BenchmarkComparison:
    """Results of benchmark comparison"""
    # Strategy metrics
    strategy_return: float = 0.0
    strategy_annualized: float = 0.0
    strategy_volatility: float = 0.0
    strategy_sharpe: float = 0.0
    strategy_max_drawdown: float = 0.0
    
    # Benchmark metrics
    benchmark_name: str = ""
    benchmark_ticker: str = ""
    benchmark_return: float = 0.0
    benchmark_annualized: float = 0.0
    benchmark_volatility: float = 0.0
    benchmark_sharpe: float = 0.0
    benchmark_max_drawdown: float = 0.0
    
    # Comparison
    alpha: float = 0.0  # Excess return over benchmark
    beta: float = 0.0   # Sensitivity to benchmark
    correlation: float = 0.0  # Correlation with benchmark
    information_ratio: float = 0.0  # Risk-adjusted alpha
    tracking_error: float = 0.0  # Std dev of excess returns
    
    # Outperformance
    outperformance: float = 0.0  # Strategy - Benchmark return
    outperformance_pct: float = 0.0  # Percentage outperformance
    
    # Time period
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    trading_days: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "strategy": {
                "return": round(self.strategy_return, 4),
                "annualized_return": round(self.strategy_annualized, 4),
                "volatility": round(self.strategy_volatility, 4),
                "sharpe_ratio": round(self.strategy_sharpe, 2),
                "max_drawdown": round(self.strategy_max_drawdown, 4),
            },
            "benchmark": {
                "name": self.benchmark_name,
                "ticker": self.benchmark_ticker,
                "return": round(self.benchmark_return, 4),
                "annualized_return": round(self.benchmark_annualized, 4),
                "volatility": round(self.benchmark_volatility, 4),
                "sharpe_ratio": round(self.benchmark_sharpe, 2),
                "max_drawdown": round(self.benchmark_max_drawdown, 4),
            },
            "comparison": {
                "alpha": round(self.alpha, 4),
                "beta": round(self.beta, 2),
                "correlation": round(self.correlation, 2),
                "information_ratio": round(self.information_ratio, 2),
                "tracking_error": round(self.tracking_error, 4),
                "outperformance": round(self.outperformance, 4),
                "outperformance_pct": round(self.outperformance_pct, 2),
            },
            "period": {
                "start_date": self.start_date.isoformat() if self.start_date else None,
                "end_date": self.end_date.isoformat() if self.end_date else None,
                "trading_days": self.trading_days,
            },
        }
    
    def summary(self) -> str:
        """Generate human-readable summary"""
        status = "🟢 OUTPERFORMING" if self.outperformance > 0 else "🔴 UNDERPERFORMING"
        return (
            f"\n{'='*60}\n"
            f"BENCHMARK COMPARISON: ReviewSignal vs {self.benchmark_name}\n"
            f"{'='*60}\n"
            f"\n{status} by {abs(self.outperformance):.2%}\n\n"
            f"STRATEGY PERFORMANCE:\n"
            f"  Total Return:      {self.strategy_return:>10.2%}\n"
            f"  Annualized Return: {self.strategy_annualized:>10.2%}\n"
            f"  Volatility:        {self.strategy_volatility:>10.2%}\n"
            f"  Sharpe Ratio:      {self.strategy_sharpe:>10.2f}\n"
            f"  Max Drawdown:      {self.strategy_max_drawdown:>10.2%}\n\n"
            f"BENCHMARK ({self.benchmark_ticker}):\n"
            f"  Total Return:      {self.benchmark_return:>10.2%}\n"
            f"  Annualized Return: {self.benchmark_annualized:>10.2%}\n"
            f"  Volatility:        {self.benchmark_volatility:>10.2%}\n"
            f"  Sharpe Ratio:      {self.benchmark_sharpe:>10.2f}\n"
            f"  Max Drawdown:      {self.benchmark_max_drawdown:>10.2%}\n\n"
            f"RISK METRICS:\n"
            f"  Alpha:             {self.alpha:>10.2%}\n"
            f"  Beta:              {self.beta:>10.2f}\n"
            f"  Correlation:       {self.correlation:>10.2f}\n"
            f"  Information Ratio: {self.information_ratio:>10.2f}\n"
            f"  Tracking Error:    {self.tracking_error:>10.2%}\n"
            f"{'='*60}\n"
        )


class BenchmarkComparator:
    """
    Compare strategy performance against market benchmarks
    
    Fetches benchmark data from Yahoo Finance and calculates
    comprehensive comparison metrics.
    """
    
    def __init__(self, risk_free_rate: float = 0.05):
        """
        Initialize comparator
        
        Args:
            risk_free_rate: Annual risk-free rate (default 5%)
        """
        self.risk_free_rate = risk_free_rate
        self.perf_calc = PerformanceCalculator()
        self._benchmark_cache: Dict[str, pd.DataFrame] = {}
        logger.info(f"BenchmarkComparator initialized | Risk-free: {risk_free_rate:.2%}")
    
    def compare_to_benchmark(
        self,
        signals: List[Signal],
        benchmark: str = "SPY",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> BenchmarkComparison:
        """
        Compare signal performance to benchmark
        
        Args:
            signals: List of completed signals
            benchmark: Benchmark ticker symbol
            start_date: Start of comparison period
            end_date: End of comparison period
            
        Returns:
            BenchmarkComparison object
        """
        completed = [s for s in signals if s.outcome_return is not None]
        
        if not completed:
            logger.warning("No completed signals for benchmark comparison")
            return BenchmarkComparison(benchmark_ticker=benchmark)
        
        # Determine date range
        signal_dates = [s.generated_at for s in completed]
        start_date = start_date or min(signal_dates)
        end_date = end_date or max(signal_dates)
        
        # Get strategy returns
        strategy_returns = self._get_strategy_returns(completed)
        
        # Get benchmark returns
        benchmark_returns = self._get_benchmark_returns(
            benchmark, start_date, end_date
        )
        
        # Align returns
        strategy_returns, benchmark_returns = self._align_returns(
            strategy_returns, benchmark_returns
        )
        
        if len(strategy_returns) == 0:
            logger.warning("No overlapping data for comparison")
            return BenchmarkComparison(benchmark_ticker=benchmark)
        
        # Calculate comparison
        comparison = self._calculate_comparison(
            strategy_returns=strategy_returns,
            benchmark_returns=benchmark_returns,
            benchmark_ticker=benchmark,
            start_date=start_date,
            end_date=end_date,
        )
        
        logger.info(
            f"Benchmark comparison complete | "
            f"{benchmark}: {comparison.benchmark_return:.2%} | "
            f"Strategy: {comparison.strategy_return:.2%} | "
            f"Alpha: {comparison.alpha:.2%}"
        )
        
        return comparison
    
    def _get_strategy_returns(self, signals: List[Signal]) -> pd.Series:
        """Convert signals to daily returns series"""
        # Create returns DataFrame
        data = []
        for s in signals:
            if s.outcome_date:
                data.append({
                    "date": s.outcome_date.date(),
                    "return": s.outcome_return,
                })
        
        if not data:
            return pd.Series(dtype=float)
        
        df = pd.DataFrame(data)
        df = df.groupby("date")["return"].sum()  # Sum returns on same day
        return df
    
    def _get_benchmark_returns(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.Series:
        """
        Get benchmark returns from Yahoo Finance
        
        Falls back to simulated data if yfinance unavailable.
        """
        cache_key = f"{ticker}_{start_date.date()}_{end_date.date()}"
        
        if cache_key in self._benchmark_cache:
            return self._benchmark_cache[cache_key]
        
        if yf is not None:
            try:
                # Fetch from Yahoo Finance
                data = yf.download(
                    ticker,
                    start=start_date - timedelta(days=5),
                    end=end_date + timedelta(days=1),
                    progress=False,
                )
                
                if len(data) > 0:
                    returns = data["Adj Close"].pct_change().dropna()
                    returns.index = returns.index.date
                    self._benchmark_cache[cache_key] = returns
                    return returns
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker}: {e}")
        
        # Fallback: Simulated benchmark returns
        logger.info(f"Using simulated returns for {ticker}")
        return self._simulate_benchmark_returns(start_date, end_date)
    
    def _simulate_benchmark_returns(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.Series:
        """Generate simulated benchmark returns for testing"""
        # Generate business days
        dates = pd.bdate_range(start=start_date, end=end_date)
        
        # Simulate returns: ~10% annual return, ~15% volatility
        np.random.seed(42)  # Reproducible
        daily_return = 0.10 / 252  # ~10% annual
        daily_vol = 0.15 / np.sqrt(252)  # ~15% annual vol
        
        returns = np.random.normal(daily_return, daily_vol, len(dates))
        
        return pd.Series(returns, index=dates.date)
    
    def _align_returns(
        self,
        strategy: pd.Series,
        benchmark: pd.Series,
    ) -> tuple:
        """Align strategy and benchmark returns to common dates"""
        # Find common dates
        common_dates = set(strategy.index) & set(benchmark.index)
        
        if not common_dates:
            return pd.Series(dtype=float), pd.Series(dtype=float)
        
        common_dates = sorted(common_dates)
        
        return (
            strategy.loc[common_dates],
            benchmark.loc[common_dates],
        )
    
    def _calculate_comparison(
        self,
        strategy_returns: pd.Series,
        benchmark_returns: pd.Series,
        benchmark_ticker: str,
        start_date: datetime,
        end_date: datetime,
    ) -> BenchmarkComparison:
        """Calculate all comparison metrics"""
        comparison = BenchmarkComparison(
            benchmark_ticker=benchmark_ticker,
            benchmark_name=BENCHMARKS.get(benchmark_ticker, benchmark_ticker),
            start_date=start_date,
            end_date=end_date,
            trading_days=len(strategy_returns),
        )
        
        # Strategy metrics
        comparison.strategy_return = (1 + strategy_returns).prod() - 1
        comparison.strategy_volatility = strategy_returns.std() * np.sqrt(252)
        comparison.strategy_max_drawdown = self._calculate_max_drawdown(strategy_returns)
        
        # Annualized
        years = len(strategy_returns) / 252
        if years > 0:
            comparison.strategy_annualized = (
                (1 + comparison.strategy_return) ** (1 / years) - 1
            )
        
        # Sharpe
        if comparison.strategy_volatility > 0:
            comparison.strategy_sharpe = (
                (comparison.strategy_annualized - self.risk_free_rate)
                / comparison.strategy_volatility
            )
        
        # Benchmark metrics
        comparison.benchmark_return = (1 + benchmark_returns).prod() - 1
        comparison.benchmark_volatility = benchmark_returns.std() * np.sqrt(252)
        comparison.benchmark_max_drawdown = self._calculate_max_drawdown(benchmark_returns)
        
        if years > 0:
            comparison.benchmark_annualized = (
                (1 + comparison.benchmark_return) ** (1 / years) - 1
            )
        
        if comparison.benchmark_volatility > 0:
            comparison.benchmark_sharpe = (
                (comparison.benchmark_annualized - self.risk_free_rate)
                / comparison.benchmark_volatility
            )
        
        # Comparison metrics
        comparison.outperformance = (
            comparison.strategy_return - comparison.benchmark_return
        )
        
        if comparison.benchmark_return != 0:
            comparison.outperformance_pct = (
                comparison.outperformance / abs(comparison.benchmark_return) * 100
            )
        
        # Correlation and Beta
        if len(strategy_returns) > 1:
            comparison.correlation = strategy_returns.corr(benchmark_returns)
            
            # Beta = Cov(strategy, benchmark) / Var(benchmark)
            covariance = strategy_returns.cov(benchmark_returns)
            benchmark_var = benchmark_returns.var()
            if benchmark_var > 0:
                comparison.beta = covariance / benchmark_var
        
        # Alpha = Strategy Return - (Risk-free + Beta * (Benchmark - Risk-free))
        comparison.alpha = (
            comparison.strategy_annualized
            - (self.risk_free_rate + comparison.beta * 
               (comparison.benchmark_annualized - self.risk_free_rate))
        )
        
        # Tracking Error = Std Dev of (Strategy Returns - Benchmark Returns)
        excess_returns = strategy_returns - benchmark_returns
        comparison.tracking_error = excess_returns.std() * np.sqrt(252)
        
        # Information Ratio = Alpha / Tracking Error
        if comparison.tracking_error > 0:
            comparison.information_ratio = comparison.alpha / comparison.tracking_error
        
        return comparison
    
    def _calculate_max_drawdown(self, returns: pd.Series) -> float:
        """Calculate maximum drawdown from returns series"""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        return drawdown.min()
    
    def compare_multiple_benchmarks(
        self,
        signals: List[Signal],
        benchmarks: Optional[List[str]] = None,
    ) -> Dict[str, BenchmarkComparison]:
        """
        Compare strategy against multiple benchmarks
        
        Args:
            signals: List of completed signals
            benchmarks: List of benchmark tickers (default: all standard)
            
        Returns:
            Dictionary mapping ticker to comparison
        """
        if benchmarks is None:
            benchmarks = list(BENCHMARKS.keys())
        
        results = {}
        for benchmark in benchmarks:
            results[benchmark] = self.compare_to_benchmark(signals, benchmark)
        
        return results
    
    def rank_against_benchmarks(
        self,
        signals: List[Signal],
        metric: str = "return",
    ) -> pd.DataFrame:
        """
        Rank strategy against all benchmarks
        
        Args:
            signals: List of completed signals
            metric: Metric to rank by ('return', 'sharpe', 'alpha')
            
        Returns:
            DataFrame with rankings
        """
        comparisons = self.compare_multiple_benchmarks(signals)
        
        data = []
        for ticker, comp in comparisons.items():
            data.append({
                "ticker": ticker,
                "name": comp.benchmark_name,
                "return": comp.benchmark_return,
                "sharpe": comp.benchmark_sharpe,
                "strategy_outperformance": comp.outperformance,
            })
        
        # Add strategy
        first_comp = list(comparisons.values())[0]
        data.append({
            "ticker": "REVIEWSIGNAL",
            "name": "ReviewSignal Strategy",
            "return": first_comp.strategy_return,
            "sharpe": first_comp.strategy_sharpe,
            "strategy_outperformance": 0.0,
        })
        
        df = pd.DataFrame(data)
        df = df.sort_values(metric, ascending=False)
        df["rank"] = range(1, len(df) + 1)
        
        return df
