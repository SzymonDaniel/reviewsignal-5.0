#!/usr/bin/env python3
"""
NEURAL INTEGRATION - Hooks for ReviewSignal Components
Provides integration points for Neural Core with existing modules.

This module connects Neural Core with:
1. Production Scraper - process new reviews as they arrive
2. Echo Engine - enhance with semantic weights
3. ML Anomaly Detector - combine with incremental stats
4. API endpoints - unified intelligence layer

Author: ReviewSignal Team
Version: 5.1.0
Date: February 2026
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime
from functools import wraps
import structlog

logger = structlog.get_logger()

# Lazy import Neural Core
_neural_core = None


def get_neural_core():
    """Get Neural Core singleton"""
    global _neural_core
    if _neural_core is None:
        try:
            from modules.neural_core import get_neural_core as _get_core
            _neural_core = _get_core()
        except Exception as e:
            logger.warning("neural_core_not_available", error=str(e))
            return None
    return _neural_core


# ═══════════════════════════════════════════════════════════════════
# DECORATOR FOR NEURAL PROCESSING
# ═══════════════════════════════════════════════════════════════════

def neural_process_review(func: Callable) -> Callable:
    """
    Decorator to automatically process reviews through Neural Core.
    Use on functions that save reviews to database.

    Example:
        @neural_process_review
        def save_review(review_data):
            # ... save to database ...
            return review_data
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Execute original function
        result = func(*args, **kwargs)

        # Process through Neural Core if available
        core = get_neural_core()
        if core is None:
            return result

        try:
            # Extract review data from result or kwargs
            review_text = None
            rating = None
            location_id = None

            if isinstance(result, dict):
                review_text = result.get("text") or result.get("review_text")
                rating = result.get("rating")
                location_id = result.get("location_id")
            elif kwargs:
                review_text = kwargs.get("text") or kwargs.get("review_text")
                rating = kwargs.get("rating")
                location_id = kwargs.get("location_id")

            if review_text and rating and location_id:
                # Update stats
                core.update_stats(str(location_id), float(rating), "location")

                # Check anomaly
                anomaly = core.check_anomaly(str(location_id), float(rating))

                if anomaly.is_anomaly:
                    logger.info(
                        "neural_anomaly_detected",
                        location_id=location_id,
                        rating=rating,
                        score=anomaly.anomaly_score
                    )

        except Exception as e:
            logger.debug("neural_processing_failed", error=str(e))

        return result

    return wrapper


# ═══════════════════════════════════════════════════════════════════
# REVIEW PROCESSOR
# ═══════════════════════════════════════════════════════════════════

