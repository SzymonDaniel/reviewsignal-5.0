"""
Drawdown Analysis for ReviewSignal Track Record System

Comprehensive drawdown metrics and analysis for risk management.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from track_record.performance.returns import ReturnSeries


logger = logging.getLogger(__name__)


@dataclass
class DrawdownPeriod:
    """
    Represents a single drawdown period.
    """
    start_date: datetime = field(default_factory=datetime.utcnow)
    trough_date: datetime = field(default_factory=datetime.utcnow)
    end_date: Optional[datetime] = None
    
    peak_value: float = 0.0           # Value at peak
    trough_value: float = 0.0         # Value at trough
    recovery_value: float = 0.0       # Value at recovery
    
    drawdown_pct: float = 0.0         # Max drawdown percentage
    drawdown_duration: int = 0        # Days from peak to trough
    recovery_duration: int = 0        # Days from trough to recovery
    total_duration: int = 0           # Total days underwater
    
    is_recovered: bool = False        # Whether fully recovered
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_date": self.start_date.isoformat(),
            "trough_date": self.trough_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "peak_value": self.peak_value,
            "trough_value": self.trough_value,
            "drawdown_pct": round(self.drawdown_pct, 2),
            "drawdown_duration": self.drawdown_duration,
            "recovery_duration": self.recovery_duration,
            "total_duration": self.total_duration,
            "is_recovered": self.is_recovered,
        }


@dataclass
class DrawdownMetrics:
    """
    Comprehensive drawdown metrics.
    """
    # Maximum drawdown
    max_drawdown: float = 0.0         # Maximum drawdown percentage
    max_drawdown_date: Optional[datetime] = None
    max_drawdown_period: Optional[DrawdownPeriod] = None
    
    # Average metrics
    avg_drawdown: float = 0.0         # Average drawdown depth
    avg_drawdown_duration: int = 0    # Average days in drawdown
    avg_recovery_duration: int = 0    # Average days to recover
    
    # Current status
    current_drawdown: float = 0.0     # Current drawdown (if any)
    days_in_current_dd: int = 0       # Days in current drawdown
    
    # Historical
    total_drawdown_periods: int = 0   # Number of drawdown periods
    drawdown_periods: List[DrawdownPeriod] = field(default_factory=list)
    
    # Time underwater
    percent_time_underwater: float = 0.0  # % of time in drawdown
    longest_drawdown_days: int = 0        # Longest drawdown duration
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_drawdown": round(self.max_drawdown, 2),
            "max_drawdown_date": self.max_drawdown_date.isoformat() if self.max_drawdown_date else None,
            "avg_drawdown": round(self.avg_drawdown, 2),
            "avg_drawdown_duration": self.avg_drawdown_duration,
            "avg_recovery_duration": self.avg_recovery_duration,
            "current_drawdown": round(self.current_drawdown, 2),
            "days_in_current_dd": self.days_in_current_dd,
            "total_drawdown_periods": self.total_drawdown_periods,
            "percent_time_underwater": round(self.percent_time_underwater, 1),
            "longest_drawdown_days": self.longest_drawdown_days,
        }


class DrawdownAnalyzer:
    """
    Analyze drawdowns from return series.
    
    Provides comprehensive drawdown analysis including:
    - Maximum drawdown calculation
    - Drawdown period identification
    - Recovery analysis
    - Underwater analysis
    
    Usage:
        analyzer = DrawdownAnalyzer()
        metrics = analyzer.analyze(return_series)
        
        print(f"Max Drawdown: {metrics.max_drawdown}%")
        print(f"Average Recovery: {metrics.avg_recovery_duration} days")
    """
    
    def __init__(self, starting_value: float = 100.0):
        """
        Initialize DrawdownAnalyzer.
        
        Args:
            starting_value: Starting portfolio value for calculations
        """
        self.starting_value = starting_value
    
    def analyze(self, return_series: ReturnSeries) -> DrawdownMetrics:
        """
        Perform comprehensive drawdown analysis.
        
        Args:
            return_series: Return series to analyze
            
        Returns:
            DrawdownMetrics with all calculations
        """
        metrics = DrawdownMetrics()
        
        if len(return_series) == 0:
            return metrics
        
        # Convert returns to equity curve
        equity_curve = self._returns_to_equity(return_series)
        
        # Calculate drawdown series
        drawdown_series = self._calculate_drawdown_series(equity_curve)
        
        # Find maximum drawdown
        max_dd_idx = 0
        max_dd = 0.0
        for i, dd in enumerate(drawdown_series):
            if dd < max_dd:
                max_dd = dd
                max_dd_idx = i
        
        metrics.max_drawdown = abs(max_dd)
        if max_dd_idx < len(return_series.dates):
            metrics.max_drawdown_date = return_series.dates[max_dd_idx]
        
        # Identify all drawdown periods
        metrics.drawdown_periods = self._identify_periods(
            return_series.dates,
            equity_curve,
            drawdown_series
        )
        
        metrics.total_drawdown_periods = len(metrics.drawdown_periods)
        
        # Calculate averages
        if metrics.drawdown_periods:
            depths = [p.drawdown_pct for p in metrics.drawdown_periods]
            metrics.avg_drawdown = sum(depths) / len(depths)
            
            durations = [p.drawdown_duration for p in metrics.drawdown_periods]
            metrics.avg_drawdown_duration = int(sum(durations) / len(durations))
            
            recovered = [p for p in metrics.drawdown_periods if p.is_recovered]
            if recovered:
                recovery_times = [p.recovery_duration for p in recovered]
                metrics.avg_recovery_duration = int(sum(recovery_times) / len(recovery_times))
            
            metrics.longest_drawdown_days = max(
                p.total_duration for p in metrics.drawdown_periods
            )
            
            # Find max drawdown period
            max_dd_period = max(metrics.drawdown_periods, key=lambda p: p.drawdown_pct)
            metrics.max_drawdown_period = max_dd_period
        
        # Current drawdown
        if drawdown_series and drawdown_series[-1] < 0:
            metrics.current_drawdown = abs(drawdown_series[-1])
            # Find when current drawdown started
            for i in range(len(drawdown_series) - 1, -1, -1):
                if drawdown_series[i] >= 0:
                    metrics.days_in_current_dd = len(drawdown_series) - i - 1
                    break
        
        # Percent time underwater
        underwater_days = sum(1 for dd in drawdown_series if dd < -0.1)  # -0.1% threshold
        total_days = len(drawdown_series)
        metrics.percent_time_underwater = (underwater_days / total_days * 100) if total_days > 0 else 0
        
        return metrics
    
    def _returns_to_equity(self, return_series: ReturnSeries) -> List[float]:
        """Convert return series to equity curve."""
        equity = [self.starting_value]
        
        for r in return_series.returns:
            new_value = equity[-1] * (1 + r / 100)
            equity.append(new_value)
        
        return equity[1:]  # Remove initial value
    
    def _calculate_drawdown_series(self, equity_curve: List[float]) -> List[float]:
        """Calculate drawdown at each point."""
        if not equity_curve:
            return []
        
        drawdowns = []
        running_max = equity_curve[0]
        
        for value in equity_curve:
            if value > running_max:
                running_max = value
            dd = ((value - running_max) / running_max) * 100
            drawdowns.append(dd)
        
        return drawdowns
    
    def _identify_periods(
        self,
        dates: List[datetime],
        equity: List[float],
        drawdowns: List[float],
    ) -> List[DrawdownPeriod]:
        """
        Identify distinct drawdown periods.
        """
        if not drawdowns:
            return []
        
        periods = []
        in_drawdown = False
        current_period = None
        running_max = equity[0]
        running_max_idx = 0
        
        for i, (date, value, dd) in enumerate(zip(dates, equity, drawdowns)):
            if value > running_max:
                running_max = value
                running_max_idx = i
            
            if not in_drawdown and dd < -0.1:  # Start of drawdown
                in_drawdown = True
                current_period = DrawdownPeriod(
                    start_date=dates[running_max_idx] if running_max_idx < len(dates) else date,
                    peak_value=running_max,
                )
                current_period.trough_date = date
                current_period.trough_value = value
                current_period.drawdown_pct = abs(dd)
            
            elif in_drawdown:
                if dd < -(current_period.drawdown_pct):  # Deeper drawdown
                    current_period.trough_date = date
                    current_period.trough_value = value
                    current_period.drawdown_pct = abs(dd)
                
                if dd >= 0:  # Recovery
                    in_drawdown = False
                    current_period.end_date = date
                    current_period.recovery_value = value
                    current_period.is_recovered = True
                    
                    # Calculate durations
                    current_period.drawdown_duration = (
                        current_period.trough_date - current_period.start_date
                    ).days
                    current_period.recovery_duration = (
                        current_period.end_date - current_period.trough_date
                    ).days
                    current_period.total_duration = (
                        current_period.end_date - current_period.start_date
                    ).days
                    
                    periods.append(current_period)
                    current_period = None
        
        # Handle ongoing drawdown
        if in_drawdown and current_period:
            current_period.drawdown_duration = (
                dates[-1] - current_period.start_date
            ).days if dates else 0
            current_period.total_duration = current_period.drawdown_duration
            periods.append(current_period)
        
        return periods
    
    def calculate_underwater_curve(
        self,
        return_series: ReturnSeries,
    ) -> Tuple[List[datetime], List[float]]:
        """
        Calculate underwater curve (drawdown over time).
        
        Returns:
            Tuple of (dates, underwater_values)
        """
        equity = self._returns_to_equity(return_series)
        drawdowns = self._calculate_drawdown_series(equity)
        
        return return_series.dates, drawdowns
