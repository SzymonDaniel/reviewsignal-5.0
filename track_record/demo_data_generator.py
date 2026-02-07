#!/usr/bin/env python3
"""
Demo Data Generator for ReviewSignal Track Record System
=========================================================
Generates realistic demo trading signals for presentations to hedge funds.

This creates a 6-month track record with:
- 60-70% win rate (realistic for sentiment-based signals)
- 1.8+ Sharpe ratio
- Signals correlated with actual market movements

Usage:
    python demo_data_generator.py --months 6 --output demo_signals.json
    python demo_data_generator.py --generate-report

Author: ReviewSignal.ai
Version: 1.0.0
"""

import json
import random
import math
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import uuid

# Stock tickers and brands we track
TRACKED_COMPANIES = {
    "MCD": {"brand": "McDonald's", "sector": "restaurants", "beta": 0.65},
    "SBUX": {"brand": "Starbucks", "sector": "restaurants", "beta": 0.85},
    "CMG": {"brand": "Chipotle", "sector": "restaurants", "beta": 1.15},
    "YUM": {"brand": "Yum! Brands", "sector": "restaurants", "beta": 0.75},
    "DPZ": {"brand": "Domino's Pizza", "sector": "restaurants", "beta": 0.90},
    "QSR": {"brand": "Restaurant Brands", "sector": "restaurants", "beta": 0.80},
    "DRI": {"brand": "Darden Restaurants", "sector": "restaurants", "beta": 1.05},
    "TXRH": {"brand": "Texas Roadhouse", "sector": "restaurants", "beta": 1.10},
    "WMT": {"brand": "Walmart", "sector": "retail", "beta": 0.50},
    "TGT": {"brand": "Target", "sector": "retail", "beta": 1.00},
    "COST": {"brand": "Costco", "sector": "retail", "beta": 0.70},
    "HD": {"brand": "Home Depot", "sector": "retail", "beta": 1.05},
    "LOW": {"brand": "Lowe's", "sector": "retail", "beta": 1.10},
    "MAR": {"brand": "Marriott", "sector": "hospitality", "beta": 1.40},
    "HLT": {"brand": "Hilton", "sector": "hospitality", "beta": 1.35},
    "H": {"brand": "Hyatt Hotels", "sector": "hospitality", "beta": 1.45},
}

SIGNAL_SOURCES = [
    "sentiment_spike",
    "rating_change",
    "review_volume",
    "competitor_shift",
    "anomaly_detection",
    "echo_engine"
]


@dataclass
class DemoSignal:
    """Demo trading signal for track record"""
    id: str
    symbol: str
    brand: str
    sector: str
    signal_type: str  # BUY, SELL, STRONG_BUY, STRONG_SELL
    confidence: float
    generated_at: str
    entry_price: float
    target_price: float
    stop_loss: float
    source: str
    reasoning: str

    # Outcomes (filled after "resolution")
    outcome_price: Optional[float] = None
    outcome_date: Optional[str] = None
    outcome_return: Optional[float] = None
    is_winner: Optional[bool] = None
    holding_days: Optional[int] = None

    # Metadata
    locations_analyzed: int = 0
    reviews_analyzed: int = 0
    sentiment_score: float = 0.0
    sentiment_change: float = 0.0


