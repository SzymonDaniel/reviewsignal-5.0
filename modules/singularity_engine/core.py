# ═══════════════════════════════════════════════════════════════════════════════
# SINGULARITY ENGINE - Core Orchestrator
# Main engine that coordinates all analysis modules
# ═══════════════════════════════════════════════════════════════════════════════

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import structlog

from .models import (
    SingularityConfig,
    SingularityResult,
    SingularityInsight,
    ReviewData,
    EventData,
    TemporalFoldResult,
    SemanticResonance,
    PropheticReview,
    EmergentTheme,
    CausalGraph,
    TopologicalInsight,
    ModuleContribution,
    InsightConfidence,
    TradingAction,
)
from .utils import (
    generate_analysis_id,
    Timer,
    SimpleCache,
    combine_confidences,
    calculate_confidence_level,
)

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SINGULARITY ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class SingularityEngine:
    """
    Singularity Engine - Beyond Human Cognition Analytics

    Orchestrates multiple analysis modules:
    - Temporal Manifold: Fold time to find hidden patterns
    - Semantic Resonance: Detect unexpected correlations
    - Causal Archaeology: Dig deep into root causes (7+ levels)
    - Topological Analysis: Find "holes" in data

    All modules converge to produce synthesized trading signals.
    """

    def __init__(
        self,
        reviews: List[ReviewData],
        config: Optional[SingularityConfig] = None,
        events: Optional[List[EventData]] = None,
        echo_engine: Optional[Any] = None
    ):
        """
        Initialize Singularity Engine

        Args:
            reviews: List of ReviewData objects to analyze
            config: Engine configuration (uses defaults if not provided)
            events: Optional external events for temporal alignment
            echo_engine: Optional Echo Engine instance for integration
        """
        self.reviews = reviews
        self.config = config or SingularityConfig()
        self.events = events or []
        self.echo_engine = echo_engine

        # Initialize cache
        self._cache = SimpleCache(ttl_seconds=self.config.cache_ttl_seconds)

        # Module instances (lazy loaded)
        self._temporal_manifold = None
        self._semantic_resonance = None
        self._causal_archaeologist = None
        self._topological_analyzer = None
        self._signal_synthesizer = None
        self._echo_integration = None

        # Analysis state
        self._analysis_id = None
        self._start_time = None

        logger.info(
            "singularity_engine_initialized",
            review_count=len(reviews),
            event_count=len(events),
            has_echo_engine=echo_engine is not None
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # LAZY MODULE LOADING
    # ═══════════════════════════════════════════════════════════════════════════

    @property
    def temporal_manifold(self):
        """Lazy load Temporal Manifold module"""
        if self._temporal_manifold is None:
            from .temporal_manifold import TemporalManifold
            self._temporal_manifold = TemporalManifold(
                reviews=self.reviews,
                events=self.events,
                config=self.config
            )
        return self._temporal_manifold

    @property
    def semantic_resonance(self):
        """Lazy load Semantic Resonance module"""
        if self._semantic_resonance is None:
            from .semantic_resonance import SemanticResonanceField
            self._semantic_resonance = SemanticResonanceField(
                reviews=self.reviews,
                config=self.config
            )
        return self._semantic_resonance

    @property
    def causal_archaeologist(self):
        """Lazy load Causal Archaeologist module"""
        if self._causal_archaeologist is None:
            from .causal_archaeology import CausalArchaeologist
            self._causal_archaeologist = CausalArchaeologist(
                reviews=self.reviews,
                config=self.config
            )
        return self._causal_archaeologist

    @property
    def topological_analyzer(self):
        """Lazy load Topological Analyzer module"""
        if self._topological_analyzer is None:
            from .topological_analyzer import TopologicalAnalyzer
            self._topological_analyzer = TopologicalAnalyzer(
                reviews=self.reviews,
                config=self.config
            )
        return self._topological_analyzer

    @property
    def signal_synthesizer(self):
        """Lazy load Signal Synthesizer"""
        if self._signal_synthesizer is None:
            from .signal_synthesizer import SignalSynthesizer
            self._signal_synthesizer = SignalSynthesizer(config=self.config)
        return self._signal_synthesizer

    @property
    def echo_integration(self):
        """Lazy load Echo Engine Integration"""
        if self._echo_integration is None and self.echo_engine is not None:
            from .integration import EchoSingularityIntegration
            self._echo_integration = EchoSingularityIntegration(
                echo_engine=self.echo_engine,
                config=self.config
            )
        return self._echo_integration

    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN ANALYSIS METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def analyze(
        self,
        modules: Optional[List[str]] = None,
        chain_filter: Optional[str] = None,
        city_filter: Optional[str] = None,
        max_depth: int = 7,
        parallel: bool = True
    ) -> SingularityResult:
        """
        Run full Singularity Engine analysis

        Args:
            modules: List of modules to run. Options:
                     ['temporal', 'semantic', 'causal', 'topology', 'echo']
                     If None, runs all available modules.
            chain_filter: Filter reviews by chain (e.g., "starbucks")
            city_filter: Filter reviews by city (e.g., "new york")
            max_depth: Maximum depth for causal archaeology
            parallel: Run modules in parallel (faster but more memory)

        Returns:
            SingularityResult with all findings and synthesized insights
        """
        self._analysis_id = generate_analysis_id()
        self._start_time = datetime.utcnow()

        logger.info(
            "singularity_analysis_started",
            analysis_id=self._analysis_id,
            modules=modules,
            chain_filter=chain_filter,
            city_filter=city_filter
        )

        # Filter reviews if needed
        filtered_reviews = self._filter_reviews(chain_filter, city_filter)

        if len(filtered_reviews) < self.config.temporal_min_samples:
            logger.warning(
                "insufficient_reviews",
                count=len(filtered_reviews),
                minimum=self.config.temporal_min_samples
            )
            return self._create_empty_result(
                chain_filter, city_filter,
                warning="Insufficient reviews for analysis"
            )

        # Determine which modules to run
        available_modules = ['temporal', 'semantic', 'causal', 'topology']
        if self.echo_engine is not None:
            available_modules.append('echo')

        modules_to_run = modules or available_modules
        modules_to_run = [m for m in modules_to_run if m in available_modules]

        # Run analysis
        if parallel:
            results = self._run_parallel(filtered_reviews, modules_to_run, max_depth)
        else:
            results = self._run_sequential(filtered_reviews, modules_to_run, max_depth)

        # Synthesize results
        synthesized = self._synthesize_results(results, filtered_reviews)

        # Build final result
        result = self._build_result(
            results=results,
            synthesized=synthesized,
            chain_filter=chain_filter,
            city_filter=city_filter,
            modules_used=modules_to_run,
            review_count=len(filtered_reviews)
        )

        elapsed_ms = int((datetime.utcnow() - self._start_time).total_seconds() * 1000)
        result.processing_time_ms = elapsed_ms

        logger.info(
            "singularity_analysis_completed",
            analysis_id=self._analysis_id,
            elapsed_ms=elapsed_ms,
            insight_count=len(result.synthesized_insights)
        )

        return result

    def analyze_symptom(
        self,
        symptom: str,
        max_depth: int = 7
    ) -> CausalGraph:
        """
        Deep-dive causal analysis for a specific symptom

        Args:
            symptom: The symptom to investigate (e.g., "rating dropped 20%")
            max_depth: How deep to dig (up to 7+ levels)

        Returns:
            CausalGraph with full causal chain
        """
        logger.info("analyzing_symptom", symptom=symptom, max_depth=max_depth)
        return self.causal_archaeologist.investigate(symptom, max_depth=max_depth)

    def find_prophetic_reviews(
        self,
        lookback_days: int = 90
    ) -> List[PropheticReview]:
        """
        Find reviews that predicted future events

        Args:
            lookback_days: How far back to look

        Returns:
            List of prophetic reviews with their predictions
        """
        logger.info("finding_prophetic_reviews", lookback_days=lookback_days)
        return self.semantic_resonance.find_prophetic_reviews(lookback_days)

    def detect_emergent_themes(
        self,
        min_reviews: int = 5,
        growth_threshold: float = 0.2
    ) -> List[EmergentTheme]:
        """
        Detect emerging themes in reviews

        Args:
            min_reviews: Minimum reviews for a theme to be significant
            growth_threshold: Minimum growth rate to be considered "emergent"

        Returns:
            List of emergent themes
        """
        logger.info(
            "detecting_emergent_themes",
            min_reviews=min_reviews,
            growth_threshold=growth_threshold
        )
        return self.semantic_resonance.detect_emergent_themes(
            min_reviews=min_reviews,
            growth_threshold=growth_threshold
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # PRIVATE METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def _filter_reviews(
        self,
        chain_filter: Optional[str],
        city_filter: Optional[str]
    ) -> List[ReviewData]:
        """Filter reviews by chain and/or city"""
        filtered = self.reviews

        if chain_filter:
            chain_lower = chain_filter.lower()
            filtered = [r for r in filtered if r.chain_id and chain_lower in r.chain_id.lower()]

        if city_filter:
            city_lower = city_filter.lower()
            filtered = [r for r in filtered if r.city and city_lower in r.city.lower()]

        return filtered

    def _run_parallel(
        self,
        reviews: List[ReviewData],
        modules: List[str],
        max_depth: int
    ) -> Dict[str, Any]:
        """Run modules in parallel using ThreadPoolExecutor"""
        results = {}

        with ThreadPoolExecutor(max_workers=len(modules)) as executor:
            futures = {}

            if 'temporal' in modules:
                futures['temporal'] = executor.submit(
                    self._run_temporal, reviews
                )

            if 'semantic' in modules:
                futures['semantic'] = executor.submit(
                    self._run_semantic, reviews
                )

            if 'causal' in modules:
                futures['causal'] = executor.submit(
                    self._run_causal, reviews, max_depth
                )

            if 'topology' in modules:
                futures['topology'] = executor.submit(
                    self._run_topology, reviews
                )

            if 'echo' in modules and self.echo_integration:
                futures['echo'] = executor.submit(
                    self._run_echo_integration, reviews
                )

            # Collect results
            for module_name, future in futures.items():
                try:
                    results[module_name] = future.result(
                        timeout=self.config.max_processing_time_seconds
                    )
                except Exception as e:
                    logger.error(
                        "module_failed",
                        module=module_name,
                        error=str(e)
                    )
                    results[module_name] = {'error': str(e)}

        return results

    def _run_sequential(
        self,
        reviews: List[ReviewData],
        modules: List[str],
        max_depth: int
    ) -> Dict[str, Any]:
        """Run modules sequentially"""
        results = {}

        if 'temporal' in modules:
            try:
                results['temporal'] = self._run_temporal(reviews)
            except Exception as e:
                logger.error("temporal_failed", error=str(e))
                results['temporal'] = {'error': str(e)}

        if 'semantic' in modules:
            try:
                results['semantic'] = self._run_semantic(reviews)
            except Exception as e:
                logger.error("semantic_failed", error=str(e))
                results['semantic'] = {'error': str(e)}

        if 'causal' in modules:
            try:
                results['causal'] = self._run_causal(reviews, max_depth)
            except Exception as e:
                logger.error("causal_failed", error=str(e))
                results['causal'] = {'error': str(e)}

        if 'topology' in modules:
            try:
                results['topology'] = self._run_topology(reviews)
            except Exception as e:
                logger.error("topology_failed", error=str(e))
                results['topology'] = {'error': str(e)}

        if 'echo' in modules and self.echo_integration:
            try:
                results['echo'] = self._run_echo_integration(reviews)
            except Exception as e:
                logger.error("echo_failed", error=str(e))
                results['echo'] = {'error': str(e)}

        return results

    def _run_temporal(self, reviews: List[ReviewData]) -> Dict[str, Any]:
        """Run temporal manifold analysis"""
        with Timer("temporal_analysis"):
            fold_results = self.temporal_manifold.analyze_all_folds(reviews)
            return {
                'fold_results': fold_results,
                'anomaly_count': sum(f.anomaly_count for f in fold_results),
                'strongest_patterns': [
                    f.strongest_pattern for f in fold_results
                    if f.strongest_pattern
                ]
            }

    def _run_semantic(self, reviews: List[ReviewData]) -> Dict[str, Any]:
        """Run semantic resonance analysis"""
        with Timer("semantic_analysis"):
            resonances = self.semantic_resonance.find_resonances(reviews)
            prophetic = self.semantic_resonance.find_prophetic_reviews(
                lookback_days=self.config.temporal_lookback_days
            )
            themes = self.semantic_resonance.detect_emergent_themes()

            return {
                'resonances': resonances,
                'prophetic_reviews': prophetic,
                'emergent_themes': themes
            }

    def _run_causal(self, reviews: List[ReviewData], max_depth: int) -> Dict[str, Any]:
        """Run causal archaeology analysis"""
        with Timer("causal_analysis"):
            # Find main symptoms to investigate
            symptoms = self.causal_archaeologist.identify_symptoms(reviews)

            # Investigate top symptoms
            graphs = []
            for symptom in symptoms[:3]:  # Top 3 symptoms
                graph = self.causal_archaeologist.investigate(
                    symptom=symptom,
                    max_depth=min(max_depth, self.config.causal_max_depth)
                )
                graphs.append(graph)

            return {
                'causal_graphs': graphs,
                'symptoms_found': len(symptoms)
            }

    def _run_topology(self, reviews: List[ReviewData]) -> Dict[str, Any]:
        """Run topological analysis"""
        with Timer("topological_analysis"):
            insights = self.topological_analyzer.analyze(reviews)
            return {
                'insights': insights,
                'holes_found': len([i for i in insights if i.feature_type.value == 'hole']),
                'clusters_found': len([i for i in insights if i.feature_type.value == 'cluster'])
            }

    def _run_echo_integration(self, reviews: List[ReviewData]) -> Dict[str, Any]:
        """Run Echo Engine integration"""
        with Timer("echo_integration"):
            if not self.echo_integration:
                return {'error': 'Echo Engine not available'}

            return self.echo_integration.analyze_with_echo(reviews)

    def _synthesize_results(
        self,
        results: Dict[str, Any],
        reviews: List[ReviewData]
    ) -> List[SingularityInsight]:
        """Synthesize results from all modules into actionable insights"""
        return self.signal_synthesizer.synthesize(
            temporal_results=results.get('temporal', {}),
            semantic_results=results.get('semantic', {}),
            causal_results=results.get('causal', {}),
            topology_results=results.get('topology', {}),
            echo_results=results.get('echo', {}),
            reviews=reviews
        )

    def _build_result(
        self,
        results: Dict[str, Any],
        synthesized: List[SingularityInsight],
        chain_filter: Optional[str],
        city_filter: Optional[str],
        modules_used: List[str],
        review_count: int
    ) -> SingularityResult:
        """Build the final SingularityResult object"""
        # Extract temporal results
        temporal_results = []
        if 'temporal' in results and 'fold_results' in results['temporal']:
            temporal_results = results['temporal']['fold_results']

        # Extract semantic results
        semantic_resonances = []
        prophetic_reviews = []
        emergent_themes = []
        if 'semantic' in results:
            semantic_resonances = results['semantic'].get('resonances', [])
            prophetic_reviews = results['semantic'].get('prophetic_reviews', [])
            emergent_themes = results['semantic'].get('emergent_themes', [])

        # Extract causal results
        causal_graphs = []
        if 'causal' in results and 'causal_graphs' in results['causal']:
            causal_graphs = results['causal']['causal_graphs']

        # Extract topological results
        topological_insights = []
        if 'topology' in results and 'insights' in results['topology']:
            topological_insights = results['topology']['insights']

        # Calculate overall confidence
        if synthesized:
            overall_confidence = np.mean([s.confidence_score for s in synthesized])
        else:
            overall_confidence = 0.0

        # Collect warnings and errors
        warnings = []
        errors = []
        for module_name, module_result in results.items():
            if isinstance(module_result, dict) and 'error' in module_result:
                errors.append(f"{module_name}: {module_result['error']}")

        # Get unique locations
        location_ids = set(r.location_id for r in self.reviews if r.location_id)

        return SingularityResult(
            analysis_id=self._analysis_id,
            chain_filter=chain_filter,
            city_filter=city_filter,
            analysis_period_days=self.config.temporal_lookback_days,
            temporal_results=temporal_results,
            semantic_resonances=semantic_resonances,
            prophetic_reviews=prophetic_reviews,
            emergent_themes=emergent_themes,
            causal_graphs=causal_graphs,
            topological_insights=topological_insights,
            synthesized_insights=synthesized,
            overall_confidence=float(overall_confidence),
            modules_used=modules_used,
            total_reviews_analyzed=review_count,
            total_locations_analyzed=len(location_ids),
            warnings=warnings,
            errors=errors
        )

    def _create_empty_result(
        self,
        chain_filter: Optional[str],
        city_filter: Optional[str],
        warning: str
    ) -> SingularityResult:
        """Create empty result with warning"""
        return SingularityResult(
            analysis_id=self._analysis_id or generate_analysis_id(),
            chain_filter=chain_filter,
            city_filter=city_filter,
            analysis_period_days=self.config.temporal_lookback_days,
            warnings=[warning]
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def get_review_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded reviews"""
        if not self.reviews:
            return {'count': 0}

        ratings = [r.rating for r in self.reviews if r.rating]
        sentiments = [r.sentiment_score for r in self.reviews if r.sentiment_score is not None]
        chains = set(r.chain_id for r in self.reviews if r.chain_id)
        cities = set(r.city for r in self.reviews if r.city)

        return {
            'count': len(self.reviews),
            'avg_rating': float(np.mean(ratings)) if ratings else None,
            'avg_sentiment': float(np.mean(sentiments)) if sentiments else None,
            'unique_chains': len(chains),
            'unique_cities': len(cities),
            'date_range': self._get_date_range()
        }

    def _get_date_range(self) -> Dict[str, str]:
        """Get date range of reviews"""
        dates = [r.review_time for r in self.reviews if r.review_time]
        if not dates:
            return {'min': None, 'max': None}
        return {
            'min': min(dates).isoformat(),
            'max': max(dates).isoformat()
        }

    def clear_cache(self) -> None:
        """Clear internal cache"""
        self._cache.clear()
        logger.info("cache_cleared")


# ═══════════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def create_singularity_engine_from_db(
    chain_filter: Optional[str] = None,
    city_filter: Optional[str] = None,
    days_back: int = 90,
    include_echo: bool = True,
    config: Optional[SingularityConfig] = None,
    db_connection: Optional[Any] = None
) -> Tuple[SingularityEngine, Optional[Any]]:
    """
    Factory function to create SingularityEngine from database

    Args:
        chain_filter: Filter by chain name
        city_filter: Filter by city name
        days_back: How many days of reviews to load
        include_echo: Whether to include Echo Engine
        config: Custom configuration
        db_connection: Optional existing database connection

    Returns:
        Tuple of (SingularityEngine, EchoEngine or None)

    Example:
        engine, echo = create_singularity_engine_from_db(
            chain_filter="starbucks",
            include_echo=True
        )
        result = engine.analyze()
    """
    import psycopg2
    from psycopg2 import pool
    from datetime import datetime, timedelta
    import os

    # Database connection with connection pooling for enterprise scalability
    if db_connection is None:
        # Get credentials from environment (secure)
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'reviewsignal')
        db_user = os.getenv('DB_USER', 'reviewsignal')
        db_pass = os.getenv('DB_PASS')
        if not db_pass:
            raise RuntimeError("DB_PASS environment variable must be set")

        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_pass
        )
    else:
        conn = db_connection

    try:
        cursor = conn.cursor()

        # Build query
        query = """
            SELECT
                r.id::text,
                r.location_id::text,
                r.review_text,
                r.rating,
                r.sentiment_score,
                r.sentiment_label,
                r.review_time,
                l.chain_id,
                l.city,
                l.name as location_name
            FROM reviews r
            LEFT JOIN locations l ON r.location_id = l.id
            WHERE r.review_time >= %s
        """
        params = [datetime.utcnow() - timedelta(days=days_back)]

        if chain_filter:
            query += " AND LOWER(l.chain_id) LIKE %s"
            params.append(f"%{chain_filter.lower()}%")

        if city_filter:
            query += " AND LOWER(l.city) LIKE %s"
            params.append(f"%{city_filter.lower()}%")

        query += " ORDER BY r.review_time DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Convert to ReviewData objects
        reviews = []
        for row in rows:
            review = ReviewData(
                review_id=row[0],
                location_id=row[1],
                text=row[2] or "",
                rating=float(row[3]) if row[3] else 3.0,
                sentiment_score=float(row[4]) if row[4] else None,
                sentiment_label=row[5],
                review_time=row[6],
                chain_id=row[7],
                city=row[8],
                location_name=row[9]
            )
            reviews.append(review)

        logger.info(
            "reviews_loaded_from_db",
            count=len(reviews),
            chain_filter=chain_filter,
            city_filter=city_filter,
            days_back=days_back
        )

        # Load Echo Engine if requested
        echo_engine = None
        if include_echo:
            try:
                from ..echo_engine import EchoEngine
                echo_engine = EchoEngine()
                logger.info("echo_engine_loaded")
            except ImportError:
                logger.warning("echo_engine_not_available")

        # Create engine
        engine = SingularityEngine(
            reviews=reviews,
            config=config,
            echo_engine=echo_engine
        )

        return engine, echo_engine

    finally:
        if db_connection is None:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def quick_analyze(
    chain: str,
    city: Optional[str] = None,
    days: int = 30
) -> SingularityResult:
    """
    Quick analysis for a chain/city combination

    Args:
        chain: Chain name (e.g., "starbucks")
        city: Optional city filter
        days: Days of data to analyze

    Returns:
        SingularityResult

    Example:
        result = quick_analyze("starbucks", "new york", days=14)
        print(result.synthesized_insights[0].synthesis)
    """
    engine, _ = create_singularity_engine_from_db(
        chain_filter=chain,
        city_filter=city,
        days_back=days,
        include_echo=False
    )
    return engine.analyze()


def deep_causal_analysis(
    chain: str,
    symptom: str,
    max_depth: int = 7
) -> CausalGraph:
    """
    Deep causal analysis for a specific symptom

    Args:
        chain: Chain name
        symptom: Symptom to investigate
        max_depth: How deep to dig

    Returns:
        CausalGraph with full causal chain

    Example:
        graph = deep_causal_analysis(
            "starbucks",
            "rating dropped 20% in Q4",
            max_depth=7
        )
        print(f"Root causes: {graph.root_causes}")
    """
    engine, _ = create_singularity_engine_from_db(
        chain_filter=chain,
        include_echo=False
    )
    return engine.analyze_symptom(symptom, max_depth=max_depth)
