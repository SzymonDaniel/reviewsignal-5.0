#!/usr/bin/env python3
"""
ECHO-NEURAL BRIDGE - Integration between Echo Engine and Neural Core
Connects quantum-inspired sentiment propagation with semantic embeddings.

This bridge enables:
1. Semantic similarity weighting in propagation matrix
2. Embedding-based anomaly detection
3. Review clustering for better brand analysis
4. Neural-enhanced trading signals

Author: ReviewSignal Team
Version: 5.1.0
Date: February 2026
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
import structlog

logger = structlog.get_logger()


@dataclass
class NeuralEnhancedSignal:
    """Trading signal enhanced with neural analysis"""
    # Base signal info
    brand: str
    signal: str  # BUY, HOLD, SELL
    confidence: float

    # Echo Engine metrics
    echo_chaos_index: float
    echo_mean: float
    echo_stability: str

    # Neural metrics
    semantic_coherence: float  # How consistent are reviews semantically
    anomaly_rate: float  # Percentage of anomalous reviews
    sentiment_momentum: float  # Neural-detected sentiment trend

    # Combined score
    combined_score: float
    risk_adjusted_score: float

    # Recommendations
    recommendation: str
    key_factors: List[str]

    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return asdict(self)


class EchoNeuralBridge:
    """
    Bridge connecting Echo Engine with Neural Core.
    Enhances sentiment propagation with semantic understanding.
    """

    def __init__(self, echo_engine=None, neural_core=None):
        """
        Initialize the bridge.

        Args:
            echo_engine: EchoEngine instance (lazy loaded if None)
            neural_core: NeuralCore instance (lazy loaded if None)
        """
        self._echo_engine = echo_engine
        self._neural_core = neural_core
        self._semantic_cache: Dict[str, np.ndarray] = {}

        logger.info("echo_neural_bridge_initialized")

    @property
    def echo_engine(self):
        if self._echo_engine is None:
            from modules.echo_engine import create_echo_engine_from_db
            self._echo_engine = create_echo_engine_from_db()
        return self._echo_engine

    @property
    def neural_core(self):
        if self._neural_core is None:
            from modules.neural_core import get_neural_core
            self._neural_core = get_neural_core()
        return self._neural_core

    # ─────────────────────────────────────────────────────────────
    # SEMANTIC PROPAGATION WEIGHTS
    # ─────────────────────────────────────────────────────────────

    def compute_semantic_similarity_matrix(
        self,
        review_texts: Dict[str, List[str]],
        max_reviews_per_location: int = 10
    ) -> np.ndarray:
        """
        Compute semantic similarity matrix between locations based on reviews.

        Args:
            review_texts: Dict mapping location_id to list of review texts
            max_reviews_per_location: Max reviews to consider per location

        Returns:
            Similarity matrix (n_locations x n_locations)
        """
        location_ids = list(review_texts.keys())
        n = len(location_ids)

        # Get average embedding for each location
        location_embeddings = []

        for loc_id in location_ids:
            reviews = review_texts[loc_id][:max_reviews_per_location]

            if not reviews:
                # Use zero vector for locations without reviews
                location_embeddings.append(np.zeros(384))
                continue

            # Get embeddings for reviews
            embeddings = self.neural_core.embed_batch(reviews)

            # Average embedding
            avg_embedding = np.mean(embeddings, axis=0)
            location_embeddings.append(avg_embedding)

        embeddings_matrix = np.array(location_embeddings)

        # Compute cosine similarity matrix
        norms = np.linalg.norm(embeddings_matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        normalized = embeddings_matrix / norms

        similarity_matrix = normalized @ normalized.T

        return similarity_matrix

    def enhance_propagation_with_semantics(
        self,
        review_texts: Dict[str, List[str]],
        semantic_weight: float = 0.1
    ) -> None:
        """
        Enhance Echo Engine propagation matrix with semantic similarities.

        Args:
            review_texts: Dict mapping location_id to list of review texts
            semantic_weight: Weight for semantic similarity (0-1)
        """
        # This would modify the Echo Engine's propagation matrix
        # For now, we log and store for future use
        logger.info(
            "semantic_enhancement_computed",
            n_locations=len(review_texts),
            semantic_weight=semantic_weight
        )

        # Store semantic similarities for signal generation
        sim_matrix = self.compute_semantic_similarity_matrix(review_texts)
        self._semantic_cache["similarity_matrix"] = sim_matrix
        self._semantic_cache["location_ids"] = list(review_texts.keys())

    # ─────────────────────────────────────────────────────────────
    # NEURAL-ENHANCED ANALYSIS
    # ─────────────────────────────────────────────────────────────

    def analyze_brand_reviews(
        self,
        brand: str,
        reviews: List[Dict],
        n_clusters: int = 5
    ) -> Dict:
        """
        Analyze brand reviews using neural embeddings.

        Args:
            brand: Brand name
            reviews: List of review dicts with 'text', 'rating', 'location_id'
            n_clusters: Number of topic clusters

        Returns:
            Analysis result with themes, anomalies, sentiment
        """
        if not reviews:
            return {
                "brand": brand,
                "status": "no_reviews",
                "analyzed_at": datetime.utcnow().isoformat()
            }

        # Extract texts and compute embeddings
        texts = [r.get("text", "") for r in reviews if r.get("text")]
        ratings = [r.get("rating", 3.0) for r in reviews]

        if not texts:
            return {
                "brand": brand,
                "status": "no_text_content",
                "analyzed_at": datetime.utcnow().isoformat()
            }

        embeddings = self.neural_core.embed_batch(texts)

        # Calculate semantic coherence (how similar are reviews to each other)
        if len(embeddings) > 1:
            centroid = np.mean(embeddings, axis=0)
            distances = [np.linalg.norm(e - centroid) for e in embeddings]
            coherence = 1.0 / (1.0 + np.mean(distances))
        else:
            coherence = 1.0

        # Check for anomalies in ratings
        anomalies = []
        for i, (review, rating) in enumerate(zip(reviews, ratings)):
            location_id = review.get("location_id", f"unknown_{i}")
            prediction = self.neural_core.check_anomaly(location_id, rating)
            if prediction.is_anomaly:
                anomalies.append({
                    "index": i,
                    "rating": rating,
                    "score": prediction.anomaly_score,
                    "text_preview": texts[i][:100] if i < len(texts) else ""
                })

        # Calculate sentiment momentum
        # Group by time if available, otherwise use position
        recent_ratings = ratings[-10:] if len(ratings) > 10 else ratings
        older_ratings = ratings[:-10] if len(ratings) > 10 else []

        if older_ratings:
            momentum = np.mean(recent_ratings) - np.mean(older_ratings)
        else:
            momentum = 0.0

        # Find representative reviews (closest to centroid)
        if len(embeddings) > 0:
            centroid = np.mean(embeddings, axis=0)
            distances = [np.linalg.norm(e - centroid) for e in embeddings]
            representative_idx = int(np.argmin(distances))
            representative_review = texts[representative_idx][:200]
        else:
            representative_review = ""

        return {
            "brand": brand,
            "total_reviews": len(reviews),
            "avg_rating": round(float(np.mean(ratings)), 2),
            "semantic_coherence": round(coherence, 4),
            "sentiment_momentum": round(momentum, 4),
            "anomaly_count": len(anomalies),
            "anomaly_rate": round(len(anomalies) / len(reviews), 4) if reviews else 0,
            "anomalies": anomalies[:5],  # Top 5
            "representative_review": representative_review,
            "analyzed_at": datetime.utcnow().isoformat()
        }

    # ─────────────────────────────────────────────────────────────
    # NEURAL-ENHANCED TRADING SIGNALS
    # ─────────────────────────────────────────────────────────────

    def generate_neural_enhanced_signal(
        self,
        brand: str,
        reviews: Optional[List[Dict]] = None,
        n_trials: int = 300
    ) -> NeuralEnhancedSignal:
        """
        Generate trading signal enhanced with neural analysis.

        Args:
            brand: Brand to analyze
            reviews: Optional list of reviews (will fetch if not provided)
            n_trials: Monte Carlo trials for Echo Engine

        Returns:
            NeuralEnhancedSignal with combined analysis
        """
        # 1. Get base Echo Engine signal
        echo_signal = self.echo_engine.generate_trading_signal(brand, n_trials)

        # 2. Perform neural analysis if reviews provided
        if reviews:
            neural_analysis = self.analyze_brand_reviews(brand, reviews)
            semantic_coherence = neural_analysis.get("semantic_coherence", 0.5)
            anomaly_rate = neural_analysis.get("anomaly_rate", 0.0)
            sentiment_momentum = neural_analysis.get("sentiment_momentum", 0.0)
        else:
            semantic_coherence = 0.5
            anomaly_rate = 0.0
            sentiment_momentum = 0.0

        # 3. Combine signals
        # Echo score: chaos_index weighted (lower = better)
        echo_score = max(0, 1 - (echo_signal.chaos_index / 10))

        # Neural score: coherence + low anomaly rate + positive momentum
        neural_score = (
            semantic_coherence * 0.4 +
            (1 - anomaly_rate) * 0.3 +
            (0.5 + min(0.5, max(-0.5, sentiment_momentum))) * 0.3
        )

        # Combined score (50% echo, 50% neural)
        combined_score = echo_score * 0.5 + neural_score * 0.5

        # Risk adjustment based on anomaly rate
        risk_factor = 1 - (anomaly_rate * 0.5)
        risk_adjusted_score = combined_score * risk_factor

        # Determine final signal
        if risk_adjusted_score > 0.7:
            final_signal = "BUY"
            recommendation = f"Strong buy signal for {brand}. System stable with coherent sentiment."
        elif risk_adjusted_score > 0.4:
            final_signal = "HOLD"
            recommendation = f"Hold position on {brand}. Mixed signals, monitor closely."
        else:
            final_signal = "SELL"
            recommendation = f"Sell signal for {brand}. High instability or anomaly rate detected."

        # Key factors
        key_factors = []
        if echo_signal.chaos_index > 3.5:
            key_factors.append(f"High chaos index ({echo_signal.chaos_index:.2f})")
        if anomaly_rate > 0.15:
            key_factors.append(f"Elevated anomaly rate ({anomaly_rate:.1%})")
        if sentiment_momentum < -0.1:
            key_factors.append(f"Negative sentiment momentum ({sentiment_momentum:.2f})")
        if semantic_coherence < 0.3:
            key_factors.append(f"Low semantic coherence ({semantic_coherence:.2f})")
        if not key_factors:
            key_factors.append("All metrics within normal range")

        return NeuralEnhancedSignal(
            brand=brand,
            signal=final_signal,
            confidence=round(echo_signal.confidence * risk_factor, 2),
            echo_chaos_index=echo_signal.chaos_index,
            echo_mean=echo_signal.echo_mean,
            echo_stability=echo_signal.risk_level,
            semantic_coherence=round(semantic_coherence, 4),
            anomaly_rate=round(anomaly_rate, 4),
            sentiment_momentum=round(sentiment_momentum, 4),
            combined_score=round(combined_score, 4),
            risk_adjusted_score=round(risk_adjusted_score, 4),
            recommendation=recommendation,
            key_factors=key_factors
        )

    # ─────────────────────────────────────────────────────────────
    # REAL-TIME REVIEW PROCESSING
    # ─────────────────────────────────────────────────────────────

    def process_new_review(
        self,
        review_text: str,
        rating: float,
        location_id: str,
        chain_id: Optional[str] = None
    ) -> Dict:
        """
        Process a new review through both Echo and Neural systems.

        Args:
            review_text: Review text content
            rating: Rating value (1-5)
            location_id: Location identifier
            chain_id: Optional chain identifier

        Returns:
            Combined processing result
        """
        # 1. Neural analysis
        neural_result = self.neural_core.analyze_review(
            review_text,
            rating,
            location_id
        )

        # 2. Check if this triggers Echo instability
        # (only if we have chain_id and location is in Echo Engine)
        echo_impact = None
        if chain_id and hasattr(self.echo_engine, '_location_idx_map'):
            loc_key = f"loc_{location_id}"
            if loc_key in self.echo_engine._location_idx_map:
                # Simulate perturbation
                delta = (rating - 3.0) / 2.0  # Convert rating to perturbation
                echo_result = self.echo_engine.compute_echo_by_location_id(
                    loc_key,
                    delta=delta
                )
                echo_impact = {
                    "echo_value": echo_result.echo_value,
                    "stability": echo_result.system_stability.value,
                    "butterfly_coefficient": echo_result.butterfly_coefficient
                }

        return {
            "location_id": location_id,
            "rating": rating,
            "neural_analysis": neural_result,
            "echo_impact": echo_impact,
            "processed_at": datetime.utcnow().isoformat()
        }

    # ─────────────────────────────────────────────────────────────
    # HEALTH & STATUS
    # ─────────────────────────────────────────────────────────────

    def health_check(self) -> Dict:
        """Get bridge health status"""
        return {
            "status": "healthy",
            "echo_engine": {
                "loaded": self._echo_engine is not None,
                "n_locations": self.echo_engine.n if self._echo_engine else 0
            },
            "neural_core": self.neural_core.health_check() if self._neural_core else {"status": "not_loaded"},
            "semantic_cache_size": len(self._semantic_cache),
            "checked_at": datetime.utcnow().isoformat()
        }


# ═══════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════

_bridge_instance: Optional[EchoNeuralBridge] = None


def get_echo_neural_bridge() -> EchoNeuralBridge:
    """Get or create bridge singleton"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = EchoNeuralBridge()
    return _bridge_instance


