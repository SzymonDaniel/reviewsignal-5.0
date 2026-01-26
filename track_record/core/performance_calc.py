"""
Performance Calculator - Calculate returns and P&L metrics

This module calculates comprehensive performance metrics for
track record reporting to hedge fund clients.

Key Metrics:
- Total Return
- Annualized Return
- Win Rate
- Average Win/Loss
- Profit Factor
- Expectancy
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from loguru import logger

from .signal_logger import Signal, SignalType


@dataclass
class PerformanceMetrics:
    """Container for performance metrics"""
    # Returns
    total_return: float = 0.0
    annualized_return: float = 0.0
    cumulative_return: float = 0.0
    
    # Win/Loss
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # Average returns
    avg_return: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    
    # Risk metrics
    profit_factor: float = 0.0
    expectancy: float = 0.0
    payoff_ratio: float = 0.0
    
    # Streaks
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    current_streak: int = 0
    
    # Time-based
    avg_holding_period_days: float = 0.0
    trading_days: int = 0
    
    # P&L
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_return": round(self.total_return, 4),
            "annualized_return": round(self.annualized_return, 4),
            "cumulative_return": round(self.cumulative_return, 4),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 4),
            "avg_return": round(self.avg_return, 4),
            "avg_win": round(self.avg_win, 4),
            "avg_loss": round(self.avg_loss, 4),
            "profit_factor": round(self.profit_factor, 2),
            "expectancy": round(self.expectancy, 4),
            "payoff_ratio": round(self.payoff_ratio, 2),
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "avg_holding_period_days": round(self.avg_holding_period_days, 1),
            "gross_profit": round(self.gross_profit, 2),
            "gross_loss": round(self.gross_loss, 2),
            "net_profit": round(self.net_profit, 2),
        }


class PerformanceCalculator:
    """
    Performance Calculator for Track Record
    
    Calculates comprehensive trading performance metrics from
    signal history for hedge fund reporting.
    """
    
    def __init__(self, initial_capital: float = 100_000.0):
        """
        Initialize calculator
        
        Args:
            initial_capital: Starting capital for P&L calculations
        """
        self.initial_capital = initial_capital
        logger.info(f"PerformanceCalculator initialized | Capital: ${initial_capital:,.2f}")
    
    def calculate(
        self,
        signals: List[Signal],
        position_size: float = 0.1,  # 10% of capital per trade
    ) -> PerformanceMetrics:
        """
        Calculate performance metrics from signals
        
        Args:
            signals: List of completed signals with outcomes
            position_size: Fraction of capital per trade
            
        Returns:
            PerformanceMetrics object
        """
        # Filter to completed signals only
        completed = [s for s in signals if s.outcome_return is not None]
        
        if not completed:
            logger.warning("No completed signals to calculate performance")
            return PerformanceMetrics()
        
        metrics = PerformanceMetrics()
        
        # Basic counts
        metrics.total_trades = len(completed)
        metrics.winning_trades = len([s for s in completed if s.is_winner])
        metrics.losing_trades = metrics.total_trades - metrics.winning_trades
        
        # Win rate
        metrics.win_rate = metrics.winning_trades / metrics.total_trades
        
        # Returns
        returns = [s.outcome_return for s in completed]
        metrics.avg_return = np.mean(returns)
        metrics.total_return = sum(returns)
        metrics.cumulative_return = np.prod([1 + r for r in returns]) - 1
        
        # Separate wins and losses
        wins = [s.outcome_return for s in completed if s.is_winner]
        losses = [s.outcome_return for s in completed if not s.is_winner]
        
        metrics.avg_win = np.mean(wins) if wins else 0.0
        metrics.avg_loss = np.mean(losses) if losses else 0.0
        
        # Profit Factor = Gross Profit / Gross Loss
        metrics.gross_profit = sum(wins) if wins else 0.0
        metrics.gross_loss = abs(sum(losses)) if losses else 0.0
        metrics.net_profit = metrics.gross_profit - metrics.gross_loss
        
        if metrics.gross_loss > 0:
            metrics.profit_factor = metrics.gross_profit / metrics.gross_loss
        else:
            metrics.profit_factor = float('inf') if metrics.gross_profit > 0 else 0.0
        
        # Payoff Ratio = Avg Win / Avg Loss
        if metrics.avg_loss != 0:
            metrics.payoff_ratio = abs(metrics.avg_win / metrics.avg_loss)
        else:
            metrics.payoff_ratio = float('inf') if metrics.avg_win > 0 else 0.0
        
        # Expectancy = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
        metrics.expectancy = (
            metrics.win_rate * metrics.avg_win
            - (1 - metrics.win_rate) * abs(metrics.avg_loss)
        )
        
        # Streaks
        metrics.max_consecutive_wins, metrics.max_consecutive_losses = (
            self._calculate_streaks(completed)
        )
        
        # Time-based metrics
        metrics.avg_holding_period_days = self._calculate_avg_holding_period(completed)
        metrics.trading_days = self._calculate_trading_days(completed)
        
        # Annualized return
        if metrics.trading_days > 0:
            years = metrics.trading_days / 252  # Trading days per year
            if years > 0:
                metrics.annualized_return = (
                    (1 + metrics.cumulative_return) ** (1 / years) - 1
                )
        
        logger.info(
            f"Performance calculated | "
            f"Trades: {metrics.total_trades} | "
            f"Win Rate: {metrics.win_rate:.1%} | "
            f"Total Return: {metrics.total_return:.2%}"
        )
        
        return metrics
    
    def _calculate_streaks(self, signals: List[Signal]) -> Tuple[int, int]:
        """Calculate max consecutive wins and losses"""
        if not signals:
            return 0, 0
        
        # Sort by date
        sorted_signals = sorted(signals, key=lambda s: s.generated_at)
        
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0
        
        for signal in sorted_signals:
            if signal.is_winner:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
        
        return max_wins, max_losses
    
    def _calculate_avg_holding_period(self, signals: List[Signal]) -> float:
        """Calculate average holding period in days"""
        holding_periods = []
        
        for signal in signals:
            if signal.outcome_date and signal.generated_at:
                delta = signal.outcome_date - signal.generated_at
                holding_periods.append(delta.days)
        
        return np.mean(holding_periods) if holding_periods else 0.0
    
    def _calculate_trading_days(self, signals: List[Signal]) -> int:
        """Calculate total trading days spanned"""
        if not signals:
            return 0
        
        dates = [s.generated_at for s in signals]
        min_date = min(dates)
        max_date = max(dates)
        
        return (max_date - min_date).days
    
    def calculate_monthly_returns(
        self,
        signals: List[Signal],
    ) -> pd.DataFrame:
        """
        Calculate monthly return breakdown
        
        Args:
            signals: List of completed signals
            
        Returns:
            DataFrame with monthly returns
        """
        completed = [s for s in signals if s.outcome_return is not None]
        
        if not completed:
            return pd.DataFrame()
        
        # Create DataFrame
        df = pd.DataFrame([
            {
                "date": s.generated_at,
                "return": s.outcome_return,
                "symbol": s.symbol,
                "is_winner": s.is_winner,
            }
            for s in completed
        ])
        
        df["month"] = df["date"].dt.to_period("M")
        
        # Group by month
        monthly = df.groupby("month").agg({
            "return": ["sum", "mean", "count"],
            "is_winner": "sum",
        })
        
        monthly.columns = ["total_return", "avg_return", "trade_count", "wins"]
        monthly["win_rate"] = monthly["wins"] / monthly["trade_count"]
        
        return monthly.reset_index()
    
    def calculate_by_symbol(
        self,
        signals: List[Signal],
    ) -> Dict[str, PerformanceMetrics]:
        """
        Calculate performance metrics by symbol
        
        Args:
            signals: List of completed signals
            
        Returns:
            Dictionary mapping symbol to metrics
        """
        completed = [s for s in signals if s.outcome_return is not None]
        
        # Group by symbol
        symbols = set(s.symbol for s in completed)
        
        results = {}
        for symbol in symbols:
            symbol_signals = [s for s in completed if s.symbol == symbol]
            results[symbol] = self.calculate(symbol_signals)
        
        return results
    
    def calculate_by_signal_source(
        self,
        signals: List[Signal],
    ) -> Dict[str, PerformanceMetrics]:
        """
        Calculate performance metrics by signal source
        
        Useful for determining which signal sources perform best.
        
        Args:
            signals: List of completed signals
            
        Returns:
            Dictionary mapping source to metrics
        """
        completed = [s for s in signals if s.outcome_return is not None]
        
        # Group by source
        sources = set(s.source.value for s in completed)
        
        results = {}
        for source in sources:
            source_signals = [s for s in completed if s.source.value == source]
            results[source] = self.calculate(source_signals)
        
        return results
    
    def generate_equity_curve(
        self,
        signals: List[Signal],
        position_size: float = 0.1,
    ) -> pd.DataFrame:
        """
        Generate equity curve from signals
        
        Args:
            signals: List of completed signals
            position_size: Fraction of capital per trade
            
        Returns:
            DataFrame with equity curve
        """
        completed = [s for s in signals if s.outcome_return is not None]
        
        if not completed:
            return pd.DataFrame()
        
        # Sort by date
        sorted_signals = sorted(completed, key=lambda s: s.generated_at)
        
        # Calculate equity curve
        equity = self.initial_capital
        curve_data = [{
            "date": sorted_signals[0].generated_at - timedelta(days=1),
            "equity": equity,
            "drawdown": 0.0,
            "return": 0.0,
        }]
        
        peak_equity = equity
        
        for signal in sorted_signals:
            # Calculate P&L for this trade
            trade_capital = equity * position_size
            trade_pnl = trade_capital * signal.outcome_return
            equity += trade_pnl
            
            # Track peak and drawdown
            peak_equity = max(peak_equity, equity)
            drawdown = (equity - peak_equity) / peak_equity if peak_equity > 0 else 0.0
            
            curve_data.append({
                "date": signal.outcome_date or signal.generated_at,
                "equity": equity,
                "drawdown": drawdown,
                "return": signal.outcome_return,
                "symbol": signal.symbol,
                "signal_type": signal.signal_type.value,
            })
        
        return pd.DataFrame(curve_data)
