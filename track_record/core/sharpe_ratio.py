"""
Sharpe Ratio Calculator - Risk-adjusted return metrics

Calculates comprehensive risk-adjusted performance metrics:
- Sharpe Ratio
- Sortino Ratio (downside deviation only)
- Calmar Ratio (return / max drawdown)
- Information Ratio
- Treynor Ratio

Usage:
    calculator = SharpeCalculator(risk_free_rate=0.05)
    metrics = calculator.calculate_all(returns)
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from loguru import logger

from .signal_logger import Signal


@dataclass
class RiskAdjustedMetrics:
    """Container for risk-adjusted performance metrics"""
    # Core ratios
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    treynor_ratio: float = 0.0
    information_ratio: float = 0.0
    
    # Return metrics
    annualized_return: float = 0.0
    annualized_volatility: float = 0.0
    downside_deviation: float = 0.0
    
    # Risk metrics
    var_95: float = 0.0  # Value at Risk 95%
    var_99: float = 0.0  # Value at Risk 99%
    cvar_95: float = 0.0  # Conditional VaR 95%
    max_drawdown: float = 0.0
    
    # Distribution
    skewness: float = 0.0
    kurtosis: float = 0.0
    
    # Period
    trading_days: int = 0
    risk_free_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "ratios": {
                "sharpe": round(self.sharpe_ratio, 3),
                "sortino": round(self.sortino_ratio, 3),
                "calmar": round(self.calmar_ratio, 3),
                "treynor": round(self.treynor_ratio, 3),
                "information": round(self.information_ratio, 3),
            },
            "returns": {
                "annualized_return": round(self.annualized_return, 4),
                "annualized_volatility": round(self.annualized_volatility, 4),
                "downside_deviation": round(self.downside_deviation, 4),
            },
            "risk": {
                "var_95": round(self.var_95, 4),
                "var_99": round(self.var_99, 4),
                "cvar_95": round(self.cvar_95, 4),
                "max_drawdown": round(self.max_drawdown, 4),
            },
            "distribution": {
                "skewness": round(self.skewness, 3),
                "kurtosis": round(self.kurtosis, 3),
            },
            "trading_days": self.trading_days,
            "risk_free_rate": self.risk_free_rate,
        }
    
    def quality_assessment(self) -> Dict[str, str]:
        """
        Assess quality of metrics for hedge fund presentation
        
        Returns:
            Dictionary with quality grades
        """
        grades = {}
        
        # Sharpe Ratio grades
        if self.sharpe_ratio >= 2.0:
            grades["sharpe"] = "🌟 Excellent (>2.0)"
        elif self.sharpe_ratio >= 1.5:
            grades["sharpe"] = "✅ Very Good (1.5-2.0)"
        elif self.sharpe_ratio >= 1.0:
            grades["sharpe"] = "🟡 Good (1.0-1.5)"
        elif self.sharpe_ratio >= 0.5:
            grades["sharpe"] = "🟠 Average (0.5-1.0)"
        else:
            grades["sharpe"] = "🔴 Below Average (<0.5)"
        
        # Sortino Ratio grades (higher threshold than Sharpe)
        if self.sortino_ratio >= 3.0:
            grades["sortino"] = "🌟 Excellent (>3.0)"
        elif self.sortino_ratio >= 2.0:
            grades["sortino"] = "✅ Very Good (2.0-3.0)"
        elif self.sortino_ratio >= 1.0:
            grades["sortino"] = "🟡 Good (1.0-2.0)"
        else:
            grades["sortino"] = "🟠 Average (<1.0)"
        
        # Max Drawdown grades
        if abs(self.max_drawdown) <= 0.10:
            grades["drawdown"] = "✅ Low Risk (<=10%)"
        elif abs(self.max_drawdown) <= 0.20:
            grades["drawdown"] = "🟡 Moderate (10-20%)"
        elif abs(self.max_drawdown) <= 0.30:
            grades["drawdown"] = "🟠 Elevated (20-30%)"
        else:
            grades["drawdown"] = "🔴 High Risk (>30%)"
        
        return grades


class SharpeCalculator:
    """
    Sharpe Ratio and Risk-Adjusted Metrics Calculator
    
    Calculates comprehensive risk-adjusted performance metrics
    for hedge fund track record reporting.
    """
    
    # Standard trading days per year
    TRADING_DAYS_PER_YEAR = 252
    
    def __init__(self, risk_free_rate: float = 0.05):
        """
        Initialize calculator
        
        Args:
            risk_free_rate: Annual risk-free rate (default 5%)
        """
        self.risk_free_rate = risk_free_rate
        logger.info(f"SharpeCalculator initialized | Risk-free: {risk_free_rate:.2%}")
    
    def calculate_all(
        self,
        returns: Union[List[float], pd.Series, np.ndarray],
        benchmark_returns: Optional[Union[List[float], pd.Series]] = None,
        beta: float = 1.0,
    ) -> RiskAdjustedMetrics:
        """
        Calculate all risk-adjusted metrics
        
        Args:
            returns: Series of returns (daily or per-trade)
            benchmark_returns: Optional benchmark for info ratio
            beta: Portfolio beta for Treynor ratio
            
        Returns:
            RiskAdjustedMetrics object
        """
        # Convert to numpy array
        returns = np.array(returns)
        returns = returns[~np.isnan(returns)]  # Remove NaN
        
        if len(returns) == 0:
            return RiskAdjustedMetrics(risk_free_rate=self.risk_free_rate)
        
        metrics = RiskAdjustedMetrics(
            risk_free_rate=self.risk_free_rate,
            trading_days=len(returns),
        )
        
        # Basic stats
        metrics.annualized_return = self._annualize_return(returns)
        metrics.annualized_volatility = self._annualize_volatility(returns)
        metrics.downside_deviation = self._downside_deviation(returns)
        
        # Sharpe Ratio
        metrics.sharpe_ratio = self.sharpe_ratio(returns)
        
        # Sortino Ratio
        metrics.sortino_ratio = self.sortino_ratio(returns)
        
        # Max Drawdown and Calmar
        metrics.max_drawdown = self._max_drawdown(returns)
        metrics.calmar_ratio = self.calmar_ratio(returns)
        
        # Treynor Ratio
        metrics.treynor_ratio = self.treynor_ratio(returns, beta)
        
        # Information Ratio (if benchmark provided)
        if benchmark_returns is not None:
            metrics.information_ratio = self.information_ratio(
                returns, np.array(benchmark_returns)
            )
        
        # VaR and CVaR
        metrics.var_95 = self.value_at_risk(returns, 0.95)
        metrics.var_99 = self.value_at_risk(returns, 0.99)
        metrics.cvar_95 = self.conditional_var(returns, 0.95)
        
        # Distribution stats
        if len(returns) > 2:
            from scipy import stats
            metrics.skewness = stats.skew(returns)
            metrics.kurtosis = stats.kurtosis(returns)
        
        logger.info(
            f"Risk metrics calculated | "
            f"Sharpe: {metrics.sharpe_ratio:.2f} | "
            f"Sortino: {metrics.sortino_ratio:.2f} | "
            f"Max DD: {metrics.max_drawdown:.2%}"
        )
        
        return metrics
    
    def sharpe_ratio(self, returns: np.ndarray) -> float:
        """
        Calculate Sharpe Ratio
        
        Sharpe = (Return - Risk-free) / Volatility
        
        Args:
            returns: Array of returns
            
        Returns:
            Annualized Sharpe Ratio
        """
        if len(returns) == 0:
            return 0.0
        
        ann_return = self._annualize_return(returns)
        ann_vol = self._annualize_volatility(returns)
        
        if ann_vol == 0:
            return 0.0
        
        return (ann_return - self.risk_free_rate) / ann_vol
    
    def sortino_ratio(self, returns: np.ndarray) -> float:
        """
        Calculate Sortino Ratio
        
        Sortino = (Return - Risk-free) / Downside Deviation
        
        Only penalizes downside volatility, not upside.
        
        Args:
            returns: Array of returns
            
        Returns:
            Annualized Sortino Ratio
        """
        if len(returns) == 0:
            return 0.0
        
        ann_return = self._annualize_return(returns)
        downside_dev = self._downside_deviation(returns)
        
        if downside_dev == 0:
            return float('inf') if ann_return > self.risk_free_rate else 0.0
        
        return (ann_return - self.risk_free_rate) / downside_dev
    
    def calmar_ratio(self, returns: np.ndarray) -> float:
        """
        Calculate Calmar Ratio
        
        Calmar = Annualized Return / |Max Drawdown|
        
        Args:
            returns: Array of returns
            
        Returns:
            Calmar Ratio
        """
        if len(returns) == 0:
            return 0.0
        
        ann_return = self._annualize_return(returns)
        max_dd = abs(self._max_drawdown(returns))
        
        if max_dd == 0:
            return float('inf') if ann_return > 0 else 0.0
        
        return ann_return / max_dd
    
    def treynor_ratio(
        self,
        returns: np.ndarray,
        beta: float = 1.0,
    ) -> float:
        """
        Calculate Treynor Ratio
        
        Treynor = (Return - Risk-free) / Beta
        
        Args:
            returns: Array of returns
            beta: Portfolio beta
            
        Returns:
            Treynor Ratio
        """
        if len(returns) == 0 or beta == 0:
            return 0.0
        
        ann_return = self._annualize_return(returns)
        
        return (ann_return - self.risk_free_rate) / beta
    
    def information_ratio(
        self,
        returns: np.ndarray,
        benchmark_returns: np.ndarray,
    ) -> float:
        """
        Calculate Information Ratio
        
        IR = Mean(Excess Return) / Std(Excess Return)
        
        Args:
            returns: Array of portfolio returns
            benchmark_returns: Array of benchmark returns
            
        Returns:
            Information Ratio
        """
        if len(returns) != len(benchmark_returns):
            # Align lengths
            min_len = min(len(returns), len(benchmark_returns))
            returns = returns[:min_len]
            benchmark_returns = benchmark_returns[:min_len]
        
        if len(returns) == 0:
            return 0.0
        
        excess_returns = returns - benchmark_returns
        tracking_error = np.std(excess_returns) * np.sqrt(self.TRADING_DAYS_PER_YEAR)
        
        if tracking_error == 0:
            return 0.0
        
        mean_excess = np.mean(excess_returns) * self.TRADING_DAYS_PER_YEAR
        
        return mean_excess / tracking_error
    
    def value_at_risk(
        self,
        returns: np.ndarray,
        confidence: float = 0.95,
    ) -> float:
        """
        Calculate Value at Risk (VaR)
        
        VaR = Percentile loss at given confidence level
        
        Args:
            returns: Array of returns
            confidence: Confidence level (e.g., 0.95)
            
        Returns:
            VaR value (negative number representing loss)
        """
        if len(returns) == 0:
            return 0.0
        
        return np.percentile(returns, (1 - confidence) * 100)
    
    def conditional_var(
        self,
        returns: np.ndarray,
        confidence: float = 0.95,
    ) -> float:
        """
        Calculate Conditional Value at Risk (CVaR / Expected Shortfall)
        
        CVaR = Average of returns below VaR threshold
        
        Args:
            returns: Array of returns
            confidence: Confidence level
            
        Returns:
            CVaR value
        """
        if len(returns) == 0:
            return 0.0
        
        var = self.value_at_risk(returns, confidence)
        return np.mean(returns[returns <= var])
    
    def _annualize_return(self, returns: np.ndarray) -> float:
        """Annualize returns"""
        if len(returns) == 0:
            return 0.0
        
        total_return = np.prod(1 + returns) - 1
        years = len(returns) / self.TRADING_DAYS_PER_YEAR
        
        if years <= 0:
            return 0.0
        
        return (1 + total_return) ** (1 / years) - 1
    
    def _annualize_volatility(self, returns: np.ndarray) -> float:
        """Annualize volatility"""
        if len(returns) == 0:
            return 0.0
        
        return np.std(returns) * np.sqrt(self.TRADING_DAYS_PER_YEAR)
    
    def _downside_deviation(self, returns: np.ndarray) -> float:
        """Calculate downside deviation (semi-deviation)"""
        if len(returns) == 0:
            return 0.0
        
        # Only consider returns below target (risk-free rate daily)
        daily_rf = self.risk_free_rate / self.TRADING_DAYS_PER_YEAR
        downside_returns = returns[returns < daily_rf]
        
        if len(downside_returns) == 0:
            return 0.0
        
        downside_var = np.mean((downside_returns - daily_rf) ** 2)
        return np.sqrt(downside_var) * np.sqrt(self.TRADING_DAYS_PER_YEAR)
    
    def _max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown"""
        if len(returns) == 0:
            return 0.0
        
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        
        return np.min(drawdowns)
    
    def calculate_from_signals(
        self,
        signals: List[Signal],
    ) -> RiskAdjustedMetrics:
        """
        Calculate metrics directly from signals
        
        Args:
            signals: List of completed signals
            
        Returns:
            RiskAdjustedMetrics
        """
        completed = [s for s in signals if s.outcome_return is not None]
        
        if not completed:
            return RiskAdjustedMetrics(risk_free_rate=self.risk_free_rate)
        
        returns = np.array([s.outcome_return for s in completed])
        return self.calculate_all(returns)
    
    def rolling_sharpe(
        self,
        returns: np.ndarray,
        window: int = 30,
    ) -> np.ndarray:
        """
        Calculate rolling Sharpe Ratio
        
        Args:
            returns: Array of returns
            window: Rolling window size
            
        Returns:
            Array of rolling Sharpe values
        """
        if len(returns) < window:
            return np.array([])
        
        rolling_sharpe = []
        
        for i in range(window, len(returns) + 1):
            window_returns = returns[i-window:i]
            sharpe = self.sharpe_ratio(window_returns)
            rolling_sharpe.append(sharpe)
        
        return np.array(rolling_sharpe)