# ═══════════════════════════════════════════════════════════════════
# CLI / MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  ECHO-NEURAL BRIDGE - Integration Test")
    print("="*70)

    bridge = EchoNeuralBridge()

    # Test review analysis
    print("\n" + "-"*70)
    print("  TEST: Brand Review Analysis")
    print("-"*70)

    test_reviews = [
        {"text": "Amazing food, great service!", "rating": 5.0, "location_id": "loc_1"},
        {"text": "Terrible experience, cold food", "rating": 1.0, "location_id": "loc_2"},
        {"text": "Average meal, nothing special", "rating": 3.0, "location_id": "loc_3"},
        {"text": "Best burger I've ever had!", "rating": 5.0, "location_id": "loc_4"},
        {"text": "Waited 45 minutes for order", "rating": 2.0, "location_id": "loc_5"},
    ]

    analysis = bridge.analyze_brand_reviews("TestBrand", test_reviews)
    print(f"  Brand: {analysis['brand']}")
    print(f"  Reviews: {analysis['total_reviews']}")
    print(f"  Avg Rating: {analysis['avg_rating']}")
    print(f"  Semantic Coherence: {analysis['semantic_coherence']}")
    print(f"  Anomaly Rate: {analysis['anomaly_rate']:.1%}")

    # Test neural-enhanced signal (mock Echo Engine data)
    print("\n" + "-"*70)
    print("  TEST: Neural-Enhanced Signal")
    print("-"*70)

    # Note: Full test requires database connection
    print("  (Full signal generation requires database connection)")

    # Health check
    print("\n" + "-"*70)
    print("  TEST: Health Check")
    print("-"*70)

    health = bridge.health_check()
    print(f"  Status: {health['status']}")
    print(f"  Neural Core: {health['neural_core']['status']}")

    print("\n" + "="*70)
    print("  ECHO-NEURAL BRIDGE TEST COMPLETE")
    print("="*70)