class NeuralReviewProcessor:
    """
    Processes reviews through Neural Core.
    Can be used as standalone or integrated with existing scrapers.
    """

    def __init__(self):
        self._core = None
        self._processed_count = 0
        self._anomaly_count = 0

    @property
    def core(self):
        if self._core is None:
            self._core = get_neural_core()
        return self._core

    def process_review(
        self,
        review_text: str,
        rating: float,
        location_id: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Process a single review through Neural Core.

        Args:
            review_text: Review text content
            rating: Rating value (1-5)
            location_id: Location identifier
            metadata: Optional additional metadata

        Returns:
            Processing result with stats and anomaly info
        """
        if self.core is None:
            return {"status": "neural_core_unavailable"}

        result = self.core.analyze_review(review_text, rating, location_id)
        self._processed_count += 1

        if result.get("anomaly", {}).get("is_anomaly"):
            self._anomaly_count += 1

        return result

    def process_batch(
        self,
        reviews: List[Dict],
        text_key: str = "text",
        rating_key: str = "rating",
        location_key: str = "location_id"
    ) -> Dict:
        """
        Process multiple reviews efficiently.

        Args:
            reviews: List of review dicts
            text_key: Key for text in review dict
            rating_key: Key for rating in review dict
            location_key: Key for location_id in review dict

        Returns:
            Batch processing result
        """
        if self.core is None:
            return {"status": "neural_core_unavailable", "processed": 0}

        results = []
        anomalies = []

        for review in reviews:
            text = review.get(text_key, "")
            rating = review.get(rating_key)
            location_id = review.get(location_key)

            if not text or rating is None or not location_id:
                continue

            result = self.process_review(text, float(rating), str(location_id))
            results.append(result)

            if result.get("anomaly", {}).get("is_anomaly"):
                anomalies.append({
                    "location_id": location_id,
                    "rating": rating,
                    "anomaly_score": result["anomaly"]["anomaly_score"]
                })

        return {
            "status": "success",
            "processed": len(results),
            "anomalies_found": len(anomalies),
            "anomaly_rate": len(anomalies) / len(results) if results else 0,
            "top_anomalies": sorted(anomalies, key=lambda x: x["anomaly_score"], reverse=True)[:10]
        }

    def get_stats(self) -> Dict:
        """Get processor statistics"""
        return {
            "processed_count": self._processed_count,
            "anomaly_count": self._anomaly_count,
            "anomaly_rate": self._anomaly_count / self._processed_count if self._processed_count > 0 else 0,
            "core_available": self.core is not None
        }


# ═══════════════════════════════════════════════════════════════════
# SCRAPER HOOK
# ═══════════════════════════════════════════════════════════════════

def create_scraper_hook() -> Callable:
    """
    Create a hook function for production scraper.

    Usage in production_scraper.py:
        from modules.neural_integration import create_scraper_hook
        neural_hook = create_scraper_hook()

        # After saving review:
        neural_hook(review_data)

    Returns:
        Hook function
    """
    processor = NeuralReviewProcessor()

    def hook(review_data: Dict) -> Dict:
        """Process review through Neural Core"""
        text = review_data.get("text") or review_data.get("review_text", "")
        rating = review_data.get("rating")
        location_id = review_data.get("location_id")

        if text and rating is not None and location_id:
            return processor.process_review(text, float(rating), str(location_id))

        return {"status": "skipped", "reason": "missing_data"}

    return hook


# ═══════════════════════════════════════════════════════════════════
# ANOMALY DETECTOR INTEGRATION
# ═══════════════════════════════════════════════════════════════════

class NeuralAnomalyIntegration:
    """
    Integrates Neural Core with existing ML Anomaly Detector.
    Provides combined anomaly detection using both systems.
    """

    def __init__(self):
        self._ml_detector = None
        self._neural_core = None

    @property
    def ml_detector(self):
        if self._ml_detector is None:
            from modules.ml_anomaly_detector import MLAnomalyDetector
            self._ml_detector = MLAnomalyDetector()
        return self._ml_detector

    @property
    def neural_core(self):
        if self._neural_core is None:
            self._neural_core = get_neural_core()
        return self._neural_core

    def combined_detection(
        self,
        entity_id: str,
        values: List[float],
        current_value: float
    ) -> Dict:
        """
        Combine ML Anomaly Detector with Neural Core incremental stats.

        Args:
            entity_id: Entity identifier
            values: Historical values for ML detector
            current_value: Current value to check

        Returns:
            Combined detection result
        """
        results = {
            "entity_id": entity_id,
            "current_value": current_value,
            "ml_detector": None,
            "neural_core": None,
            "combined_verdict": None
        }

        # ML Anomaly Detector
        try:
            ml_result = self.ml_detector.analyze(values, chain_name=entity_id)
            ml_anomalies = [a for a in ml_result.anomalies if a.index == len(values) - 1]
            results["ml_detector"] = {
                "is_anomaly": len(ml_anomalies) > 0,
                "anomaly_count": ml_result.anomalies_found,
                "trend": ml_result.trend_direction
            }
        except Exception as e:
            results["ml_detector"] = {"error": str(e)}

        # Neural Core
        if self.neural_core:
            try:
                # Update stats with historical data
                for val in values:
                    self.neural_core.update_stats(entity_id, val)

                # Check current value
                neural_pred = self.neural_core.check_anomaly(entity_id, current_value)
                results["neural_core"] = {
                    "is_anomaly": neural_pred.is_anomaly,
                    "anomaly_score": neural_pred.anomaly_score,
                    "deviation_sigma": neural_pred.deviation_sigma,
                    "trend": neural_pred.context.get("trend")
                }
            except Exception as e:
                results["neural_core"] = {"error": str(e)}
        else:
            results["neural_core"] = {"error": "not_available"}

        # Combined verdict (both agree = high confidence)
        ml_anomaly = results["ml_detector"].get("is_anomaly", False) if isinstance(results["ml_detector"], dict) else False
        neural_anomaly = results["neural_core"].get("is_anomaly", False) if isinstance(results["neural_core"], dict) else False

        if ml_anomaly and neural_anomaly:
            results["combined_verdict"] = {"is_anomaly": True, "confidence": "high", "reason": "both_agree"}
        elif ml_anomaly or neural_anomaly:
            results["combined_verdict"] = {"is_anomaly": True, "confidence": "medium", "reason": "one_detector"}
        else:
            results["combined_verdict"] = {"is_anomaly": False, "confidence": "high", "reason": "both_normal"}

        return results


# ═══════════════════════════════════════════════════════════════════
# ECHO ENGINE INTEGRATION
# ═══════════════════════════════════════════════════════════════════

def enhance_echo_signal_with_neural(
    echo_signal: Any,
    reviews: List[Dict],
    brand: str
) -> Dict:
    """
    Enhance Echo Engine signal with Neural Core analysis.

    Args:
        echo_signal: TradingSignal from Echo Engine
        reviews: List of recent reviews for the brand
        brand: Brand name

    Returns:
        Enhanced signal dict
    """
    core = get_neural_core()
    if core is None:
        return {
            "echo_signal": echo_signal.to_dict() if hasattr(echo_signal, 'to_dict') else str(echo_signal),
            "neural_enhancement": None,
            "status": "neural_core_unavailable"
        }

    # Analyze reviews
    from modules.echo_neural_bridge import EchoNeuralBridge
    bridge = EchoNeuralBridge()
    neural_analysis = bridge.analyze_brand_reviews(brand, reviews)

    # Combine signals
    echo_dict = echo_signal.to_dict() if hasattr(echo_signal, 'to_dict') else {}

    # Adjust confidence based on neural analysis
    base_confidence = echo_dict.get("confidence", 0.5)
    semantic_factor = neural_analysis.get("semantic_coherence", 0.5)
    anomaly_factor = 1 - neural_analysis.get("anomaly_rate", 0)

    adjusted_confidence = base_confidence * semantic_factor * anomaly_factor

    return {
        "brand": brand,
        "echo_signal": echo_dict,
        "neural_analysis": neural_analysis,
        "adjusted_confidence": round(adjusted_confidence, 4),
        "combined_recommendation": _generate_combined_recommendation(echo_dict, neural_analysis),
        "generated_at": datetime.utcnow().isoformat()
    }


def _generate_combined_recommendation(echo: Dict, neural: Dict) -> str:
    """Generate combined recommendation from both systems"""
    echo_signal = echo.get("signal", "hold")
    chaos_index = echo.get("chaos_index", 2.0)
    anomaly_rate = neural.get("anomaly_rate", 0)
    momentum = neural.get("sentiment_momentum", 0)

    factors = []

    if chaos_index > 3.5:
        factors.append("high system instability")
    if anomaly_rate > 0.15:
        factors.append("elevated anomaly rate")
    if momentum < -0.1:
        factors.append("negative sentiment trend")

    if not factors:
        factors.append("stable metrics")

    if echo_signal == "sell" or (chaos_index > 3.5 and anomaly_rate > 0.15):
        return f"CAUTION: {', '.join(factors)}. Consider reducing exposure."
    elif echo_signal == "buy" and anomaly_rate < 0.05 and momentum >= 0:
        return f"POSITIVE: {', '.join(factors)}. System shows resilience."
    else:
        return f"MONITOR: {', '.join(factors)}. Maintain current position."


# ═══════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def quick_embed(text: str) -> Optional[np.ndarray]:
    """Quick embedding for single text"""
    core = get_neural_core()
    if core:
        return core.embed(text)
    return None


def quick_similarity(text1: str, text2: str) -> float:
    """Quick similarity between two texts"""
    core = get_neural_core()
    if core:
        return core.similarity(text1, text2)
    return 0.0


def quick_anomaly_check(entity_id: str, value: float) -> bool:
    """Quick anomaly check"""
    core = get_neural_core()
    if core:
        result = core.check_anomaly(entity_id, value)
        return result.is_anomaly
    return False


# ═══════════════════════════════════════════════════════════════════
# MAIN / TEST
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  NEURAL INTEGRATION - Test Suite")
    print("="*60)

    # Test processor
    print("\n" + "-"*60)
    print("  TEST: Review Processor")
    print("-"*60)

    processor = NeuralReviewProcessor()
    result = processor.process_review(
        "Great food but slow service",
        3.5,
        "test_loc_001"
    )
    print(f"  Processed: {result.get('analyzed_at', 'N/A')}")
    print(f"  Anomaly: {result.get('anomaly', {}).get('is_anomaly', 'N/A')}")

    # Test batch
    print("\n" + "-"*60)
    print("  TEST: Batch Processing")
    print("-"*60)

    test_reviews = [
        {"text": "Amazing!", "rating": 5.0, "location_id": "loc_1"},
        {"text": "Terrible", "rating": 1.0, "location_id": "loc_2"},
        {"text": "Average", "rating": 3.0, "location_id": "loc_3"},
    ]

    batch_result = processor.process_batch(test_reviews)
    print(f"  Processed: {batch_result.get('processed', 0)}")
    print(f"  Anomalies: {batch_result.get('anomalies_found', 0)}")

    # Test quick functions
    print("\n" + "-"*60)
    print("  TEST: Quick Functions")
    print("-"*60)

    sim = quick_similarity("Great food", "Delicious meal")
    print(f"  Similarity: {sim:.4f}")

    print("\n" + "="*60)
    print("  NEURAL INTEGRATION TESTS COMPLETE")
    print("="*60)