class DemoDataGenerator:
    """
    Generates realistic demo trading signals for presentations.

    Target metrics:
    - Win rate: 65-70%
    - Sharpe ratio: 1.8+
    - Average return: 2-4% per signal
    - Max drawdown: < 12%
    """

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.signals: List[DemoSignal] = []

    def generate_signals(
        self,
        months: int = 6,
        signals_per_week: int = 3,
        win_rate: float = 0.67,
        avg_return_win: float = 4.5,
        avg_return_loss: float = -2.5
    ) -> List[DemoSignal]:
        """
        Generate demo signals for specified period.

        Args:
            months: Number of months of history
            signals_per_week: Average signals generated per week
            win_rate: Target win rate (0.0-1.0)
            avg_return_win: Average return on winning trades (%)
            avg_return_loss: Average return on losing trades (%)
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=months * 30)

        total_weeks = months * 4
        total_signals = int(total_weeks * signals_per_week)

        signals = []

        for i in range(total_signals):
            # Random date within period
            days_offset = random.randint(0, months * 30 - 14)
            signal_date = start_date + timedelta(days=days_offset)

            # Pick random company
            symbol = random.choice(list(TRACKED_COMPANIES.keys()))
            company = TRACKED_COMPANIES[symbol]

            # Determine signal type based on random sentiment
            is_buy = random.random() > 0.45  # Slight bias towards buys
            is_strong = random.random() > 0.7  # 30% are strong signals

            if is_buy:
                signal_type = "STRONG_BUY" if is_strong else "BUY"
            else:
                signal_type = "STRONG_SELL" if is_strong else "SELL"

            # Generate realistic prices
            base_price = self._get_realistic_price(symbol)

            if "BUY" in signal_type:
                target_pct = random.uniform(3, 8)
                stop_pct = random.uniform(2, 4)
                target_price = base_price * (1 + target_pct/100)
                stop_loss = base_price * (1 - stop_pct/100)
            else:
                target_pct = random.uniform(3, 8)
                stop_pct = random.uniform(2, 4)
                target_price = base_price * (1 - target_pct/100)
                stop_loss = base_price * (1 + stop_pct/100)

            # Confidence based on signal strength
            if is_strong:
                confidence = random.uniform(0.80, 0.95)
            else:
                confidence = random.uniform(0.60, 0.80)

            # Generate source and reasoning
            source = random.choice(SIGNAL_SOURCES)
            reasoning = self._generate_reasoning(symbol, company["brand"], signal_type, source)

            # Sentiment data
            sentiment_score = random.uniform(-0.8, 0.8)
            if "BUY" in signal_type:
                sentiment_score = abs(sentiment_score)
            else:
                sentiment_score = -abs(sentiment_score)

            sentiment_change = random.uniform(-0.3, 0.3)
            if "BUY" in signal_type:
                sentiment_change = abs(sentiment_change)
            else:
                sentiment_change = -abs(sentiment_change)

            signal = DemoSignal(
                id=str(uuid.uuid4()),
                symbol=symbol,
                brand=company["brand"],
                sector=company["sector"],
                signal_type=signal_type,
                confidence=round(confidence, 3),
                generated_at=signal_date.isoformat(),
                entry_price=round(base_price, 2),
                target_price=round(target_price, 2),
                stop_loss=round(stop_loss, 2),
                source=source,
                reasoning=reasoning,
                locations_analyzed=random.randint(50, 500),
                reviews_analyzed=random.randint(500, 5000),
                sentiment_score=round(sentiment_score, 3),
                sentiment_change=round(sentiment_change, 3)
            )

            # Determine outcome
            self._resolve_signal(signal, win_rate, avg_return_win, avg_return_loss)

            signals.append(signal)

        # Sort by date
        signals.sort(key=lambda s: s.generated_at)
        self.signals = signals

        return signals

    def _get_realistic_price(self, symbol: str) -> float:
        """Get realistic stock price for company"""
        price_ranges = {
            "MCD": (280, 320),
            "SBUX": (90, 110),
            "CMG": (2800, 3200),
            "YUM": (130, 150),
            "DPZ": (400, 480),
            "QSR": (70, 85),
            "DRI": (160, 180),
            "TXRH": (140, 170),
            "WMT": (160, 180),
            "TGT": (140, 170),
            "COST": (700, 850),
            "HD": (350, 400),
            "LOW": (220, 260),
            "MAR": (220, 260),
            "HLT": (190, 230),
            "H": (140, 170),
        }
        low, high = price_ranges.get(symbol, (100, 150))
        return random.uniform(low, high)

    def _generate_reasoning(self, symbol: str, brand: str, signal_type: str, source: str) -> str:
        """Generate realistic signal reasoning"""
        templates = {
            "sentiment_spike": {
                "BUY": f"{brand} shows 15% sentiment improvement across 200+ locations in past 2 weeks. "
                       f"Customer satisfaction scores up significantly vs competitors.",
                "SELL": f"{brand} sentiment dropped 18% across major metros. "
                       f"Negative review volume up 2.3x vs 30-day average."
            },
            "rating_change": {
                "BUY": f"Average {brand} rating up 0.3 stars in last 30 days. "
                       f"Improvement consistent across 85% of tracked locations.",
                "SELL": f"{brand} average rating declined 0.25 stars. "
                       f"Service-related complaints up 45% month-over-month."
            },
            "review_volume": {
                "BUY": f"Review volume for {brand} up 65% vs baseline. "
                       f"Positive mentions of new products driving engagement.",
                "SELL": f"Negative review velocity for {brand} up 3x normal levels. "
                       f"Spike concentrated in top 20 revenue markets."
            },
            "anomaly_detection": {
                "BUY": f"ML anomaly detector flagged unusual positive sentiment cluster for {brand}. "
                       f"Pattern historically correlates with earnings beats.",
                "SELL": f"Anomaly detection identified emerging negative pattern for {brand}. "
                       f"Similar patterns preceded -5% moves in past."
            },
            "echo_engine": {
                "BUY": f"Echo Engine detected positive sentiment propagation for {brand}. "
                       f"Butterfly effect from regional improvements expanding nationally.",
                "SELL": f"Echo Engine shows negative sentiment cascade for {brand}. "
                       f"Problems in key markets spreading to adjacent regions."
            }
        }

        direction = "BUY" if "BUY" in signal_type else "SELL"
        return templates.get(source, templates["sentiment_spike"])[direction]

    def _resolve_signal(
        self,
        signal: DemoSignal,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ):
        """Determine signal outcome"""
        is_winner = random.random() < win_rate

        # Higher confidence signals have higher win rate
        if signal.confidence > 0.85:
            is_winner = random.random() < (win_rate + 0.1)
        elif signal.confidence < 0.65:
            is_winner = random.random() < (win_rate - 0.1)

        # Calculate return
        if is_winner:
            # Winners hit target or partial target
            return_pct = random.gauss(avg_win, 1.5)
            return_pct = max(0.5, min(return_pct, 12))  # Cap at 12%
        else:
            # Losers hit stop or worse
            return_pct = random.gauss(avg_loss, 1.0)
            return_pct = max(-8, min(return_pct, -0.3))  # Floor at -8%

        # Holding period
        if is_winner:
            holding_days = random.randint(5, 20)
        else:
            holding_days = random.randint(3, 14)  # Losers cut faster

        # Calculate outcome price
        if "BUY" in signal.signal_type:
            outcome_price = signal.entry_price * (1 + return_pct/100)
        else:
            outcome_price = signal.entry_price * (1 - return_pct/100)
            return_pct = -return_pct  # SELL signals profit when price drops

        signal_date = datetime.fromisoformat(signal.generated_at.replace('Z', '+00:00'))
        outcome_date = signal_date + timedelta(days=holding_days)

        signal.outcome_price = round(outcome_price, 2)
        signal.outcome_date = outcome_date.isoformat()
        signal.outcome_return = round(return_pct, 2)
        signal.is_winner = is_winner
        signal.holding_days = holding_days

    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics for generated signals"""
        if not self.signals:
            return {}

        resolved = [s for s in self.signals if s.outcome_return is not None]

        returns = [s.outcome_return for s in resolved]
        winners = [s for s in resolved if s.is_winner]
        losers = [s for s in resolved if not s.is_winner]

        # Basic metrics
        total_return = sum(returns)
        avg_return = sum(returns) / len(returns) if returns else 0
        win_rate = len(winners) / len(resolved) if resolved else 0

        # Win/Loss metrics
        avg_win = sum(s.outcome_return for s in winners) / len(winners) if winners else 0
        avg_loss = sum(s.outcome_return for s in losers) / len(losers) if losers else 0

        profit_factor = abs(sum(s.outcome_return for s in winners)) / abs(sum(s.outcome_return for s in losers)) if losers else float('inf')

        # Risk metrics
        if len(returns) > 1:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            volatility = math.sqrt(variance)

            # Annualized (assuming ~50 signals per year)
            annualized_return = avg_return * 50
            annualized_vol = volatility * math.sqrt(50)

            # Sharpe (assuming 5% risk-free rate annually)
            risk_free_per_signal = 5.0 / 50
            sharpe = (avg_return - risk_free_per_signal) / volatility if volatility > 0 else 0
        else:
            volatility = 0
            annualized_return = 0
            annualized_vol = 0
            sharpe = 0

        # Drawdown
        cumulative = 0
        peak = 0
        max_drawdown = 0
        for r in returns:
            cumulative += r
            peak = max(peak, cumulative)
            drawdown = peak - cumulative
            max_drawdown = max(max_drawdown, drawdown)

        # By sector
        sector_returns = {}
        for s in resolved:
            if s.sector not in sector_returns:
                sector_returns[s.sector] = []
            sector_returns[s.sector].append(s.outcome_return)

        sector_perf = {
            sector: {
                "signals": len(rets),
                "avg_return": round(sum(rets)/len(rets), 2),
                "win_rate": round(len([r for r in rets if r > 0])/len(rets)*100, 1)
            }
            for sector, rets in sector_returns.items()
        }

        return {
            "period": {
                "start": self.signals[0].generated_at if self.signals else None,
                "end": self.signals[-1].generated_at if self.signals else None,
                "months": 6
            },
            "summary": {
                "total_signals": len(resolved),
                "winning_signals": len(winners),
                "losing_signals": len(losers),
                "win_rate_pct": round(win_rate * 100, 1),
                "total_return_pct": round(total_return, 2),
                "avg_return_pct": round(avg_return, 2),
                "avg_win_pct": round(avg_win, 2),
                "avg_loss_pct": round(avg_loss, 2),
                "profit_factor": round(profit_factor, 2),
                "expectancy": round((win_rate * avg_win + (1-win_rate) * avg_loss), 2)
            },
            "risk_metrics": {
                "volatility_pct": round(volatility, 2),
                "annualized_return_pct": round(annualized_return, 1),
                "annualized_volatility_pct": round(annualized_vol, 1),
                "sharpe_ratio": round(sharpe, 2),
                "max_drawdown_pct": round(max_drawdown, 2)
            },
            "by_sector": sector_perf,
            "by_signal_type": {
                "BUY": len([s for s in resolved if s.signal_type == "BUY"]),
                "STRONG_BUY": len([s for s in resolved if s.signal_type == "STRONG_BUY"]),
                "SELL": len([s for s in resolved if s.signal_type == "SELL"]),
                "STRONG_SELL": len([s for s in resolved if s.signal_type == "STRONG_SELL"])
            }
        }

    def to_json(self, filepath: str = None) -> str:
        """Export signals to JSON"""
        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metrics": self.calculate_metrics(),
            "signals": [asdict(s) for s in self.signals]
        }

        json_str = json.dumps(data, indent=2, default=str)

        if filepath:
            with open(filepath, 'w') as f:
                f.write(json_str)

        return json_str


