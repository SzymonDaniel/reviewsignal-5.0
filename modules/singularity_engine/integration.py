# ═══════════════════════════════════════════════════════════════════════════════
# SINGULARITY ENGINE - Echo Engine Integration
# Connect Singularity Engine with the quantum-inspired Echo Engine
# ═══════════════════════════════════════════════════════════════════════════════

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from collections import defaultdict
import numpy as np
import structlog

from .models import (
    SingularityConfig,
    ReviewData,
    SingularityInsight,
    ModuleContribution,
    InsightConfidence,
    TradingAction,
)
from .utils import (
    generate_id,
    normalize_sentiment,
    safe_mean,
    calculate_trend,
    combine_confidences,
)

logger = structlog.get_logger(__name__)


class EchoSingularityIntegration:
    """
    Integration layer between Singularity Engine and Echo Engine

    The Echo Engine provides:
    - Butterfly coefficient (small changes → big effects)
    - System stability assessment
    - Sentiment propagation predictions
    - Cross-location correlation

    This integration layer:
    - Feeds Singularity insights to Echo for propagation modeling
    - Takes Echo outputs and incorporates into trading signals
    - Combines both engines for comprehensive analysis
    """

    def __init__(
        self,
        echo_engine: Any,
        config: Optional[SingularityConfig] = None
    ):
        """
        Initialize Echo Integration

        Args:
            echo_engine: Instance of Echo Engine
            config: Singularity configuration
        """
        self.echo = echo_engine
        self.config = config or SingularityConfig()

        logger.info("echo_integration_initialized")

    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN INTEGRATION METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def analyze_with_echo(
        self,
        reviews: List[ReviewData]
    ) -> Dict[str, Any]:
        """
        Run Echo Engine analysis on reviews

        Args:
            reviews: Reviews to analyze

        Returns:
            Dict with Echo Engine results
        """
        if not self.echo:
            return {'error': 'Echo Engine not available'}

        try:
            # Prepare data for Echo Engine
            echo_data = self._prepare_echo_data(reviews)

            # Run Echo analysis
            result = {}

            # 1. Calculate butterfly coefficient
            butterfly = self._calculate_butterfly_coefficient(echo_data)
            result['butterfly_coefficient'] = butterfly

            # 2. Assess system stability
            stability = self._assess_system_stability(echo_data)
            result['system_stability'] = stability

            # 3. Predict sentiment propagation
            propagation = self._predict_propagation(echo_data)
            result['propagation_prediction'] = propagation

            # 4. Calculate cross-location correlations
            correlations = self._calculate_correlations(echo_data)
            result['cross_correlations'] = correlations

            # 5. Generate Echo insights
            result['echo_insights'] = self._generate_echo_insights(
                butterfly, stability, propagation, correlations
            )

            logger.info(
                "echo_analysis_complete",
                butterfly=butterfly,
                stability=stability
            )

            return result

        except Exception as e:
            logger.error("echo_analysis_failed", error=str(e))
            return {'error': str(e)}

    def enhance_singularity_insight(
        self,
        insight: SingularityInsight,
        echo_results: Dict[str, Any]
    ) -> SingularityInsight:
        """
        Enhance a Singularity insight with Echo Engine data

        Args:
            insight: Original Singularity insight
            echo_results: Results from Echo analysis

        Returns:
            Enhanced insight
        """
        if 'error' in echo_results:
            return insight

        # Add Echo data to insight
        insight.echo_butterfly_coefficient = echo_results.get('butterfly_coefficient')
        insight.echo_system_stability = echo_results.get('system_stability')

        # Adjust confidence based on Echo validation
        if insight.echo_butterfly_coefficient:
            # High butterfly coefficient means small changes can have big effects
            # This increases uncertainty in stable situations
            if insight.echo_butterfly_coefficient > 0.7:
                insight.confidence_score *= 0.9  # Reduce confidence slightly

        # Add Echo insights to warning signals
        echo_insights = echo_results.get('echo_insights', [])
        for echo_insight in echo_insights:
            if echo_insight.get('type') == 'warning':
                insight.warning_signals.append(echo_insight.get('message', ''))

        return insight

    # ═══════════════════════════════════════════════════════════════════════════
    # ECHO CALCULATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def _prepare_echo_data(
        self,
        reviews: List[ReviewData]
    ) -> Dict[str, Any]:
        """Prepare review data for Echo Engine format"""
        # Group by location
        by_location = defaultdict(list)
        for r in reviews:
            if r.location_id:
                by_location[r.location_id].append(r)

        # Calculate per-location metrics
        location_metrics = {}
        for loc_id, loc_reviews in by_location.items():
            sentiments = [
                r.sentiment_score if r.sentiment_score is not None
                else normalize_sentiment(r.rating) if r.rating else 0
                for r in loc_reviews
            ]

            # Get time series if available
            dated_reviews = sorted(
                [(r.review_time, s) for r, s in zip(loc_reviews, sentiments) if r.review_time],
                key=lambda x: x[0]
            )

            location_metrics[loc_id] = {
                'mean_sentiment': safe_mean(sentiments),
                'review_count': len(loc_reviews),
                'time_series': dated_reviews,
                'chain_id': loc_reviews[0].chain_id if loc_reviews else None,
                'city': loc_reviews[0].city if loc_reviews else None
            }

        # Group by chain
        by_chain = defaultdict(list)
        for r in reviews:
            if r.chain_id:
                by_chain[r.chain_id].append(r)

        chain_metrics = {}
        for chain, chain_reviews in by_chain.items():
            sentiments = [
                r.sentiment_score if r.sentiment_score is not None
                else normalize_sentiment(r.rating) if r.rating else 0
                for r in chain_reviews
            ]
            chain_metrics[chain] = {
                'mean_sentiment': safe_mean(sentiments),
                'review_count': len(chain_reviews),
                'location_count': len(set(r.location_id for r in chain_reviews if r.location_id))
            }

        return {
            'location_metrics': location_metrics,
            'chain_metrics': chain_metrics,
            'total_reviews': len(reviews)
        }

    def _calculate_butterfly_coefficient(
        self,
        echo_data: Dict[str, Any]
    ) -> float:
        """
        Calculate butterfly coefficient (sensitivity to small changes)

        The butterfly effect in our context means:
        - How much does a single location's sentiment change affect the whole chain?
        - High coefficient = system is sensitive to small perturbations

        Returns:
            Float between 0 and 1 (higher = more sensitive)
        """
        location_metrics = echo_data.get('location_metrics', {})

        if len(location_metrics) < 3:
            return 0.5  # Default

        # Calculate variance in location sentiments
        sentiments = [m['mean_sentiment'] for m in location_metrics.values()]
        variance = np.var(sentiments)

        # Calculate review count distribution
        counts = [m['review_count'] for m in location_metrics.values()]
        count_variance = np.var(counts) / (np.mean(counts) ** 2 + 0.001)  # Normalized

        # Butterfly coefficient: high variance + skewed distribution = sensitive system
        butterfly = min(1.0, (variance + count_variance) / 2)

        return float(butterfly)

    def _assess_system_stability(
        self,
        echo_data: Dict[str, Any]
    ) -> str:
        """
        Assess overall system stability

        Returns:
            "stable", "unstable", or "critical"
        """
        location_metrics = echo_data.get('location_metrics', {})
        chain_metrics = echo_data.get('chain_metrics', {})

        if not location_metrics:
            return "unknown"

        # Check for stability indicators
        stability_score = 0.5  # Start neutral

        # Factor 1: Sentiment variance across locations
        sentiments = [m['mean_sentiment'] for m in location_metrics.values()]
        sentiment_std = np.std(sentiments) if sentiments else 0

        if sentiment_std < 0.2:
            stability_score += 0.2  # Low variance = stable
        elif sentiment_std > 0.5:
            stability_score -= 0.2  # High variance = unstable

        # Factor 2: Trend direction across chains
        trends = []
        for chain, metrics in chain_metrics.items():
            if 'time_series' in metrics:
                values = [v for _, v in metrics.get('time_series', [])]
                if len(values) >= 3:
                    trend, _, _ = calculate_trend(values)
                    trends.append(trend)

        if trends:
            down_trends = sum(1 for t in trends if t == 'down')
            if down_trends > len(trends) * 0.5:
                stability_score -= 0.2

        # Factor 3: Review volume consistency
        counts = [m['review_count'] for m in location_metrics.values()]
        count_cv = np.std(counts) / (np.mean(counts) + 0.001)  # Coefficient of variation

        if count_cv > 1.5:
            stability_score -= 0.1

        # Determine stability level
        if stability_score >= 0.6:
            return "stable"
        elif stability_score >= 0.3:
            return "unstable"
        else:
            return "critical"

    def _predict_propagation(
        self,
        echo_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Predict how sentiment changes might propagate

        Returns:
            Dict with propagation predictions
        """
        location_metrics = echo_data.get('location_metrics', {})
        chain_metrics = echo_data.get('chain_metrics', {})

        predictions = []

        # For each chain, predict if negative sentiment will spread
        for chain, metrics in chain_metrics.items():
            mean_sentiment = metrics['mean_sentiment']
            location_count = metrics['location_count']

            if mean_sentiment < -0.2:
                # Negative sentiment - predict propagation
                propagation_risk = min(1.0, abs(mean_sentiment) * (location_count / 10))
                predictions.append({
                    'chain': chain,
                    'current_sentiment': mean_sentiment,
                    'propagation_risk': propagation_risk,
                    'predicted_direction': 'negative',
                    'confidence': 0.6 if propagation_risk > 0.5 else 0.4
                })

            elif mean_sentiment > 0.3:
                # Positive sentiment - predict spread
                propagation_chance = min(1.0, mean_sentiment * (location_count / 10))
                predictions.append({
                    'chain': chain,
                    'current_sentiment': mean_sentiment,
                    'propagation_chance': propagation_chance,
                    'predicted_direction': 'positive',
                    'confidence': 0.6 if propagation_chance > 0.5 else 0.4
                })

        return {
            'predictions': predictions,
            'overall_direction': self._determine_overall_direction(predictions)
        }

    def _determine_overall_direction(
        self,
        predictions: List[Dict]
    ) -> str:
        """Determine overall market direction from predictions"""
        if not predictions:
            return 'neutral'

        positive = sum(1 for p in predictions if p.get('predicted_direction') == 'positive')
        negative = sum(1 for p in predictions if p.get('predicted_direction') == 'negative')

        if positive > negative * 1.5:
            return 'bullish'
        elif negative > positive * 1.5:
            return 'bearish'
        else:
            return 'neutral'

    def _calculate_correlations(
        self,
        echo_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate cross-location sentiment correlations

        Returns:
            Dict with correlation matrix and key findings
        """
        location_metrics = echo_data.get('location_metrics', {})

        if len(location_metrics) < 3:
            return {'correlations': [], 'key_finding': 'Insufficient locations'}

        # Build time series matrix
        # For simplicity, use mean sentiment per location
        locations = list(location_metrics.keys())
        sentiments = [location_metrics[loc]['mean_sentiment'] for loc in locations]

        # Find highly correlated locations (by chain/city)
        by_chain = defaultdict(list)
        by_city = defaultdict(list)

        for loc_id, metrics in location_metrics.items():
            if metrics.get('chain_id'):
                by_chain[metrics['chain_id']].append(loc_id)
            if metrics.get('city'):
                by_city[metrics['city']].append(loc_id)

        correlations = []

        # Chain correlations
        for chain, locs in by_chain.items():
            if len(locs) >= 2:
                chain_sentiments = [location_metrics[loc]['mean_sentiment'] for loc in locs]
                chain_corr = 1 - np.std(chain_sentiments)  # Higher consistency = higher "correlation"
                correlations.append({
                    'type': 'chain',
                    'entity': chain,
                    'consistency': float(chain_corr),
                    'location_count': len(locs)
                })

        # City correlations
        for city, locs in by_city.items():
            if len(locs) >= 2:
                city_sentiments = [location_metrics[loc]['mean_sentiment'] for loc in locs]
                city_corr = 1 - np.std(city_sentiments)
                correlations.append({
                    'type': 'city',
                    'entity': city,
                    'consistency': float(city_corr),
                    'location_count': len(locs)
                })

        # Sort by consistency
        correlations.sort(key=lambda x: x['consistency'], reverse=True)

        # Generate key finding
        if correlations:
            top = correlations[0]
            key_finding = f"Highest consistency: {top['entity']} ({top['type']}) with {top['consistency']:.2f}"
        else:
            key_finding = "No significant correlations found"

        return {
            'correlations': correlations[:10],
            'key_finding': key_finding
        }

    def _generate_echo_insights(
        self,
        butterfly: float,
        stability: str,
        propagation: Dict[str, Any],
        correlations: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate actionable insights from Echo analysis"""
        insights = []

        # Butterfly insight
        if butterfly > 0.7:
            insights.append({
                'type': 'warning',
                'source': 'butterfly_coefficient',
                'message': f'High sensitivity detected (β={butterfly:.2f}). Small changes may cascade.',
                'action': 'Monitor closely for sudden shifts'
            })
        elif butterfly < 0.3:
            insights.append({
                'type': 'info',
                'source': 'butterfly_coefficient',
                'message': f'System is resilient (β={butterfly:.2f}). Changes propagate slowly.',
                'action': 'Safe for gradual interventions'
            })

        # Stability insight
        if stability == 'critical':
            insights.append({
                'type': 'warning',
                'source': 'system_stability',
                'message': 'System in critical state. Major disruption possible.',
                'action': 'Consider defensive positions'
            })
        elif stability == 'unstable':
            insights.append({
                'type': 'warning',
                'source': 'system_stability',
                'message': 'System unstable. Increased volatility expected.',
                'action': 'Increase monitoring frequency'
            })

        # Propagation insight
        direction = propagation.get('overall_direction', 'neutral')
        if direction == 'bearish':
            insights.append({
                'type': 'signal',
                'source': 'propagation_prediction',
                'message': 'Negative sentiment likely to spread across network.',
                'action': 'Consider reducing exposure'
            })
        elif direction == 'bullish':
            insights.append({
                'type': 'signal',
                'source': 'propagation_prediction',
                'message': 'Positive sentiment building across network.',
                'action': 'Potential entry opportunity'
            })

        return insights

    # ═══════════════════════════════════════════════════════════════════════════
    # COMBINED ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════

    def get_trading_signal(
        self,
        echo_results: Dict[str, Any],
        singularity_confidence: float
    ) -> Tuple[TradingAction, float]:
        """
        Generate combined trading signal from Echo + Singularity

        Args:
            echo_results: Results from Echo analysis
            singularity_confidence: Confidence from Singularity analysis

        Returns:
            Tuple of (TradingAction, confidence)
        """
        if 'error' in echo_results:
            return TradingAction.HOLD, 0.5

        # Get Echo signals
        stability = echo_results.get('system_stability', 'unknown')
        butterfly = echo_results.get('butterfly_coefficient', 0.5)
        direction = echo_results.get('propagation_prediction', {}).get('overall_direction', 'neutral')

        # Base signal from direction
        if direction == 'bullish':
            base_signal = TradingAction.BUY
            base_confidence = 0.6
        elif direction == 'bearish':
            base_signal = TradingAction.SELL
            base_confidence = 0.6
        else:
            base_signal = TradingAction.HOLD
            base_confidence = 0.5

        # Adjust by stability
        if stability == 'critical':
            # In critical state, lean defensive
            if base_signal == TradingAction.BUY:
                base_signal = TradingAction.HOLD
            elif base_signal == TradingAction.SELL:
                base_signal = TradingAction.STRONG_SELL
            base_confidence *= 0.8

        elif stability == 'stable':
            # In stable state, increase confidence
            base_confidence *= 1.1
            if base_signal == TradingAction.BUY and base_confidence > 0.7:
                base_signal = TradingAction.STRONG_BUY
            elif base_signal == TradingAction.SELL and base_confidence > 0.7:
                base_signal = TradingAction.STRONG_SELL

        # Adjust by butterfly coefficient
        if butterfly > 0.7:
            # High uncertainty - reduce confidence
            base_confidence *= 0.9

        # Combine with Singularity confidence
        final_confidence = combine_confidences(
            [base_confidence, singularity_confidence],
            method="harmonic"
        )

        return base_signal, min(1.0, final_confidence)
