# ═══════════════════════════════════════════════════════════════════════════════
# SINGULARITY ENGINE - Topological Analyzer
# Find "holes", clusters, and structural patterns in data using TDA concepts
# ═══════════════════════════════════════════════════════════════════════════════

from datetime import datetime
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import numpy as np
from scipy.spatial.distance import pdist, squareform
from scipy.cluster.hierarchy import linkage, fcluster
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
import structlog

from .models import (
    SingularityConfig,
    ReviewData,
    TopologicalInsight,
    TopologyFeature,
    PersistencePair,
)
from .utils import (
    generate_id,
    normalize_sentiment,
    safe_mean,
    safe_std,
    normalize_to_unit,
)

logger = structlog.get_logger(__name__)


class TopologicalAnalyzer:
    """
    Topological Data Analysis (TDA) for Review Data

    Concepts from Algebraic Topology applied to business data:

    1. H0 (Connected Components / Clusters):
       - Groups of similar reviews/locations
       - Market segments

    2. H1 (Loops / Cycles):
       - Cyclic patterns in sentiment
       - Seasonal loops

    3. H2 (Voids):
       - "Holes" in the data - market gaps
       - Opportunities where no competitor operates

    The key insight is that "holes" in the data often represent:
    - Underserved market segments
    - Geographic gaps
    - Price/quality combinations nobody offers
    - Times when demand exists but supply doesn't

    Uses simplified TDA when ripser is not available.
    """

    def __init__(
        self,
        reviews: List[ReviewData],
        config: Optional[SingularityConfig] = None
    ):
        self.reviews = reviews
        self.config = config or SingularityConfig()

        # Check for ripser availability
        self._ripser_available = self._check_ripser()

        logger.info(
            "topological_analyzer_initialized",
            review_count=len(reviews),
            ripser_available=self._ripser_available
        )

    def _check_ripser(self) -> bool:
        """Check if ripser is available for TDA"""
        if not self.config.topology_use_ripser:
            return False
        try:
            import ripser
            return True
        except ImportError:
            logger.info("ripser_not_available_using_fallback")
            return False

    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════

    def analyze(
        self,
        reviews: Optional[List[ReviewData]] = None
    ) -> List[TopologicalInsight]:
        """
        Run topological analysis on reviews

        Args:
            reviews: Reviews to analyze

        Returns:
            List of TopologicalInsight objects
        """
        reviews = reviews or self.reviews
        insights = []

        # Need sufficient data
        if len(reviews) < 20:
            return [self._create_insufficient_data_insight()]

        # 1. Cluster Analysis (H0 features)
        cluster_insights = self._analyze_clusters(reviews)
        insights.extend(cluster_insights)

        # 2. Gap Analysis (looking for "holes")
        gap_insights = self._analyze_gaps(reviews)
        insights.extend(gap_insights)

        # 3. Persistence Analysis (if ripser available)
        if self._ripser_available:
            persistence_insights = self._analyze_persistence(reviews)
            insights.extend(persistence_insights)
        else:
            # Fallback: simplified topological features
            simplified_insights = self._analyze_simplified_topology(reviews)
            insights.extend(simplified_insights)

        # 4. Bridge Analysis (connecting structures)
        bridge_insights = self._analyze_bridges(reviews)
        insights.extend(bridge_insights)

        logger.info(
            "topological_analysis_complete",
            total_insights=len(insights),
            holes_found=len([i for i in insights if i.feature_type == TopologyFeature.HOLE]),
            clusters_found=len([i for i in insights if i.feature_type == TopologyFeature.CLUSTER])
        )

        return insights

    # ═══════════════════════════════════════════════════════════════════════════
    # CLUSTER ANALYSIS (H0)
    # ═══════════════════════════════════════════════════════════════════════════

    def _analyze_clusters(
        self,
        reviews: List[ReviewData]
    ) -> List[TopologicalInsight]:
        """Analyze cluster structure in the data"""
        insights = []

        # Create feature matrix
        features = self._create_feature_matrix(reviews)
        if features is None or len(features) < 10:
            return insights

        # Hierarchical clustering
        try:
            distances = pdist(features, metric='euclidean')
            Z = linkage(distances, method='ward')

            # Find optimal number of clusters
            for n_clusters in [3, 5, 7]:
                labels = fcluster(Z, n_clusters, criterion='maxclust')

                # Analyze each cluster
                for cluster_id in range(1, n_clusters + 1):
                    cluster_mask = labels == cluster_id
                    cluster_reviews = [r for r, m in zip(reviews, cluster_mask) if m]

                    if len(cluster_reviews) < 5:
                        continue

                    # Characterize cluster
                    insight = self._characterize_cluster(cluster_reviews, cluster_id)
                    if insight:
                        insights.append(insight)

                if insights:
                    break  # Use first successful clustering

        except Exception as e:
            logger.warning("clustering_failed", error=str(e))

        return insights[:10]  # Limit clusters

    def _characterize_cluster(
        self,
        reviews: List[ReviewData],
        cluster_id: int
    ) -> Optional[TopologicalInsight]:
        """Create insight for a cluster"""
        # Get cluster statistics
        sentiments = [
            r.sentiment_score if r.sentiment_score is not None
            else normalize_sentiment(r.rating) if r.rating else 0
            for r in reviews
        ]

        avg_sentiment = safe_mean(sentiments)
        std_sentiment = safe_std(sentiments)

        # Get dominant characteristics
        chains = [r.chain_id for r in reviews if r.chain_id]
        cities = [r.city for r in reviews if r.city]

        dominant_chain = max(set(chains), key=chains.count) if chains else None
        dominant_city = max(set(cities), key=cities.count) if cities else None

        # Determine cluster meaning
        if avg_sentiment > 0.3:
            interpretation = "High-satisfaction segment"
            business_meaning = "Premium experience seekers - potential loyalty program targets"
        elif avg_sentiment < -0.3:
            interpretation = "Dissatisfied segment"
            business_meaning = "At-risk customers - prioritize service recovery"
        else:
            interpretation = "Neutral/Mixed segment"
            business_meaning = "Opportunity for differentiation"

        if dominant_chain:
            interpretation += f" (primarily {dominant_chain})"
        if dominant_city:
            interpretation += f" in {dominant_city}"

        return TopologicalInsight(
            insight_id=generate_id("topo"),
            feature_type=TopologyFeature.CLUSTER,
            dimension=0,
            persistence=std_sentiment,  # Use variability as persistence
            birth=0.0,
            death=float(std_sentiment),
            significance=min(1.0, len(reviews) / 100),
            interpretation=interpretation,
            business_meaning=business_meaning,
            affected_locations=[r.location_id for r in reviews[:10] if r.location_id],
            opportunity_score=0.5 if avg_sentiment > 0 else 0.0,
            risk_score=0.5 if avg_sentiment < 0 else 0.0
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # GAP ANALYSIS (Finding Holes)
    # ═══════════════════════════════════════════════════════════════════════════

    def _analyze_gaps(
        self,
        reviews: List[ReviewData]
    ) -> List[TopologicalInsight]:
        """Find gaps/holes in the data - potential opportunities"""
        insights = []

        # 1. Geographic gaps
        geo_gaps = self._find_geographic_gaps(reviews)
        insights.extend(geo_gaps)

        # 2. Sentiment-Rating gaps (mismatches)
        sentiment_gaps = self._find_sentiment_gaps(reviews)
        insights.extend(sentiment_gaps)

        # 3. Time gaps (periods with no reviews)
        time_gaps = self._find_time_gaps(reviews)
        insights.extend(time_gaps)

        # 4. Chain coverage gaps
        chain_gaps = self._find_chain_gaps(reviews)
        insights.extend(chain_gaps)

        return insights

    def _find_geographic_gaps(
        self,
        reviews: List[ReviewData]
    ) -> List[TopologicalInsight]:
        """Find cities/areas with no coverage"""
        insights = []

        # Get cities with coverage
        covered_cities = set(r.city.lower() for r in reviews if r.city)

        # Get chains
        chains = set(r.chain_id for r in reviews if r.chain_id)

        # For each chain, check which cities they cover vs don't
        for chain in list(chains)[:5]:
            chain_reviews = [r for r in reviews if r.chain_id == chain]
            chain_cities = set(r.city.lower() for r in chain_reviews if r.city)

            # Cities covered by others but not this chain
            other_cities = covered_cities - chain_cities

            if other_cities and len(other_cities) < len(covered_cities):
                missing_count = len(other_cities)
                total_cities = len(covered_cities)

                insight = TopologicalInsight(
                    insight_id=generate_id("topo"),
                    feature_type=TopologyFeature.HOLE,
                    dimension=1,
                    persistence=missing_count / total_cities,
                    birth=0.0,
                    death=1.0,
                    significance=missing_count / total_cities,
                    interpretation=f"{chain} has no presence in {missing_count} cities where competitors operate",
                    business_meaning=f"Geographic expansion opportunity: {', '.join(list(other_cities)[:3])}...",
                    opportunity_score=min(1.0, missing_count / 10),
                    risk_score=0.2
                )
                insights.append(insight)

        return insights[:3]

    def _find_sentiment_gaps(
        self,
        reviews: List[ReviewData]
    ) -> List[TopologicalInsight]:
        """Find gaps between rating and sentiment (potential manipulation or issues)"""
        insights = []

        # Find reviews where rating and sentiment disagree
        mismatches = []
        for r in reviews:
            if r.rating and r.sentiment_score is not None:
                expected_sentiment = normalize_sentiment(r.rating)
                actual_sentiment = r.sentiment_score
                gap = abs(expected_sentiment - actual_sentiment)
                if gap > 0.5:  # Significant mismatch
                    mismatches.append((r, gap, expected_sentiment, actual_sentiment))

        if len(mismatches) > len(reviews) * 0.1:  # More than 10% mismatch
            insight = TopologicalInsight(
                insight_id=generate_id("topo"),
                feature_type=TopologyFeature.HOLE,
                dimension=1,
                persistence=len(mismatches) / len(reviews),
                birth=0.0,
                death=1.0,
                significance=len(mismatches) / len(reviews),
                interpretation=f"{len(mismatches)} reviews show rating-sentiment mismatch",
                business_meaning="Potential review manipulation or complex customer experiences not captured by ratings alone",
                affected_locations=[m[0].location_id for m in mismatches[:10] if m[0].location_id],
                risk_score=0.6
            )
            insights.append(insight)

        return insights

    def _find_time_gaps(
        self,
        reviews: List[ReviewData]
    ) -> List[TopologicalInsight]:
        """Find time periods with no reviews"""
        insights = []

        # Get reviews with timestamps
        dated = [(r.review_time, r) for r in reviews if r.review_time]
        if len(dated) < 10:
            return insights

        dated.sort(key=lambda x: x[0])

        # Find large gaps
        gaps = []
        for i in range(1, len(dated)):
            gap_days = (dated[i][0] - dated[i-1][0]).days
            if gap_days > 7:  # Week gap
                gaps.append((dated[i-1][0], dated[i][0], gap_days))

        if gaps:
            largest_gap = max(gaps, key=lambda x: x[2])
            insight = TopologicalInsight(
                insight_id=generate_id("topo"),
                feature_type=TopologyFeature.VOID,
                dimension=2,
                persistence=largest_gap[2] / 30,  # Normalize to month
                birth=0.0,
                death=largest_gap[2] / 30,
                significance=min(1.0, largest_gap[2] / 30),
                interpretation=f"Largest review gap: {largest_gap[2]} days ({largest_gap[0].strftime('%Y-%m-%d')} to {largest_gap[1].strftime('%Y-%m-%d')})",
                business_meaning="Period of reduced customer engagement or data collection issue",
                risk_score=0.3 if largest_gap[2] > 14 else 0.1
            )
            insights.append(insight)

        return insights

    def _find_chain_gaps(
        self,
        reviews: List[ReviewData]
    ) -> List[TopologicalInsight]:
        """Find quality gaps between chains"""
        insights = []

        # Group by chain
        by_chain = defaultdict(list)
        for r in reviews:
            if r.chain_id:
                sentiment = r.sentiment_score if r.sentiment_score is not None else (
                    normalize_sentiment(r.rating) if r.rating else 0
                )
                by_chain[r.chain_id].append(sentiment)

        if len(by_chain) < 2:
            return insights

        # Calculate average sentiment per chain
        chain_sentiments = {
            chain: safe_mean(sentiments)
            for chain, sentiments in by_chain.items()
            if len(sentiments) >= 5
        }

        if len(chain_sentiments) < 2:
            return insights

        # Find the gap between best and worst
        best_chain = max(chain_sentiments.items(), key=lambda x: x[1])
        worst_chain = min(chain_sentiments.items(), key=lambda x: x[1])

        gap = best_chain[1] - worst_chain[1]

        if gap > 0.3:
            insight = TopologicalInsight(
                insight_id=generate_id("topo"),
                feature_type=TopologyFeature.HOLE,
                dimension=1,
                persistence=gap,
                birth=worst_chain[1],
                death=best_chain[1],
                significance=gap,
                interpretation=f"Quality gap: {best_chain[0]} ({best_chain[1]:.2f}) vs {worst_chain[0]} ({worst_chain[1]:.2f})",
                business_meaning=f"Competitive opportunity: {worst_chain[0]} has room for improvement",
                opportunity_score=gap,
                risk_score=0.0
            )
            insights.append(insight)

        return insights

    # ═══════════════════════════════════════════════════════════════════════════
    # PERSISTENCE ANALYSIS (Full TDA)
    # ═══════════════════════════════════════════════════════════════════════════

    def _analyze_persistence(
        self,
        reviews: List[ReviewData]
    ) -> List[TopologicalInsight]:
        """Full persistent homology analysis using ripser"""
        insights = []

        try:
            import ripser

            # Create point cloud from features
            features = self._create_feature_matrix(reviews)
            if features is None or len(features) < 20:
                return insights

            # Subsample if too large
            if len(features) > 500:
                indices = np.random.choice(len(features), 500, replace=False)
                features = features[indices]

            # Run ripser
            result = ripser.ripser(
                features,
                maxdim=min(self.config.topology_max_dimension, 2)
            )

            # Analyze persistence diagrams
            for dim, dgm in enumerate(result['dgms']):
                if len(dgm) == 0:
                    continue

                # Filter by persistence threshold
                significant = dgm[dgm[:, 1] - dgm[:, 0] > self.config.topology_persistence_threshold]

                for birth, death in significant[:5]:  # Top 5 per dimension
                    if np.isinf(death):
                        death = 1.0  # Cap infinite death

                    persistence = death - birth

                    # Create insight based on dimension
                    if dim == 0:
                        feature_type = TopologyFeature.CLUSTER
                        interpretation = f"Persistent cluster with lifetime {persistence:.2f}"
                        meaning = "Stable market segment"
                    elif dim == 1:
                        feature_type = TopologyFeature.LOOP
                        interpretation = f"Cyclic pattern detected (persistence {persistence:.2f})"
                        meaning = "Potential seasonal or periodic behavior"
                    else:
                        feature_type = TopologyFeature.VOID
                        interpretation = f"Higher-dimensional void (persistence {persistence:.2f})"
                        meaning = "Complex market structure gap"

                    insight = TopologicalInsight(
                        insight_id=generate_id("topo"),
                        feature_type=feature_type,
                        dimension=dim,
                        persistence=float(persistence),
                        birth=float(birth),
                        death=float(death),
                        significance=float(persistence),
                        interpretation=interpretation,
                        business_meaning=meaning
                    )
                    insights.append(insight)

        except Exception as e:
            logger.warning("ripser_analysis_failed", error=str(e))

        return insights

    # ═══════════════════════════════════════════════════════════════════════════
    # SIMPLIFIED TOPOLOGY (Fallback)
    # ═══════════════════════════════════════════════════════════════════════════

    def _analyze_simplified_topology(
        self,
        reviews: List[ReviewData]
    ) -> List[TopologicalInsight]:
        """Simplified topological analysis when ripser not available"""
        insights = []

        features = self._create_feature_matrix(reviews)
        if features is None or len(features) < 20:
            return insights

        # Approximate H0: Use density-based analysis
        try:
            nn = NearestNeighbors(n_neighbors=5)
            nn.fit(features)
            distances, _ = nn.kneighbors(features)

            # Average distance to neighbors
            avg_distances = distances.mean(axis=1)

            # Find sparse regions (potential holes)
            threshold = np.percentile(avg_distances, 90)
            sparse_indices = np.where(avg_distances > threshold)[0]

            if len(sparse_indices) > 0:
                sparse_reviews = [reviews[i] for i in sparse_indices if i < len(reviews)]
                insight = TopologicalInsight(
                    insight_id=generate_id("topo"),
                    feature_type=TopologyFeature.HOLE,
                    dimension=1,
                    persistence=float(np.mean(avg_distances[sparse_indices])),
                    birth=0.0,
                    death=float(threshold),
                    significance=len(sparse_indices) / len(reviews),
                    interpretation=f"{len(sparse_indices)} reviews in sparse regions",
                    business_meaning="Underserved market segments or outlier experiences",
                    affected_locations=[r.location_id for r in sparse_reviews[:10] if r.location_id],
                    opportunity_score=0.5
                )
                insights.append(insight)

            # Find dense regions (clusters)
            dense_threshold = np.percentile(avg_distances, 10)
            dense_indices = np.where(avg_distances < dense_threshold)[0]

            if len(dense_indices) > 5:
                insight = TopologicalInsight(
                    insight_id=generate_id("topo"),
                    feature_type=TopologyFeature.CLUSTER,
                    dimension=0,
                    persistence=float(np.std(avg_distances[dense_indices])),
                    birth=0.0,
                    death=float(dense_threshold),
                    significance=len(dense_indices) / len(reviews),
                    interpretation=f"{len(dense_indices)} reviews in dense regions",
                    business_meaning="Core customer segments with consistent experiences"
                )
                insights.append(insight)

        except Exception as e:
            logger.warning("simplified_topology_failed", error=str(e))

        return insights

    # ═══════════════════════════════════════════════════════════════════════════
    # BRIDGE ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════

    def _analyze_bridges(
        self,
        reviews: List[ReviewData]
    ) -> List[TopologicalInsight]:
        """Find bridging structures connecting different clusters"""
        insights = []

        # Group by chain and city
        by_chain = defaultdict(list)
        by_city = defaultdict(list)

        for r in reviews:
            if r.chain_id:
                by_chain[r.chain_id].append(r)
            if r.city:
                by_city[r.city].append(r)

        # Find chains that appear in many cities (bridges)
        chain_city_coverage = {
            chain: len(set(r.city for r in revs if r.city))
            for chain, revs in by_chain.items()
        }

        if chain_city_coverage:
            max_coverage = max(chain_city_coverage.values())
            bridges = [
                chain for chain, coverage in chain_city_coverage.items()
                if coverage == max_coverage and coverage > 1
            ]

            for chain in bridges[:2]:
                insight = TopologicalInsight(
                    insight_id=generate_id("topo"),
                    feature_type=TopologyFeature.BRIDGE,
                    dimension=1,
                    persistence=chain_city_coverage[chain] / len(by_city),
                    birth=0.0,
                    death=1.0,
                    significance=chain_city_coverage[chain] / len(by_city),
                    interpretation=f"{chain} serves as market bridge across {chain_city_coverage[chain]} cities",
                    business_meaning="Brand with strong geographic connectivity - potential benchmark"
                )
                insights.append(insight)

        return insights

    # ═══════════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def _create_feature_matrix(
        self,
        reviews: List[ReviewData]
    ) -> Optional[np.ndarray]:
        """Create feature matrix for topological analysis"""
        if not reviews:
            return None

        features = []
        for r in reviews:
            # Basic features
            rating = r.rating if r.rating else 3.0
            sentiment = r.sentiment_score if r.sentiment_score is not None else normalize_sentiment(rating)

            # Time features (if available)
            if r.review_time:
                day_of_week = r.review_time.weekday() / 6  # 0-1
                month = r.review_time.month / 12  # 0-1
            else:
                day_of_week = 0.5
                month = 0.5

            # Text length (normalized)
            text_len = len(r.text) / 1000 if r.text else 0

            features.append([rating / 5, sentiment, day_of_week, month, text_len])

        # Scale features
        scaler = StandardScaler()
        try:
            scaled = scaler.fit_transform(features)
            return scaled
        except Exception:
            return np.array(features)

    def _create_insufficient_data_insight(self) -> TopologicalInsight:
        """Create insight when there's not enough data"""
        return TopologicalInsight(
            insight_id=generate_id("topo"),
            feature_type=TopologyFeature.VOID,
            dimension=0,
            persistence=0.0,
            birth=0.0,
            death=0.0,
            significance=0.0,
            interpretation="Insufficient data for topological analysis",
            business_meaning="Need more reviews for meaningful pattern detection",
            risk_score=0.3
        )