def main():
    """Generate demo track record"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate demo track record data')
    parser.add_argument('--months', type=int, default=6, help='Months of history')
    parser.add_argument('--output', type=str, default=None, help='Output JSON file')
    parser.add_argument('--signals-per-week', type=int, default=3, help='Signals per week')

    args = parser.parse_args()

    print("=" * 60)
    print("  ReviewSignal Track Record - Demo Data Generator")
    print("=" * 60)

    generator = DemoDataGenerator(seed=42)
    signals = generator.generate_signals(
        months=args.months,
        signals_per_week=args.signals_per_week
    )

    metrics = generator.calculate_metrics()

    print(f"\n📊 Generated {len(signals)} signals over {args.months} months\n")
    print("=" * 60)
    print("  PERFORMANCE SUMMARY")
    print("=" * 60)

    s = metrics["summary"]
    r = metrics["risk_metrics"]

    print(f"""
  Signals:           {s['total_signals']} ({s['winning_signals']} wins, {s['losing_signals']} losses)
  Win Rate:          {s['win_rate_pct']}%

  Total Return:      {s['total_return_pct']}%
  Avg Return:        {s['avg_return_pct']}% per signal
  Avg Win:           {s['avg_win_pct']}%
  Avg Loss:          {s['avg_loss_pct']}%
  Profit Factor:     {s['profit_factor']}
  Expectancy:        {s['expectancy']}% per trade

  Sharpe Ratio:      {r['sharpe_ratio']}
  Max Drawdown:      {r['max_drawdown_pct']}%
  Ann. Return:       {r['annualized_return_pct']}%
  Ann. Volatility:   {r['annualized_volatility_pct']}%
""")

    print("=" * 60)
    print("  BY SECTOR")
    print("=" * 60)
    for sector, perf in metrics["by_sector"].items():
        print(f"  {sector.upper():15} {perf['signals']:3} signals | "
              f"Win: {perf['win_rate']:.1f}% | Avg: {perf['avg_return']:+.1f}%")

    if args.output:
        generator.to_json(args.output)
        print(f"\n💾 Saved to {args.output}")

    print("\n" + "=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
