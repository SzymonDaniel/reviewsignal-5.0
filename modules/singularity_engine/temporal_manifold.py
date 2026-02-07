# ═══════════════════════════════════════════════════════════════════════════════
# SINGULARITY ENGINE - Temporal Manifold
# Fold time to discover hidden patterns across different temporal dimensions
# ═══════════════════════════════════════════════════════════════════════════════

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import numpy as np
from scipy import stats
import structlog

from .models import (
    SingularityConfig,
    ReviewData,
    EventData,
    TimeFold,
    TemporalPattern,
    TemporalFoldResult,
)
from .utils import (
    generate_id,
    normalize_sentiment,
    safe_mean,
    safe_std,
    calculate_z_score,
    is_anomaly,
    calculate_trend,
    get_day_of_week_name,
    get_quarter,
    get_season,
    get_lunar_phase,
    days_from_event,
    find_nearest_event,
)

logger = structlog.get_logger(__name__)


class TemporalManifold:
    """
    Temporal Manifold - Fold Time to Reveal Hidden Patterns

    Concept: Instead of viewing time linearly, we "fold" it along different
    dimensions to reveal patterns invisible in chronological view.

    Fold Types:
    - WEEKLY: All Mondays together, all Tuesdays together, etc.
    - MONTHLY: All 1st of month together, all 15th together, etc.
    - SEASONAL: Q1 vs Q2 vs Q3 vs Q4
    - LUNAR: Sentiment patterns aligned to moon phases
    - EVENT_ALIGNED: Days relative to known events (earnings, launches)
    - COMPETITIVE: Days relative to competitor actions

    Example:
        If Starbucks always has lower sentiment on Mondays, but competitors
        don't, this reveals an operational pattern specific to Starbucks.
    """

    def __init__(
        self,
        reviews: List[ReviewData],
        events: Optional[List[EventData]] = None,
        config: Optional[SingularityConfig] = None
    ):
        self.reviews = reviews
        self.events = events or []
        self.config = config or SingularityConfig()

        # Pre-compute event dates by chain
        self._event_dates_by_chain = self._index_events()

        logger.info(
            "temporal_manifold_initialized",
            review_count=len(reviews),
            event_count=len(self.events)
        )

    def _index_events(self) -> Dict[str, List[datetime]]:
        """Index events by chain for fast lookup"""
        index = defaultdict(list)
        for event in self.events:
            if event.event_date:
                key = event.chain_id.lower() if event.chain_id else "_global"
                index[key].append(event.event_date)
        return dict(index)

    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN ANALYSIS METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def analyze_all_folds(
        self,
        reviews: Optional[List[ReviewData]] = None
    ) -> List[TemporalFoldResult]:
        """
        Analyze all temporal folds

        Args:
            reviews: Optional subset of reviews (uses all if not provided)

        Returns:
            List of TemporalFoldResult for each fold type
        """
        reviews = reviews or self.reviews
        results = []

        # Always analyze these folds
        for fold_type in [TimeFold.WEEKLY, TimeFold.MONTHLY, TimeFold.SEASONAL]:
            result = self.analyze_fold(reviews, fold_type)
            results.append(result)

        # Lunar fold (optional but interesting)
        lunar_result = self.analyze_fold(reviews, TimeFold.LUNAR)
        results.append(lunar_result)

        # Event-aligned fold (if events available)
        if self.events:
            event_result = self.analyze_fold(reviews, TimeFold.EVENT_ALIGNED)
            results.append(event_result)

        logger.info(
            "all_folds_analyzed",
            fold_count=len(results),
            total_anomalies=sum(r.anomaly_count for r in results)
        )

        return results

    def analyze_fold(
        self,
        reviews: List[ReviewData],
        fold_type: TimeFold
    ) -> TemporalFoldResult:
        """
        Analyze a single temporal fold

        Args:
            reviews: Reviews to analyze
            fold_type: Type of temporal folding to apply

        Returns:
            TemporalFoldResult with patterns and anomalies
        """
        # Filter reviews with valid timestamps
        dated_reviews = [r for r in reviews if r.review_time]

        if len(dated_reviews) < self.config.temporal_min_samples:
            return TemporalFoldResult(
                fold_type=fold_type,
                patterns=[],
                anomaly_count=0,
                strongest_pattern=None,
                insight_summary=f"Insufficient data for {fold_type.value} analysis"
            )

        # Fold the data
        folded = self._fold_reviews(dated_reviews, fold_type)

        # Calculate baseline statistics
        all_sentiments = [
            self._get_sentiment(r) for r in dated_reviews
        ]
        baseline_mean = safe_mean(all_sentiments)
        baseline_std = safe_std(all_sentiments)

        # Analyze each fold bucket
        patterns = []
        for fold_key, bucket_reviews in folded.items():
            if len(bucket_reviews) < 3:
                continue

            pattern = self._analyze_bucket(
                fold_type=fold_type,
                fold_key=fold_key,
                reviews=bucket_reviews,
                baseline_mean=baseline_mean,
                baseline_std=baseline_std
            )
            patterns.append(pattern)

        # Find anomalies
        anomalies = [p for p in patterns if p.is_anomaly]

        # Find strongest pattern
        strongest = None
        if patterns:
            strongest = max(patterns, key=lambda p: abs(p.z_score))

        # Generate insight summary
        insight = self._generate_fold_insight(fold_type, patterns, anomalies)

        return TemporalFoldResult(
            fold_type=fold_type,
            patterns=patterns,
            anomaly_count=len(anomalies),
            strongest_pattern=strongest,
            insight_summary=insight
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # FOLDING METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def _fold_reviews(
        self,
        reviews: List[ReviewData],
        fold_type: TimeFold
    ) -> Dict[str, List[ReviewData]]:
        """
        Fold reviews by the specified temporal dimension

        Returns:
            Dict mapping fold_key to list of reviews
        """
        folded = defaultdict(list)

        for review in reviews:
            fold_key = self._get_fold_key(review, fold_type)
            if fold_key:
                folded[fold_key].append(review)

        return dict(folded)

    def _get_fold_key(
        self,
        review: ReviewData,
        fold_type: TimeFold
    ) -> Optional[str]:
        """Get the fold key for a review based on fold type"""
        if not review.review_time:
            return None

        dt = review.review_time

        if fold_type == TimeFold.WEEKLY:
            return get_day_of_week_name(dt)

        elif fold_type == TimeFold.MONTHLY:
            day = dt.day
            if day <= 7:
                return "Week1"
            elif day <= 14:
                return "Week2"
            elif day <= 21:
                return "Week3"
            else:
                return "Week4"

        elif fold_type == TimeFold.SEASONAL:
            return get_quarter(dt)

        elif fold_type == TimeFold.LUNAR:
            return get_lunar_phase(dt)

        elif fold_type == TimeFold.EVENT_ALIGNED:
            return self._get_event_aligned_key(review)

        elif fold_type == TimeFold.COMPETITIVE:
            return self._get_competitive_key(review)

        return None

    def _get_event_aligned_key(self, review: ReviewData) -> Optional[str]:
        """Get fold key relative to nearest event"""
        if not review.review_time:
            return None

        # Get events for this chain
        chain_key = review.chain_id.lower() if review.chain_id else "_global"
        event_dates = self._event_dates_by_chain.get(chain_key, [])

        # Also include global events
        global_events = self._event_dates_by_chain.get("_global", [])
        all_events = event_dates + global_events

        if not all_events:
            return None

        result = find_nearest_event(review.review_time, all_events, max_distance_days=30)
        if result:
            _, days = result
            # Bucket into ranges: -30 to -15, -14 to -8, -7 to -1, 0, 1 to 7, 8 to 14, 15 to 30
            if days < -14:
                return "pre_event_far"
            elif days < -7:
                return "pre_event_medium"
            elif days < 0:
                return "pre_event_close"
            elif days == 0:
                return "event_day"
            elif days <= 7:
                return "post_event_close"
            elif days <= 14:
                return "post_event_medium"
            else:
                return "post_event_far"

        return None

    def _get_competitive_key(self, review: ReviewData) -> Optional[str]:
        """Get fold key relative to competitor events"""
        # For competitive analysis, we need competitor event data
        # This is a placeholder - would need competitor event tracking
        return None

    # ═══════════════════════════════════════════════════════════════════════════
    # ANALYSIS METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def _analyze_bucket(
        self,
        fold_type: TimeFold,
        fold_key: str,
        reviews: List[ReviewData],
        baseline_mean: float,
        baseline_std: float
    ) -> TemporalPattern:
        """Analyze a single bucket of folded reviews"""
        # Get sentiments
        sentiments = [self._get_sentiment(r) for r in reviews]

        # Calculate statistics
        bucket_mean = safe_mean(sentiments)
        bucket_std = safe_std(sentiments)
        deviation = bucket_mean - baseline_mean

        # Calculate z-score
        z_score = calculate_z_score(bucket_mean, baseline_mean, baseline_std)

        # Determine if anomaly
        is_anomalous = is_anomaly(z_score, self.config.temporal_anomaly_threshold)

        # Calculate trend if enough data
        trend_direction = "stable"
        if len(reviews) >= 5:
            # Sort by time and check trend
            sorted_reviews = sorted(reviews, key=lambda r: r.review_time or datetime.min)
            sorted_sentiments = [self._get_sentiment(r) for r in sorted_reviews]
            trend_direction, _, _ = calculate_trend(sorted_sentiments)

        # Find peak and trough periods
        peaks, troughs = self._find_peaks_troughs(reviews)

        return TemporalPattern(
            pattern_id=generate_id("tmp"),
            fold_type=fold_type,
            fold_key=fold_key,
            mean_sentiment=bucket_mean,
            std_sentiment=bucket_std,
            sample_count=len(reviews),
            baseline_mean=baseline_mean,
            baseline_std=baseline_std,
            deviation_from_baseline=deviation,
            z_score=z_score,
            is_anomaly=is_anomalous,
            trend_direction=trend_direction,
            peak_periods=peaks,
            trough_periods=troughs
        )

    def _find_peaks_troughs(
        self,
        reviews: List[ReviewData]
    ) -> Tuple[List[str], List[str]]:
        """Find peak and trough time periods within a bucket"""
        if len(reviews) < 10:
            return [], []

        # Group by date
        by_date = defaultdict(list)
        for r in reviews:
            if r.review_time:
                date_key = r.review_time.strftime("%Y-%m-%d")
                by_date[date_key].append(self._get_sentiment(r))

        if len(by_date) < 3:
            return [], []

        # Calculate daily means
        daily_means = {k: safe_mean(v) for k, v in by_date.items()}

        # Find overall mean
        overall_mean = safe_mean(list(daily_means.values()))
        overall_std = safe_std(list(daily_means.values()))

        if overall_std == 0:
            return [], []

        # Find peaks (1+ std above mean) and troughs (1+ std below)
        peaks = [
            k for k, v in daily_means.items()
            if v > overall_mean + overall_std
        ]
        troughs = [
            k for k, v in daily_means.items()
            if v < overall_mean - overall_std
        ]

        return sorted(peaks)[:5], sorted(troughs)[:5]

    def _get_sentiment(self, review: ReviewData) -> float:
        """Get sentiment score from review (normalize rating if needed)"""
        if review.sentiment_score is not None:
            return review.sentiment_score
        if review.rating:
            return normalize_sentiment(review.rating)
        return 0.0

    # ═══════════════════════════════════════════════════════════════════════════
    # INSIGHT GENERATION
    # ═══════════════════════════════════════════════════════════════════════════

    def _generate_fold_insight(
        self,
        fold_type: TimeFold,
        patterns: List[TemporalPattern],
        anomalies: List[TemporalPattern]
    ) -> str:
        """Generate human-readable insight for a fold analysis"""
        if not patterns:
            return f"No significant patterns found in {fold_type.value} analysis."

        insights = []

        # Report anomalies
        if anomalies:
            for anomaly in anomalies[:3]:  # Top 3
                direction = "higher" if anomaly.deviation_from_baseline > 0 else "lower"
                insights.append(
                    f"{anomaly.fold_key} shows {abs(anomaly.deviation_from_baseline):.2f} "
                    f"{direction} sentiment than average (z={anomaly.z_score:.2f})"
                )

        # Report strongest pattern if not already in anomalies
        strongest = max(patterns, key=lambda p: abs(p.z_score))
        if strongest not in anomalies:
            if abs(strongest.z_score) > 1.0:
                direction = "higher" if strongest.deviation_from_baseline > 0 else "lower"
                insights.append(
                    f"Notable: {strongest.fold_key} tends to have {direction} sentiment"
                )

        # Report trends
        trending_up = [p for p in patterns if p.trend_direction == "up"]
        trending_down = [p for p in patterns if p.trend_direction == "down"]

        if trending_up:
            insights.append(
                f"Improving trend in: {', '.join(p.fold_key for p in trending_up[:2])}"
            )
        if trending_down:
            insights.append(
                f"Declining trend in: {', '.join(p.fold_key for p in trending_down[:2])}"
            )

        if not insights:
            return f"Stable patterns across {fold_type.value} dimension."

        return "; ".join(insights)

    # ═══════════════════════════════════════════════════════════════════════════
    # SPECIALIZED ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════

    def find_best_worst_periods(
        self,
        reviews: Optional[List[ReviewData]] = None,
        fold_type: TimeFold = TimeFold.WEEKLY
    ) -> Dict[str, any]:
        """
        Find the best and worst performing time periods

        Returns:
            Dict with 'best' and 'worst' periods and their statistics
        """
        reviews = reviews or self.reviews
        result = self.analyze_fold(reviews, fold_type)

        if not result.patterns:
            return {'best': None, 'worst': None}

        sorted_patterns = sorted(
            result.patterns,
            key=lambda p: p.mean_sentiment,
            reverse=True
        )

        return {
            'best': sorted_patterns[0] if sorted_patterns else None,
            'worst': sorted_patterns[-1] if sorted_patterns else None,
            'spread': (
                sorted_patterns[0].mean_sentiment - sorted_patterns[-1].mean_sentiment
                if len(sorted_patterns) >= 2 else 0
            )
        }

    def detect_seasonality(
        self,
        reviews: Optional[List[ReviewData]] = None
    ) -> Dict[str, any]:
        """
        Detect seasonal patterns in sentiment

        Returns:
            Dict with seasonality analysis
        """
        reviews = reviews or self.reviews
        result = self.analyze_fold(reviews, TimeFold.SEASONAL)

        if not result.patterns or len(result.patterns) < 2:
            return {'has_seasonality': False}

        # Check if there's significant variance between quarters
        sentiments = [p.mean_sentiment for p in result.patterns]
        variance = np.var(sentiments)

        # Perform ANOVA if we have all quarters
        if len(result.patterns) == 4:
            groups = []
            folded = self._fold_reviews([r for r in reviews if r.review_time], TimeFold.SEASONAL)
            for key in ['Q1', 'Q2', 'Q3', 'Q4']:
                if key in folded:
                    groups.append([self._get_sentiment(r) for r in folded[key]])

            if len(groups) == 4 and all(len(g) >= 3 for g in groups):
                f_stat, p_value = stats.f_oneway(*groups)
                has_seasonality = p_value < 0.05
            else:
                has_seasonality = variance > 0.01
        else:
            has_seasonality = variance > 0.01

        # Find peak and trough quarters
        sorted_patterns = sorted(result.patterns, key=lambda p: p.mean_sentiment, reverse=True)

        return {
            'has_seasonality': has_seasonality,
            'variance': float(variance),
            'peak_quarter': sorted_patterns[0].fold_key if sorted_patterns else None,
            'trough_quarter': sorted_patterns[-1].fold_key if sorted_patterns else None,
            'patterns': result.patterns
        }

    def analyze_event_impact(
        self,
        event_type: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Analyze how events impact sentiment over time

        Args:
            event_type: Filter to specific event type (e.g., "earnings")

        Returns:
            Dict with event impact analysis
        """
        if not self.events:
            return {'has_events': False}

        # Filter events if needed
        events = self.events
        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if not events:
            return {'has_events': False, 'event_type': event_type}

        # Analyze event-aligned patterns
        result = self.analyze_fold(self.reviews, TimeFold.EVENT_ALIGNED)

        # Calculate pre vs post event sentiment
        pre_patterns = [p for p in result.patterns if 'pre_event' in p.fold_key]
        post_patterns = [p for p in result.patterns if 'post_event' in p.fold_key]
        event_day = [p for p in result.patterns if p.fold_key == 'event_day']

        pre_mean = safe_mean([p.mean_sentiment for p in pre_patterns]) if pre_patterns else None
        post_mean = safe_mean([p.mean_sentiment for p in post_patterns]) if post_patterns else None
        event_mean = event_day[0].mean_sentiment if event_day else None

        return {
            'has_events': True,
            'event_count': len(events),
            'pre_event_sentiment': pre_mean,
            'event_day_sentiment': event_mean,
            'post_event_sentiment': post_mean,
            'impact': (post_mean - pre_mean) if pre_mean and post_mean else None,
            'patterns': result.patterns
        }

    def compare_chains_temporal(
        self,
        chain_a: str,
        chain_b: str,
        fold_type: TimeFold = TimeFold.WEEKLY
    ) -> Dict[str, any]:
        """
        Compare temporal patterns between two chains

        Args:
            chain_a: First chain name
            chain_b: Second chain name
            fold_type: Temporal fold to compare

        Returns:
            Dict with comparison results
        """
        # Filter reviews by chain
        reviews_a = [r for r in self.reviews if r.chain_id and chain_a.lower() in r.chain_id.lower()]
        reviews_b = [r for r in self.reviews if r.chain_id and chain_b.lower() in r.chain_id.lower()]

        if len(reviews_a) < self.config.temporal_min_samples:
            return {'error': f'Insufficient data for {chain_a}'}
        if len(reviews_b) < self.config.temporal_min_samples:
            return {'error': f'Insufficient data for {chain_b}'}

        # Analyze each chain
        result_a = self.analyze_fold(reviews_a, fold_type)
        result_b = self.analyze_fold(reviews_b, fold_type)

        # Compare patterns
        patterns_a = {p.fold_key: p for p in result_a.patterns}
        patterns_b = {p.fold_key: p for p in result_b.patterns}

        common_keys = set(patterns_a.keys()) & set(patterns_b.keys())

        comparisons = []
        for key in common_keys:
            pa = patterns_a[key]
            pb = patterns_b[key]
            diff = pa.mean_sentiment - pb.mean_sentiment
            comparisons.append({
                'period': key,
                f'{chain_a}_sentiment': pa.mean_sentiment,
                f'{chain_b}_sentiment': pb.mean_sentiment,
                'difference': diff,
                'favors': chain_a if diff > 0 else chain_b
            })

        # Calculate correlation
        if len(common_keys) >= 3:
            vals_a = [patterns_a[k].mean_sentiment for k in common_keys]
            vals_b = [patterns_b[k].mean_sentiment for k in common_keys]
            corr, p_value = stats.pearsonr(vals_a, vals_b)
        else:
            corr, p_value = None, None

        return {
            'chain_a': chain_a,
            'chain_b': chain_b,
            'fold_type': fold_type.value,
            'comparisons': comparisons,
            'correlation': corr,
            'correlation_p_value': p_value,
            'patterns_similar': corr and corr > 0.7 and p_value < 0.05
        }
