"""
Drawdown Analyzer - Comprehensive drawdown analysis

Analyzes portfolio drawdowns for risk management:
- Maximum Drawdown
- Drawdown Duration
- Recovery Time
- Underwater Periods
- Drawdown Distribution

Usage:
    analyzer = DrawdownAnalyzer()
    analysis = analyzer.analyze(returns)
    print(analysis.summary())
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger

from .signal_logger import Signal


@dataclass
class DrawdownPeriod:
    """Single drawdown period"""
    start_idx: int = 0
    trough_idx: int = 0
    end_idx: Optional[int] = None  # None if not recovered
    
    peak_value: float = 0.0
    trough_value: float = 0.0
    recovery_value: Optional[float] = None
    
    drawdown_pct: float = 0.0
    duration_to_trough: int = 0  # Days to reach bottom
    recovery_duration: Optional[int] = None  # Days to recover
    total_duration: Optional[int] = None  # Total underwater days
    
    start_date: Optional[datetime] = None
    trough_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    def is_recovered(self) -> bool:
        """Check if drawdown has recovered"""
        return self.end_idx is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "drawdown_pct": round(self.drawdown_pct, 4),
            "peak_value": round(self.peak_value, 4),
            "trough_value": round(self.trough_value, 4),
            "duration_to_trough": self.duration_to_trough,
            "recovery_duration": self.recovery_duration,
            "total_duration": self.total_duration,
            "is_recovered": self.is_recovered(),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "trough_date": self.trough_date.isoformat() if self.trough_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
        }


@dataclass
class DrawdownAnalysis:
    """Complete drawdown analysis results"""
    # Max drawdown
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0  # Days
    max_recovery_time: int = 0  # Days
    
    # Current state
    current_drawdown: float = 0.0
    is_in_drawdown: bool = False
    days_in_current_drawdown: int = 0
    
    # Statistics
    avg_drawdown: float = 0.0
    avg_duration: float = 0.0
    avg_recovery_time: float = 0.0
    
    # Counts
    total_drawdown_periods: int = 0
    recovered_periods: int = 0
    ongoing_periods: int = 0
    
    # Distribution
    drawdown_5th_percentile: float = 0.0
    drawdown_25th_percentile: float = 0.0
    drawdown_median: float = 0.0
    drawdown_75th_percentile: float = 0.0
    drawdown_95th_percentile: float = 0.0
    
    # Time underwater
    total_underwater_days: int = 0
    pct_time_underwater: float = 0.0
    
    # Individual periods
    drawdown_periods: List[DrawdownPeriod] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "max_drawdown": round(self.max_drawdown, 4),
            "max_drawdown_duration": self.max_drawdown_duration,
            "max_recovery_time": self.max_recovery_time,
            "current_drawdown": round(self.current_drawdown, 4),
            "is_in_drawdown": self.is_in_drawdown,
            "days_in_current_drawdown": self.days_in_current_drawdown,
            "avg_drawdown": round(self.avg_drawdown, 4),
            "avg_duration": round(self.avg_duration, 1),
            "avg_recovery_time": round(self.avg_recovery_time, 1),
            "total_drawdown_periods": self.total_drawdown_periods,
            "recovered_periods": self.recovered_periods,
            "ongoing_periods": self.ongoing_periods,
            "total_underwater_days": self.total_underwater_days,
            "pct_time_underwater": round(self.pct_time_underwater, 4),
            "distribution": {
                "5th": round(self.drawdown_5th_percentile, 4),
                "25th": round(self.drawdown_25th_percentile, 4),
                "median": round(self.drawdown_median, 4),
                "75th": round(self.drawdown_75th_percentile, 4),
                "95th": round(self.drawdown_95th_percentile, 4),
            },
            "top_5_drawdowns": [
                dd.to_dict() for dd in sorted(
                    self.drawdown_periods,
                    key=lambda x: x.drawdown_pct
                )[:5]
            ],
        }
    
    def summary(self) -> str:
        """Generate human-readable summary"""
        status = "🔴 IN DRAWDOWN" if self.is_in_drawdown else "🟢 AT OR NEAR PEAK"
        
        return (
            f"\n{'='*60}\n"
            f"DRAWDOWN ANALYSIS\n"
            f"{'='*60}\n"
            f"\nCurrent Status: {status}\n"
            f"Current Drawdown: {self.current_drawdown:.2%}\n\n"
            f"MAXIMUM DRAWDOWN:\n"
            f"  Max Drawdown:      {self.max_drawdown:>10.2%}\n"
            f"  Duration:          {self.max_drawdown_duration:>10} days\n"
            f"  Recovery Time:     {self.max_recovery_time:>10} days\n\n"
            f"STATISTICS:\n"
            f"  Total Periods:     {self.total_drawdown_periods:>10}\n"
            f"  Recovered:         {self.recovered_periods:>10}\n"
            f"  Avg Drawdown:      {self.avg_drawdown:>10.2%}\n"
            f"  Avg Duration:      {self.avg_duration:>10.1f} days\n"
            f"  Avg Recovery:      {self.avg_recovery_time:>10.1f} days\n\n"
            f"TIME UNDERWATER:\n"
            f"  Total Days:        {self.total_underwater_days:>10}\n"
            f"  Percentage:        {self.pct_time_underwater:>10.1%}\n"
            f"{'='*60}\n"
        )
    
    def risk_assessment(self) -> Dict[str, str]:
        """Assess drawdown risk levels"""
        assessment = {}
        
        # Max drawdown assessment
        if abs(self.max_drawdown) <= 0.10:
            assessment["max_dd_risk"] = "🟢 LOW - Max DD under 10%"
        elif abs(self.max_drawdown) <= 0.20:
            assessment["max_dd_risk"] = "🟡 MODERATE - Max DD 10-20%"
        elif abs(self.max_drawdown) <= 0.30:
            assessment["max_dd_risk"] = "🟠 ELEVATED - Max DD 20-30%"
        else:
            assessment["max_dd_risk"] = "🔴 HIGH - Max DD over 30%"
        
        # Recovery time assessment
        if self.max_recovery_time <= 30:
            assessment["recovery_risk"] = "🟢 FAST - Recovers within 30 days"
        elif self.max_recovery_time <= 90:
            assessment["recovery_risk"] = "🟡 MODERATE - 30-90 day recovery"
        elif self.max_recovery_time <= 180:
            assessment["recovery_risk"] = "🟠 SLOW - 90-180 day recovery"
        else:
            assessment["recovery_risk"] = "🔴 PROLONGED - Over 180 day recovery"
        
        # Time underwater assessment
        if self.pct_time_underwater <= 0.20:
            assessment["underwater_risk"] = "🟢 LOW - Under 20% time underwater"
        elif self.pct_time_underwater <= 0.40:
            assessment["underwater_risk"] = "🟡 MODERATE - 20-40% underwater"
        elif self.pct_time_underwater <= 0.60:
            assessment["underwater_risk"] = "🟠 ELEVATED - 40-60% underwater"
        else:
            assessment["underwater_risk"] = "🔴 HIGH - Over 60% underwater"
        
        return assessment


class DrawdownAnalyzer:
    """
    Comprehensive Drawdown Analyzer
    
    Analyzes portfolio drawdowns for hedge fund risk reporting.
    Identifies all drawdown periods, calculates recovery times,
    and provides risk assessment.
    """
    
    def __init__(self, threshold: float = 0.01):
        """
        Initialize analyzer
        
        Args:
            threshold: Minimum drawdown to track (default 1%)
        """
        self.threshold = threshold
        logger.info(f"DrawdownAnalyzer initialized | Threshold: {threshold:.2%}")
    
    def analyze(
        self,
        returns: np.ndarray,
        dates: Optional[List[datetime]] = None,
    ) -> DrawdownAnalysis:
        """
        Analyze drawdowns from returns
        
        Args:
            returns: Array of returns
            dates: Optional list of dates for each return
            
        Returns:
            DrawdownAnalysis object
        """
        if len(returns) == 0:
            return DrawdownAnalysis()
        
        # Calculate cumulative returns and drawdowns
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        
        analysis = DrawdownAnalysis()
        
        # Max drawdown
        analysis.max_drawdown = np.min(drawdowns)
        
        # Identify all drawdown periods
        analysis.drawdown_periods = self._identify_periods(
            cumulative, running_max, drawdowns, dates
        )
        
        # Filter by threshold
        significant_periods = [
            p for p in analysis.drawdown_periods
            if abs(p.drawdown_pct) >= self.threshold
        ]
        analysis.drawdown_periods = significant_periods
        
        # Count periods
        analysis.total_drawdown_periods = len(significant_periods)
        analysis.recovered_periods = len([p for p in significant_periods if p.is_recovered()])
        analysis.ongoing_periods = analysis.total_drawdown_periods - analysis.recovered_periods
        
        if significant_periods:
            # Find max drawdown period details
            max_dd_period = min(significant_periods, key=lambda x: x.drawdown_pct)
            analysis.max_drawdown_duration = max_dd_period.total_duration or max_dd_period.duration_to_trough
            analysis.max_recovery_time = max_dd_period.recovery_duration or 0
            
            # Average stats
            analysis.avg_drawdown = np.mean([p.drawdown_pct for p in significant_periods])
            durations = [p.total_duration for p in significant_periods if p.total_duration]
            analysis.avg_duration = np.mean(durations) if durations else 0
            
            recoveries = [p.recovery_duration for p in significant_periods if p.recovery_duration]
            analysis.avg_recovery_time = np.mean(recoveries) if recoveries else 0
            
            # Distribution
            dd_values = [p.drawdown_pct for p in significant_periods]
            analysis.drawdown_5th_percentile = np.percentile(dd_values, 5)
            analysis.drawdown_25th_percentile = np.percentile(dd_values, 25)
            analysis.drawdown_median = np.percentile(dd_values, 50)
            analysis.drawdown_75th_percentile = np.percentile(dd_values, 75)
            analysis.drawdown_95th_percentile = np.percentile(dd_values, 95)
        
        # Current state
        analysis.current_drawdown = drawdowns[-1]
        analysis.is_in_drawdown = analysis.current_drawdown < -self.threshold
        
        if analysis.is_in_drawdown:
            # Find when current drawdown started
            for i in range(len(drawdowns) - 1, -1, -1):
                if drawdowns[i] >= -self.threshold:
                    analysis.days_in_current_drawdown = len(drawdowns) - 1 - i
                    break
        
        # Time underwater
        underwater_days = np.sum(drawdowns < -self.threshold)
        analysis.total_underwater_days = int(underwater_days)
        analysis.pct_time_underwater = underwater_days / len(drawdowns)
        
        logger.info(
            f"Drawdown analysis complete | "
            f"Max DD: {analysis.max_drawdown:.2%} | "
            f"Periods: {analysis.total_drawdown_periods} | "
            f"Underwater: {analysis.pct_time_underwater:.1%}"
        )
        
        return analysis
    
    def _identify_periods(
        self,
        cumulative: np.ndarray,
        running_max: np.ndarray,
        drawdowns: np.ndarray,
        dates: Optional[List[datetime]],
    ) -> List[DrawdownPeriod]:
        """Identify all drawdown periods"""
        periods = []
        in_drawdown = False
        current_period = None
        
        for i in range(len(drawdowns)):
            dd = drawdowns[i]
            
            if not in_drawdown and dd < -self.threshold:
                # Start of new drawdown
                in_drawdown = True
                current_period = DrawdownPeriod(
                    start_idx=i,
                    trough_idx=i,
                    peak_value=running_max[i],
                    trough_value=cumulative[i],
                    drawdown_pct=dd,
                    start_date=dates[i] if dates else None,
                    trough_date=dates[i] if dates else None,
                )
            
            elif in_drawdown:
                if dd < current_period.drawdown_pct:
                    # New trough
                    current_period.trough_idx = i
                    current_period.trough_value = cumulative[i]
                    current_period.drawdown_pct = dd
                    current_period.trough_date = dates[i] if dates else None
                
                if dd >= 0:
                    # Recovered
                    current_period.end_idx = i
                    current_period.recovery_value = cumulative[i]
                    current_period.end_date = dates[i] if dates else None
                    current_period.duration_to_trough = (
                        current_period.trough_idx - current_period.start_idx
                    )
                    current_period.recovery_duration = (
                        current_period.end_idx - current_period.trough_idx
                    )
                    current_period.total_duration = (
                        current_period.end_idx - current_period.start_idx
                    )
                    
                    periods.append(current_period)
                    in_drawdown = False
                    current_period = None
        
        # Handle ongoing drawdown
        if in_drawdown and current_period:
            current_period.duration_to_trough = (
                current_period.trough_idx - current_period.start_idx
            )
            periods.append(current_period)
        
        return periods
    
    def analyze_from_signals(
        self,
        signals: List[Signal],
    ) -> DrawdownAnalysis:
        """
        Analyze drawdowns from signals
        
        Args:
            signals: List of completed signals
            
        Returns:
            DrawdownAnalysis
        """
        completed = [s for s in signals if s.outcome_return is not None]
        
        if not completed:
            return DrawdownAnalysis()
        
        # Sort by date
        sorted_signals = sorted(completed, key=lambda s: s.generated_at)
        
        returns = np.array([s.outcome_return for s in sorted_signals])
        dates = [s.outcome_date or s.generated_at for s in sorted_signals]
        
        return self.analyze(returns, dates)
    
    def underwater_curve(
        self,
        returns: np.ndarray,
    ) -> pd.DataFrame:
        """
        Generate underwater equity curve
        
        Shows how long and how deep portfolio was underwater.
        
        Args:
            returns: Array of returns
            
        Returns:
            DataFrame with underwater curve
        """
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        
        return pd.DataFrame({
            "cumulative_return": cumulative,
            "high_water_mark": running_max,
            "drawdown": drawdowns,
            "is_underwater": drawdowns < 0,
        })
    
    def stress_test(
        self,
        returns: np.ndarray,
        scenarios: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """
        Stress test portfolio against historical scenarios
        
        Args:
            returns: Array of returns
            scenarios: Dictionary of scenario name to market drop
            
        Returns:
            Dictionary of scenario results
        """
        if scenarios is None:
            scenarios = {
                "2008_Financial_Crisis": -0.50,
                "2020_COVID_Crash": -0.34,
                "2022_Bear_Market": -0.25,
                "Flash_Crash": -0.10,
                "Mild_Correction": -0.05,
            }
        
        # Calculate portfolio beta to market (simplified)
        portfolio_vol = np.std(returns) * np.sqrt(252)
        market_vol = 0.15  # Assume 15% market vol
        
        # Assume correlation of 0.6 with market
        beta = (portfolio_vol / market_vol) * 0.6
        
        results = {}
        for scenario_name, market_drop in scenarios.items():
            expected_drop = market_drop * beta
            results[scenario_name] = expected_drop
        
        return results
