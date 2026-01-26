"""
Return Calculations for ReviewSignal Track Record System

Comprehensive return calculation engine supporting multiple
return types and time periods.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import math

from track_record.core.signal_types import Signal, SignalStatus


logger = logging.getLogger(__name__)


@dataclass
class ReturnSeries:
    """
    A time series of returns.
    """
    dates: List[datetime] = field(default_factory=list)
    returns: List[float] = field(default_factory=list)  # Percentage returns
    cumulative: List[float] = field(default_factory=list)  # Cumulative returns
    
    def __len__(self) -> int:
        return len(self.returns)
    
    def add(self, date: datetime, return_pct: float) -> None:
        """Add a return to the series."""
        self.dates.append(date)
        self.returns.append(return_pct)
        
        # Calculate cumulative
        if not self.cumulative:
            self.cumulative.append(return_pct)
        else:
            prev_cum = self.cumulative[-1]
            new_cum = (1 + prev_cum / 100) * (1 + return_pct / 100) - 1
            self.cumulative.append(new_cum * 100)
    
    @property
    def total_return(self) -> float:
        """Get total cumulative return."""
        if not self.cumulative:
            return 0.0
        return self.cumulative[-1]
    
    @property
    def mean_return(self) -> float:
        """Get mean return."""
        if not self.returns:
            return 0.0
        return sum(self.returns) / len(self.returns)
    
    @property
    def std_return(self) -> float:
        """Get standard deviation of returns."""
        if len(self.returns) < 2:
            return 0.0
        mean = self.mean_return
        variance = sum((r - mean) ** 2 for r in self.returns) / (len(self.returns) - 1)
        return math.sqrt(variance)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "dates": [d.isoformat() for d in self.dates],
            "returns": self.returns,
            "cumulative": self.cumulative,
            "total_return": self.total_return,
            "mean_return": self.mean_return,
            "std_return": self.std_return,
        }


class ReturnCalculator:
    """
    Calculate returns from signals and price data.
    
    Supports:
    - Simple returns
    - Log returns
    - Risk-adjusted returns
    - Time-weighted returns
    - Money-weighted returns (IRR)
    
    Usage:
        calculator = ReturnCalculator()
        
        # From closed signals
        returns = calculator.calculate_from_signals(signals)
        
        # Annualized
        annual = calculator.annualize(returns, periods_per_year=252)
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.05,  # 5% annual risk-free rate
        trading_days_per_year: int = 252,
    ):
        """
        Initialize ReturnCalculator.
        
        Args:
            risk_free_rate: Annual risk-free rate for excess return calculations
            trading_days_per_year: Number of trading days per year
        """
        self.risk_free_rate = risk_free_rate
        self.trading_days_per_year = trading_days_per_year
        self.daily_risk_free = (1 + risk_free_rate) ** (1 / trading_days_per_year) - 1
    
    def calculate_from_signals(
        self,
        signals: List[Signal],
        include_pending: bool = False,
    ) -> ReturnSeries:
        """
        Calculate return series from a list of signals.
        
        Args:
            signals: List of Signal objects
            include_pending: Whether to include unrealized returns from active signals
            
        Returns:
            ReturnSeries with calculated returns
        """
        series = ReturnSeries()
        
        # Filter and sort signals
        if include_pending:
            valid_signals = [s for s in signals if s.return_pct is not None or s.is_active]
        else:
            valid_signals = [s for s in signals if s.is_closed and s.return_pct is not None]
        
        valid_signals.sort(key=lambda s: s.closed_at or s.created_at)
        
        for signal in valid_signals:
            date = signal.closed_at or signal.updated_at or signal.created_at
            return_pct = signal.return_pct or 0.0
            series.add(date, return_pct)
        
        return series
    
    def calculate_simple_return(
        self,
        entry_price: float,
        exit_price: float,
        is_long: bool = True,
    ) -> float:
        """
        Calculate simple percentage return.
        
        Args:
            entry_price: Entry price
            exit_price: Exit price
            is_long: True for long position, False for short
            
        Returns:
            Percentage return
        """
        if entry_price <= 0:
            return 0.0
        
        if is_long:
            return ((exit_price - entry_price) / entry_price) * 100
        else:
            return ((entry_price - exit_price) / entry_price) * 100
    
    def calculate_log_return(
        self,
        entry_price: float,
        exit_price: float,
    ) -> float:
        """
        Calculate logarithmic return.
        
        Args:
            entry_price: Entry price
            exit_price: Exit price
            
        Returns:
            Log return (for compounding)
        """
        if entry_price <= 0 or exit_price <= 0:
            return 0.0
        return math.log(exit_price / entry_price) * 100
    
    def calculate_excess_return(
        self,
        return_pct: float,
        holding_period_days: int,
    ) -> float:
        """
        Calculate excess return over risk-free rate.
        
        Args:
            return_pct: Actual return percentage
            holding_period_days: Number of days held
            
        Returns:
            Excess return percentage
        """
        rf_return = self.daily_risk_free * holding_period_days * 100
        return return_pct - rf_return
    
    def annualize_return(
        self,
        return_pct: float,
        holding_period_days: int,
    ) -> float:
        """
        Annualize a return based on holding period.
        
        Args:
            return_pct: Return percentage
            holding_period_days: Number of days held
            
        Returns:
            Annualized return percentage
        """
        if holding_period_days <= 0:
            return 0.0
        
        # Convert to decimal, annualize, convert back to percentage
        return_decimal = return_pct / 100
        annual_decimal = (1 + return_decimal) ** (self.trading_days_per_year / holding_period_days) - 1
        return annual_decimal * 100
    
    def calculate_portfolio_return(
        self,
        signals: List[Signal],
        weights: Optional[List[float]] = None,
    ) -> float:
        """
        Calculate weighted portfolio return from multiple signals.
        
        Args:
            signals: List of closed signals
            weights: Optional position weights (equal weight if not provided)
            
        Returns:
            Portfolio return percentage
        """
        closed_signals = [s for s in signals if s.is_closed and s.return_pct is not None]
        
        if not closed_signals:
            return 0.0
        
        if weights is None:
            weights = [1.0 / len(closed_signals)] * len(closed_signals)
        
        if len(weights) != len(closed_signals):
            raise ValueError("Weights length must match signals length")
        
        portfolio_return = sum(
            w * s.return_pct for w, s in zip(weights, closed_signals)
        )
        
        return portfolio_return
    
    def calculate_twrr(
        self,
        period_returns: List[float],
    ) -> float:
        """
        Calculate Time-Weighted Rate of Return (TWRR).
        
        TWRR eliminates the impact of cash flows and measures
        pure investment performance.
        
        Args:
            period_returns: List of period returns (as percentages)
            
        Returns:
            TWRR as percentage
        """
        if not period_returns:
            return 0.0
        
        # Product of (1 + r) for all periods
        cumulative = 1.0
        for r in period_returns:
            cumulative *= (1 + r / 100)
        
        return (cumulative - 1) * 100
    
    def calculate_mwrr(
        self,
        cash_flows: List[Tuple[datetime, float]],
        ending_value: float,
    ) -> float:
        """
        Calculate Money-Weighted Rate of Return (MWRR / IRR).
        
        MWRR accounts for the timing and size of cash flows.
        
        Args:
            cash_flows: List of (date, amount) tuples. Negative = investment.
            ending_value: Final portfolio value
            
        Returns:
            MWRR as annualized percentage
        """
        if not cash_flows:
            return 0.0
        
        # Newton-Raphson method to find IRR
        def npv(rate: float) -> float:
            """Calculate NPV at given rate."""
            start_date = cash_flows[0][0]
            total = 0.0
            
            for date, amount in cash_flows:
                years = (date - start_date).days / 365
                total += amount / ((1 + rate) ** years)
            
            # Add ending value
            end_date = max(cf[0] for cf in cash_flows)
            years = (end_date - start_date).days / 365
            total += ending_value / ((1 + rate) ** years)
            
            return total
        
        # Find IRR using bisection method
        low, high = -0.99, 10.0
        tolerance = 0.0001
        max_iterations = 100
        
        for _ in range(max_iterations):
            mid = (low + high) / 2
            npv_mid = npv(mid)
            
            if abs(npv_mid) < tolerance:
                return mid * 100
            
            if npv_mid > 0:
                low = mid
            else:
                high = mid
        
        return ((low + high) / 2) * 100
    
    def aggregate_daily_returns(
        self,
        signals: List[Signal],
        start_date: datetime,
        end_date: datetime,
    ) -> ReturnSeries:
        """
        Aggregate signals into daily returns.
        
        Useful for calculating risk metrics that require daily data.
        
        Args:
            signals: List of signals
            start_date: Start of period
            end_date: End of period
            
        Returns:
            Daily return series
        """
        from collections import defaultdict
        
        # Group signals by close date
        daily_returns = defaultdict(float)
        daily_counts = defaultdict(int)
        
        for signal in signals:
            if signal.is_closed and signal.return_pct is not None and signal.closed_at:
                date_key = signal.closed_at.date()
                if start_date.date() <= date_key <= end_date.date():
                    daily_returns[date_key] += signal.return_pct
                    daily_counts[date_key] += 1
        
        # Average returns for days with multiple signals
        for date_key in daily_returns:
            if daily_counts[date_key] > 1:
                daily_returns[date_key] /= daily_counts[date_key]
        
        # Create series
        series = ReturnSeries()
        current_date = start_date.date()
        end = end_date.date()
        
        while current_date <= end:
            # Skip weekends
            if current_date.weekday() < 5:
                return_pct = daily_returns.get(current_date, 0.0)
                series.add(
                    datetime.combine(current_date, datetime.min.time()),
                    return_pct
                )
            current_date += timedelta(days=1)
        
        return series
    
    def calculate_win_loss_stats(
        self,
        signals: List[Signal],
    ) -> Dict[str, Any]:
        """
        Calculate win/loss statistics.
        
        Args:
            signals: List of closed signals
            
        Returns:
            Dictionary with win/loss statistics
        """
        closed_signals = [
            s for s in signals 
            if s.is_closed and s.return_pct is not None
        ]
        
        if not closed_signals:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "win_loss_ratio": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
            }
        
        winners = [s for s in closed_signals if s.return_pct > 0]
        losers = [s for s in closed_signals if s.return_pct < 0]
        
        total_trades = len(closed_signals)
        winning_trades = len(winners)
        losing_trades = len(losers)
        
        avg_win = sum(s.return_pct for s in winners) / len(winners) if winners else 0.0
        avg_loss = abs(sum(s.return_pct for s in losers) / len(losers)) if losers else 0.0
        
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0.0
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float('inf')
        
        gross_profit = sum(s.return_pct for s in winners) if winners else 0.0
        gross_loss = abs(sum(s.return_pct for s in losers)) if losers else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Expectancy = (Win% × Avg Win) - (Loss% × Avg Loss)
        expectancy = (win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss)
        
        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "win_loss_ratio": win_loss_ratio,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "largest_win": max((s.return_pct for s in winners), default=0.0),
            "largest_loss": min((s.return_pct for s in losers), default=0.0),
            "avg_holding_days": sum(s.holding_period_days or 0 for s in closed_signals) / total_trades,
        }
