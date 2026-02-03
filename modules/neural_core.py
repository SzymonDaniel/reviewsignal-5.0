#!/usr/bin/env python3
"""
NEURAL CORE - Unified Intelligence Layer for ReviewSignal
System 5.1.0 - MiniLM Embeddings + Incremental Statistics + Adaptive Learning

This module serves as the central "brain" connecting all ReviewSignal components:
- Semantic embeddings via MiniLM (sentence-transformers)
- Incremental statistics with sliding windows
- Adaptive Isolation Forest with weekly refit
- Unified Redis cache layer

Author: ReviewSignal Team
Version: 5.1.0
Date: February 2026

Zero additional infrastructure cost - runs on CPU, uses existing Redis.
"""

import os
import json
import pickle
import hashlib
import numpy as np
from collections import deque
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
import time
import structlog

# Lazy imports for heavy dependencies
_sentence_transformer = None
_isolation_forest = None
_redis_client = None

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

@dataclass
class NeuralCoreConfig:
    """Configuration for Neural Core"""
    # MiniLM settings
    embedding_model: str = "all-MiniLM-L6-v2"  # 80MB, 384 dimensions
    embedding_dim: int = 384
    embedding_batch_size: int = 32

    # Incremental statistics
    stats_window_days: int = 30
    stats_min_samples: int = 10
    anomaly_threshold_sigma: float = 2.5

    # Isolation Forest
    iso_contamination: float = 0.1
    iso_n_estimators: int = 100
    iso_refit_interval_days: int = 7
    iso_min_samples_for_refit: int = 100

    # Redis cache
    redis_url: str = "redis://localhost:6379/0"
    cache_embedding_ttl: int = 86400 * 30  # 30 days
    cache_stats_ttl: int = 86400 * 7       # 7 days
    cache_prediction_ttl: int = 86400      # 1 day

    # Performance
    max_cache_size_mb: int = 500
    lazy_load: bool = True

    def to_dict(self) -> Dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class EmbeddingResult:
    """Result of embedding computation"""
    text: str
    embedding: np.ndarray
    model: str
    computed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    from_cache: bool = False

    def to_dict(self) -> Dict:
        return {
            "text_hash": hashlib.md5(self.text.encode()).hexdigest()[:16],
            "embedding_shape": self.embedding.shape,
            "model": self.model,
            "computed_at": self.computed_at,
            "from_cache": self.from_cache
        }


@dataclass
class IncrementalStats:
    """Incremental statistics for a location/chain"""
    entity_id: str
    entity_type: str  # "location" or "chain"

    # Core stats
    count: int = 0
    mean: float = 0.0
    variance: float = 0.0
    min_value: float = float('inf')
    max_value: float = float('-inf')

    # Momentum indicators
    momentum_7d: float = 0.0
    momentum_30d: float = 0.0
    trend_direction: str = "stable"

    # Anomaly detection
    baseline_mean: float = 0.0
    baseline_std: float = 0.0
    last_anomaly_at: Optional[str] = None
    anomaly_count_7d: int = 0

    # Metadata
    first_seen: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def std(self) -> float:
        return np.sqrt(self.variance) if self.variance > 0 else 0.0

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['std'] = self.std
        return data


@dataclass
class SimilarityResult:
    """Result of semantic similarity search"""
    query: str
    matches: List[Dict]  # [{text, score, metadata}]
    total_candidates: int
    search_time_ms: float

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AnomalyPrediction:
    """Real-time anomaly prediction"""
    entity_id: str
    value: float
    is_anomaly: bool
    anomaly_score: float  # 0-1, higher = more anomalous
    deviation_sigma: float
    context: Dict = field(default_factory=dict)
    predicted_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════
# LAZY LOADERS
# ═══════════════════════════════════════════════════════════════════

def get_sentence_transformer(model_name: str = "all-MiniLM-L6-v2"):
    """Lazy load sentence transformer model"""
    global _sentence_transformer
    if _sentence_transformer is None:
        logger.info("loading_sentence_transformer", model=model_name)
        from sentence_transformers import SentenceTransformer
        _sentence_transformer = SentenceTransformer(model_name)
        logger.info("sentence_transformer_loaded", model=model_name)
    return _sentence_transformer


def get_redis_client(redis_url: str = "redis://localhost:6379/0"):
    """Lazy load Redis client"""
    global _redis_client
    if _redis_client is None:
        logger.info("connecting_redis", url=redis_url)
        import redis
        _redis_client = redis.from_url(redis_url, decode_responses=False)
        _redis_client.ping()
        logger.info("redis_connected")
    return _redis_client


# ═══════════════════════════════════════════════════════════════════
# UNIFIED CACHE LAYER
# ═══════════════════════════════════════════════════════════════════

class UnifiedCache:
    """
    Unified Redis cache for all Neural Core operations.
    Handles embeddings, statistics, predictions with appropriate TTLs.
    """

    # Cache key prefixes
    PREFIX_EMBEDDING = "nc:emb:"
    PREFIX_STATS = "nc:stats:"
    PREFIX_PREDICTION = "nc:pred:"
    PREFIX_MODEL = "nc:model:"
    PREFIX_SIMILARITY = "nc:sim:"

    def __init__(self, config: NeuralCoreConfig):
        self.config = config
        self._client = None
        self._local_cache = {}  # In-memory fallback
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "errors": 0
        }

    @property
    def client(self):
        if self._client is None:
            try:
                self._client = get_redis_client(self.config.redis_url)
            except Exception as e:
                logger.warning("redis_connection_failed", error=str(e))
                self._client = None
        return self._client

    def _make_key(self, prefix: str, identifier: str) -> str:
        """Create cache key with prefix"""
        return f"{prefix}{identifier}"

    def _hash_text(self, text: str) -> str:
        """Create hash for text content"""
        return hashlib.sha256(text.encode()).hexdigest()[:32]

    # ─────────────────────────────────────────────────────────────
    # EMBEDDING CACHE
    # ─────────────────────────────────────────────────────────────

    def get_embedding(self, text: str) -> Optional[np.ndarray]:
        """Get cached embedding for text"""
        key = self._make_key(self.PREFIX_EMBEDDING, self._hash_text(text))

        try:
            if self.client:
                data = self.client.get(key)
                if data:
                    self._stats["hits"] += 1
                    return pickle.loads(data)
            elif key in self._local_cache:
                self._stats["hits"] += 1
                return self._local_cache[key]
        except Exception as e:
            self._stats["errors"] += 1
            logger.debug("cache_get_error", key=key[:20], error=str(e))

        self._stats["misses"] += 1
        return None

    def set_embedding(self, text: str, embedding: np.ndarray) -> bool:
        """Cache embedding for text"""
        key = self._make_key(self.PREFIX_EMBEDDING, self._hash_text(text))

        try:
            data = pickle.dumps(embedding)
            if self.client:
                self.client.setex(key, self.config.cache_embedding_ttl, data)
            else:
                self._local_cache[key] = embedding
            self._stats["sets"] += 1
            return True
        except Exception as e:
            self._stats["errors"] += 1
            logger.debug("cache_set_error", key=key[:20], error=str(e))
            return False

    def get_embeddings_batch(self, texts: List[str]) -> Dict[str, Optional[np.ndarray]]:
        """Get multiple embeddings at once"""
        results = {}
        keys = [self._make_key(self.PREFIX_EMBEDDING, self._hash_text(t)) for t in texts]

        try:
            if self.client:
                values = self.client.mget(keys)
                for text, value in zip(texts, values):
                    if value:
                        results[text] = pickle.loads(value)
                        self._stats["hits"] += 1
                    else:
                        results[text] = None
                        self._stats["misses"] += 1
            else:
                for text, key in zip(texts, keys):
                    results[text] = self._local_cache.get(key)
        except Exception as e:
            self._stats["errors"] += 1
            for text in texts:
                results[text] = None

        return results

    # ─────────────────────────────────────────────────────────────
    # STATISTICS CACHE
    # ─────────────────────────────────────────────────────────────

    def get_stats(self, entity_id: str) -> Optional[IncrementalStats]:
        """Get cached statistics for entity"""
        key = self._make_key(self.PREFIX_STATS, entity_id)

        try:
            if self.client:
                data = self.client.get(key)
                if data:
                    self._stats["hits"] += 1
                    stats_dict = json.loads(data)
                    return IncrementalStats(**stats_dict)
        except Exception as e:
            self._stats["errors"] += 1

        self._stats["misses"] += 1
        return None

    def set_stats(self, stats: IncrementalStats) -> bool:
        """Cache statistics"""
        key = self._make_key(self.PREFIX_STATS, stats.entity_id)

        try:
            data = json.dumps(stats.to_dict())
            if self.client:
                self.client.setex(key, self.config.cache_stats_ttl, data)
                self._stats["sets"] += 1
                return True
        except Exception as e:
            self._stats["errors"] += 1
        return False

    # ─────────────────────────────────────────────────────────────
    # MODEL CACHE
    # ─────────────────────────────────────────────────────────────

    def get_model(self, model_id: str) -> Optional[Any]:
        """Get cached ML model"""
        key = self._make_key(self.PREFIX_MODEL, model_id)

        try:
            if self.client:
                data = self.client.get(key)
                if data:
                    return pickle.loads(data)
        except Exception as e:
            self._stats["errors"] += 1
        return None

    def set_model(self, model_id: str, model: Any, ttl: int = 86400 * 7) -> bool:
        """Cache ML model"""
        key = self._make_key(self.PREFIX_MODEL, model_id)

        try:
            data = pickle.dumps(model)
            if self.client:
                self.client.setex(key, ttl, data)
                return True
        except Exception as e:
            self._stats["errors"] += 1
        return False

    # ─────────────────────────────────────────────────────────────
    # UTILITY
    # ─────────────────────────────────────────────────────────────

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0

        return {
            **self._stats,
            "total_requests": total,
            "hit_rate": round(hit_rate, 4)
        }

    def clear_prefix(self, prefix: str) -> int:
        """Clear all keys with given prefix"""
        if not self.client:
            return 0

        try:
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = self.client.scan(cursor, match=f"{prefix}*", count=100)
                if keys:
                    deleted += self.client.delete(*keys)
                if cursor == 0:
                    break
            return deleted
        except Exception as e:
            logger.error("cache_clear_error", prefix=prefix, error=str(e))
            return 0


# ═══════════════════════════════════════════════════════════════════
# EMBEDDING ENGINE
# ═══════════════════════════════════════════════════════════════════

class EmbeddingEngine:
    """
    MiniLM-based semantic embedding engine.
    Lightweight (80MB), CPU-friendly, 384-dimensional vectors.
    """

    def __init__(self, config: NeuralCoreConfig, cache: UnifiedCache):
        self.config = config
        self.cache = cache
        self._model = None
        self._lock = threading.Lock()

    @property
    def model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    self._model = get_sentence_transformer(self.config.embedding_model)
        return self._model

    def embed(self, text: str, use_cache: bool = True) -> EmbeddingResult:
        """
        Generate embedding for single text.

        Args:
            text: Text to embed
            use_cache: Whether to use cache

        Returns:
            EmbeddingResult with embedding vector
        """
        # Check cache first
        if use_cache:
            cached = self.cache.get_embedding(text)
            if cached is not None:
                return EmbeddingResult(
                    text=text,
                    embedding=cached,
                    model=self.config.embedding_model,
                    from_cache=True
                )

        # Compute embedding
        embedding = self.model.encode(text, convert_to_numpy=True)

        # Cache result
        if use_cache:
            self.cache.set_embedding(text, embedding)

        return EmbeddingResult(
            text=text,
            embedding=embedding,
            model=self.config.embedding_model,
            from_cache=False
        )

    def embed_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
        show_progress: bool = False
    ) -> List[EmbeddingResult]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed
            use_cache: Whether to use cache
            show_progress: Show progress bar

        Returns:
            List of EmbeddingResult objects
        """
        results = []
        texts_to_compute = []
        text_indices = []

        # Check cache for all texts
        if use_cache:
            cached = self.cache.get_embeddings_batch(texts)
            for i, text in enumerate(texts):
                if cached.get(text) is not None:
                    results.append(EmbeddingResult(
                        text=text,
                        embedding=cached[text],
                        model=self.config.embedding_model,
                        from_cache=True
                    ))
                else:
                    texts_to_compute.append(text)
                    text_indices.append(i)
        else:
            texts_to_compute = texts
            text_indices = list(range(len(texts)))

        # Compute missing embeddings in batches
        if texts_to_compute:
            embeddings = self.model.encode(
                texts_to_compute,
                batch_size=self.config.embedding_batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True
            )

            for text, embedding in zip(texts_to_compute, embeddings):
                if use_cache:
                    self.cache.set_embedding(text, embedding)
                results.append(EmbeddingResult(
                    text=text,
                    embedding=embedding,
                    model=self.config.embedding_model,
                    from_cache=False
                ))

        return results

    def similarity(
        self,
        text1: str,
        text2: str
    ) -> float:
        """
        Calculate cosine similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0-1)
        """
        emb1 = self.embed(text1).embedding
        emb2 = self.embed(text2).embedding

        # Cosine similarity
        return float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))

    def find_similar(
        self,
        query: str,
        candidates: List[str],
        top_k: int = 5,
        threshold: float = 0.5
    ) -> SimilarityResult:
        """
        Find most similar texts from candidates.

        Args:
            query: Query text
            candidates: List of candidate texts
            top_k: Number of top matches to return
            threshold: Minimum similarity threshold

        Returns:
            SimilarityResult with matches
        """
        start_time = time.time()

        # Get embeddings
        query_emb = self.embed(query).embedding
        candidate_results = self.embed_batch(candidates)
        candidate_embs = np.array([r.embedding for r in candidate_results])

        # Calculate similarities
        similarities = np.dot(candidate_embs, query_emb) / (
            np.linalg.norm(candidate_embs, axis=1) * np.linalg.norm(query_emb)
        )

        # Get top matches
        sorted_indices = np.argsort(similarities)[::-1]
        matches = []

        for idx in sorted_indices[:top_k]:
            score = float(similarities[idx])
            if score >= threshold:
                matches.append({
                    "text": candidates[idx],
                    "score": round(score, 4),
                    "rank": len(matches) + 1
                })

        return SimilarityResult(
            query=query,
            matches=matches,
            total_candidates=len(candidates),
            search_time_ms=round((time.time() - start_time) * 1000, 2)
        )


# ═══════════════════════════════════════════════════════════════════
# INCREMENTAL STATISTICS ENGINE
# ═══════════════════════════════════════════════════════════════════

class IncrementalStatsEngine:
    """
    Welford's online algorithm for incremental mean/variance.
    Maintains sliding window statistics without storing all data.
    """

    def __init__(self, config: NeuralCoreConfig, cache: UnifiedCache):
        self.config = config
        self.cache = cache
        self._windows: Dict[str, deque] = {}  # entity_id -> deque of (timestamp, value)
        self._stats: Dict[str, IncrementalStats] = {}

    def _get_or_create_stats(self, entity_id: str, entity_type: str) -> IncrementalStats:
        """Get existing stats or create new"""
        if entity_id not in self._stats:
            # Try cache
            cached = self.cache.get_stats(entity_id)
            if cached:
                self._stats[entity_id] = cached
            else:
                self._stats[entity_id] = IncrementalStats(
                    entity_id=entity_id,
                    entity_type=entity_type
                )
        return self._stats[entity_id]

    def _get_window(self, entity_id: str) -> deque:
        """Get or create sliding window for entity"""
        if entity_id not in self._windows:
            max_samples = self.config.stats_window_days * 100  # ~100 samples/day
            self._windows[entity_id] = deque(maxlen=max_samples)
        return self._windows[entity_id]

    def update(
        self,
        entity_id: str,
        value: float,
        entity_type: str = "location",
        timestamp: Optional[datetime] = None
    ) -> IncrementalStats:
        """
        Update statistics with new value using Welford's algorithm.

        Args:
            entity_id: Entity identifier
            value: New value to incorporate
            entity_type: Type of entity
            timestamp: Timestamp for value (default: now)

        Returns:
            Updated IncrementalStats
        """
        timestamp = timestamp or datetime.utcnow()
        stats = self._get_or_create_stats(entity_id, entity_type)
        window = self._get_window(entity_id)

        # Add to sliding window
        window.append((timestamp.isoformat(), value))

        # Welford's online algorithm for mean and variance
        stats.count += 1
        delta = value - stats.mean
        stats.mean += delta / stats.count
        delta2 = value - stats.mean
        stats.variance += (delta * delta2 - stats.variance) / stats.count

        # Update min/max
        stats.min_value = min(stats.min_value, value)
        stats.max_value = max(stats.max_value, value)

        # Update baseline (use first 100 samples or recalculate periodically)
        if stats.count <= 100:
            stats.baseline_mean = stats.mean
            stats.baseline_std = stats.std

        # Calculate momentum
        stats.momentum_7d = self._calculate_momentum(window, days=7)
        stats.momentum_30d = self._calculate_momentum(window, days=30)

        # Determine trend
        if stats.momentum_7d > 0.05:
            stats.trend_direction = "up"
        elif stats.momentum_7d < -0.05:
            stats.trend_direction = "down"
        else:
            stats.trend_direction = "stable"

        stats.last_updated = datetime.utcnow().isoformat()

        # Cache updated stats
        self.cache.set_stats(stats)

        return stats

    def _calculate_momentum(self, window: deque, days: int) -> float:
        """Calculate momentum over specified days"""
        if len(window) < 2:
            return 0.0

        cutoff = datetime.utcnow() - timedelta(days=days)
        recent_values = [v for ts, v in window if datetime.fromisoformat(ts) > cutoff]

        if len(recent_values) < 2:
            return 0.0

        # Simple momentum: (recent_avg - older_avg) / older_avg
        mid = len(recent_values) // 2
        recent_avg = np.mean(recent_values[mid:])
        older_avg = np.mean(recent_values[:mid])

        if older_avg == 0:
            return 0.0

        return (recent_avg - older_avg) / abs(older_avg)

    def get_stats(self, entity_id: str) -> Optional[IncrementalStats]:
        """Get current statistics for entity"""
        if entity_id in self._stats:
            return self._stats[entity_id]
        return self.cache.get_stats(entity_id)

    def is_anomaly(
        self,
        entity_id: str,
        value: float,
        threshold_sigma: Optional[float] = None
    ) -> AnomalyPrediction:
        """
        Check if value is anomalous based on incremental statistics.

        Args:
            entity_id: Entity identifier
            value: Value to check
            threshold_sigma: Standard deviations for anomaly (default from config)

        Returns:
            AnomalyPrediction with result
        """
        threshold = threshold_sigma or self.config.anomaly_threshold_sigma
        stats = self.get_stats(entity_id)

        if stats is None or stats.count < self.config.stats_min_samples:
            return AnomalyPrediction(
                entity_id=entity_id,
                value=value,
                is_anomaly=False,
                anomaly_score=0.0,
                deviation_sigma=0.0,
                context={"reason": "insufficient_data", "samples": stats.count if stats else 0}
            )

        # Calculate deviation in standard deviations
        if stats.baseline_std == 0:
            deviation_sigma = 0.0
        else:
            deviation_sigma = abs(value - stats.baseline_mean) / stats.baseline_std

        # Anomaly score (0-1, using sigmoid-like transformation)
        anomaly_score = min(1.0, deviation_sigma / (threshold * 2))

        is_anomaly = deviation_sigma > threshold

        # Update anomaly tracking
        if is_anomaly:
            stats.last_anomaly_at = datetime.utcnow().isoformat()
            stats.anomaly_count_7d += 1
            self.cache.set_stats(stats)

        return AnomalyPrediction(
            entity_id=entity_id,
            value=value,
            is_anomaly=is_anomaly,
            anomaly_score=round(anomaly_score, 4),
            deviation_sigma=round(deviation_sigma, 4),
            context={
                "baseline_mean": round(stats.baseline_mean, 4),
                "baseline_std": round(stats.baseline_std, 4),
                "threshold_sigma": threshold,
                "trend": stats.trend_direction,
                "momentum_7d": round(stats.momentum_7d, 4)
            }
        )

    def get_all_stats(self) -> List[IncrementalStats]:
        """Get all tracked statistics"""
        return list(self._stats.values())


# ═══════════════════════════════════════════════════════════════════
# ADAPTIVE ISOLATION FOREST
# ═══════════════════════════════════════════════════════════════════

class AdaptiveIsolationForest:
    """
    Isolation Forest with automatic weekly refit.
    Adapts to changing data patterns without manual intervention.
    """

    def __init__(self, config: NeuralCoreConfig, cache: UnifiedCache):
        self.config = config
        self.cache = cache
        self._model = None
        self._scaler = None
        self._training_data: deque = deque(maxlen=10000)
        self._last_refit: Optional[datetime] = None
        self._refit_count: int = 0
        self._lock = threading.Lock()

        # Try to load cached model from Redis on startup
        self._load_cached_model()

    def _load_cached_model(self) -> bool:
        """
        Load model from Redis cache if available.
        Returns True if model was loaded successfully.
        """
        try:
            model_data = self.cache.get_model("isolation_forest_latest")
            if model_data and isinstance(model_data, dict):
                self._model = model_data.get("model")
                self._scaler = model_data.get("scaler")
                refit_at = model_data.get("refit_at")
                if refit_at:
                    self._last_refit = datetime.fromisoformat(refit_at)
                n_samples = model_data.get("n_samples", 0)

                logger.info(
                    "isolation_forest_loaded_from_cache",
                    last_refit=refit_at,
                    n_samples=n_samples
                )
                return True
        except Exception as e:
            logger.warning("isolation_forest_cache_load_failed", error=str(e))
        return False

    def reload_from_cache(self) -> Dict:
        """
        Explicitly reload model from Redis cache.
        Call this after external refit (e.g., cron job).
        """
        with self._lock:
            if self._load_cached_model():
                return {
                    "status": "success",
                    "has_model": self._model is not None,
                    "last_refit": self._last_refit.isoformat() if self._last_refit else None
                }
            return {"status": "failed", "reason": "no_cached_model"}

    def _needs_refit(self) -> bool:
        """Check if model needs refit"""
        if self._model is None:
            return True

        if self._last_refit is None:
            return True

        days_since_refit = (datetime.utcnow() - self._last_refit).days
        return days_since_refit >= self.config.iso_refit_interval_days

    def add_sample(self, features: np.ndarray) -> None:
        """
        Add sample to training buffer for next refit.

        Args:
            features: Feature vector (1D or 2D array)
        """
        if len(features.shape) == 1:
            features = features.reshape(1, -1)

        for row in features:
            self._training_data.append(row)

    def refit(self, force: bool = False) -> Dict:
        """
        Refit model on accumulated data.

        Args:
            force: Force refit even if not scheduled

        Returns:
            Refit statistics
        """
        if not force and not self._needs_refit():
            return {"status": "skipped", "reason": "not_scheduled"}

        if len(self._training_data) < self.config.iso_min_samples_for_refit:
            return {
                "status": "skipped",
                "reason": "insufficient_samples",
                "samples": len(self._training_data),
                "required": self.config.iso_min_samples_for_refit
            }

        with self._lock:
            from sklearn.ensemble import IsolationForest
            from sklearn.preprocessing import StandardScaler

            # Prepare data
            X = np.array(list(self._training_data))

            # Fit scaler
            self._scaler = StandardScaler()
            X_scaled = self._scaler.fit_transform(X)

            # Fit model
            self._model = IsolationForest(
                contamination=self.config.iso_contamination,
                n_estimators=self.config.iso_n_estimators,
                random_state=42,
                n_jobs=-1
            )
            self._model.fit(X_scaled)

            self._last_refit = datetime.utcnow()
            self._refit_count += 1

            # Cache model
            model_data = {
                "model": self._model,
                "scaler": self._scaler,
                "refit_at": self._last_refit.isoformat(),
                "n_samples": len(X)
            }
            self.cache.set_model("isolation_forest_latest", model_data)

            logger.info(
                "isolation_forest_refit",
                samples=len(X),
                refit_count=self._refit_count
            )

            return {
                "status": "success",
                "samples": len(X),
                "refit_at": self._last_refit.isoformat(),
                "refit_count": self._refit_count
            }

    def predict(self, features: np.ndarray) -> Tuple[bool, float]:
        """
        Predict if sample is anomalous.

        Args:
            features: Feature vector

        Returns:
            Tuple of (is_anomaly, anomaly_score)
        """
        # Auto-refit if needed
        if self._needs_refit():
            self.refit()

        if self._model is None or self._scaler is None:
            return False, 0.0

        # Reshape if needed
        if len(features.shape) == 1:
            features = features.reshape(1, -1)

        # Scale and predict
        features_scaled = self._scaler.transform(features)

        # Get prediction (-1 = anomaly, 1 = normal)
        prediction = self._model.predict(features_scaled)[0]

        # Get anomaly score (lower = more anomalous)
        raw_score = self._model.decision_function(features_scaled)[0]

        # Normalize score to 0-1 (higher = more anomalous)
        anomaly_score = max(0, min(1, 0.5 - raw_score))

        return prediction == -1, float(anomaly_score)

    def get_model_info(self) -> Dict:
        """Get model information"""
        return {
            "has_model": self._model is not None,
            "training_samples": len(self._training_data),
            "last_refit": self._last_refit.isoformat() if self._last_refit else None,
            "refit_count": self._refit_count,
            "needs_refit": self._needs_refit(),
            "config": {
                "contamination": self.config.iso_contamination,
                "n_estimators": self.config.iso_n_estimators,
                "refit_interval_days": self.config.iso_refit_interval_days
            }
        }


# ═══════════════════════════════════════════════════════════════════
# NEURAL CORE - MAIN CLASS
# ═══════════════════════════════════════════════════════════════════

class NeuralCore:
    """
    Central intelligence hub for ReviewSignal.
    Integrates embeddings, statistics, and anomaly detection.

    Usage:
        core = NeuralCore()

        # Embeddings
        emb = core.embed("Great food, terrible service")
        similar = core.find_similar("bad experience", reviews)

        # Statistics
        core.update_stats("loc_123", 4.5)
        is_anomaly = core.check_anomaly("loc_123", 2.0)

        # Weekly refit (call from cron)
        core.weekly_refit()
    """

    def __init__(self, config: Optional[NeuralCoreConfig] = None):
        """
        Initialize Neural Core.

        Args:
            config: NeuralCoreConfig (uses defaults if not provided)
        """
        self.config = config or NeuralCoreConfig()
        self.cache = UnifiedCache(self.config)
        self.embeddings = EmbeddingEngine(self.config, self.cache)
        self.stats = IncrementalStatsEngine(self.config, self.cache)
        self.isolation_forest = AdaptiveIsolationForest(self.config, self.cache)

        self._initialized_at = datetime.utcnow()

        logger.info(
            "neural_core_initialized",
            embedding_model=self.config.embedding_model,
            stats_window=self.config.stats_window_days,
            iso_refit_interval=self.config.iso_refit_interval_days
        )

    # ─────────────────────────────────────────────────────────────
    # EMBEDDING API
    # ─────────────────────────────────────────────────────────────

    def embed(self, text: str) -> np.ndarray:
        """Get embedding for text"""
        return self.embeddings.embed(text).embedding

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Get embeddings for multiple texts"""
        results = self.embeddings.embed_batch(texts)
        return np.array([r.embedding for r in results])

    def similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between texts"""
        return self.embeddings.similarity(text1, text2)

    def find_similar(
        self,
        query: str,
        candidates: List[str],
        top_k: int = 5
    ) -> List[Dict]:
        """Find similar texts"""
        result = self.embeddings.find_similar(query, candidates, top_k)
        return result.matches

    # ─────────────────────────────────────────────────────────────
    # STATISTICS API
    # ─────────────────────────────────────────────────────────────

    def update_stats(
        self,
        entity_id: str,
        value: float,
        entity_type: str = "location"
    ) -> IncrementalStats:
        """Update incremental statistics"""
        return self.stats.update(entity_id, value, entity_type)

    def get_stats(self, entity_id: str) -> Optional[IncrementalStats]:
        """Get statistics for entity"""
        return self.stats.get_stats(entity_id)

    def check_anomaly(
        self,
        entity_id: str,
        value: float
    ) -> AnomalyPrediction:
        """Check if value is anomalous"""
        return self.stats.is_anomaly(entity_id, value)

    # ─────────────────────────────────────────────────────────────
    # ISOLATION FOREST API
    # ─────────────────────────────────────────────────────────────

    def add_training_sample(self, features: np.ndarray) -> None:
        """Add sample for Isolation Forest training"""
        self.isolation_forest.add_sample(features)

    def predict_anomaly(self, features: np.ndarray) -> Tuple[bool, float]:
        """Predict anomaly using Isolation Forest"""
        return self.isolation_forest.predict(features)

    def weekly_refit(self) -> Dict:
        """
        Perform weekly model refit.
        Call this from cron job.
        """
        logger.info("weekly_refit_starting")
        result = self.isolation_forest.refit(force=True)
        logger.info("weekly_refit_complete", result=result)
        return result

    def reload_model(self) -> Dict:
        """
        Reload Isolation Forest model from Redis cache.
        Call this after external refit (e.g., cron job) to sync.
        """
        logger.info("model_reload_requested")
        result = self.isolation_forest.reload_from_cache()
        logger.info("model_reload_complete", result=result)
        return result

    # ─────────────────────────────────────────────────────────────
    # COMBINED API
    # ─────────────────────────────────────────────────────────────

    def analyze_review(
        self,
        review_text: str,
        rating: float,
        location_id: str
    ) -> Dict:
        """
        Complete analysis of a single review.

        Args:
            review_text: Review text content
            rating: Rating value (1-5)
            location_id: Location identifier

        Returns:
            Analysis result with embedding, stats update, and anomaly check
        """
        # 1. Generate embedding
        embedding_result = self.embeddings.embed(review_text)

        # 2. Update statistics
        stats = self.stats.update(location_id, rating, "location")

        # 3. Check for anomaly
        anomaly = self.stats.is_anomaly(location_id, rating)

        # 4. Add to Isolation Forest training
        # Use embedding + rating as features
        features = np.concatenate([
            embedding_result.embedding,
            np.array([rating, stats.momentum_7d, stats.count])
        ])
        self.isolation_forest.add_sample(features)

        return {
            "embedding_computed": True,
            "embedding_from_cache": embedding_result.from_cache,
            "stats": stats.to_dict(),
            "anomaly": anomaly.to_dict(),
            "analyzed_at": datetime.utcnow().isoformat()
        }

    # ─────────────────────────────────────────────────────────────
    # HEALTH & MONITORING
    # ─────────────────────────────────────────────────────────────

    def health_check(self) -> Dict:
        """Get health status of Neural Core"""
        return {
            "status": "healthy",
            "initialized_at": self._initialized_at.isoformat(),
            "uptime_seconds": (datetime.utcnow() - self._initialized_at).total_seconds(),
            "cache": self.cache.get_cache_stats(),
            "isolation_forest": self.isolation_forest.get_model_info(),
            "stats_tracked": len(self.stats._stats),
            "config": self.config.to_dict()
        }


# ═══════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════

_neural_core_instance: Optional[NeuralCore] = None


def get_neural_core(config: Optional[NeuralCoreConfig] = None) -> NeuralCore:
    """Get or create Neural Core singleton instance"""
    global _neural_core_instance
    if _neural_core_instance is None:
        _neural_core_instance = NeuralCore(config)
    return _neural_core_instance


# ═══════════════════════════════════════════════════════════════════
# CLI / MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  NEURAL CORE - ReviewSignal Intelligence Hub")
    print("  Version 5.1.0 - MiniLM + Incremental Stats + Adaptive IF")
    print("="*70)

    # Initialize
    core = NeuralCore()

    # Test 1: Embeddings
    print("\n" + "-"*70)
    print("  TEST 1: Semantic Embeddings (MiniLM)")
    print("-"*70)

    texts = [
        "The food was absolutely amazing, best restaurant ever!",
        "Terrible experience, cold food and rude staff",
        "Average meal, nothing special but okay",
        "Great service but the food was disappointing"
    ]

    for text in texts[:2]:
        emb = core.embed(text)
        print(f"  '{text[:50]}...'")
        print(f"    → Shape: {emb.shape}, Norm: {np.linalg.norm(emb):.4f}")

    # Similarity
    sim = core.similarity(texts[0], texts[1])
    print(f"\n  Similarity (positive vs negative): {sim:.4f}")

    # Test 2: Incremental Statistics
    print("\n" + "-"*70)
    print("  TEST 2: Incremental Statistics")
    print("-"*70)

    # Simulate ratings over time
    np.random.seed(42)
    for i in range(50):
        rating = np.random.normal(4.0, 0.3)
        stats = core.update_stats("test_location", rating)

    print(f"  Location: test_location")
    print(f"  Count: {stats.count}")
    print(f"  Mean: {stats.mean:.4f}")
    print(f"  Std: {stats.std:.4f}")
    print(f"  Trend: {stats.trend_direction}")
    print(f"  Momentum (7d): {stats.momentum_7d:.4f}")

    # Test anomaly
    anomaly = core.check_anomaly("test_location", 2.0)
    print(f"\n  Anomaly check (value=2.0):")
    print(f"    Is Anomaly: {anomaly.is_anomaly}")
    print(f"    Anomaly Score: {anomaly.anomaly_score}")
    print(f"    Deviation (σ): {anomaly.deviation_sigma}")

    # Test 3: Find Similar
    print("\n" + "-"*70)
    print("  TEST 3: Semantic Search")
    print("-"*70)

    query = "bad food quality"
    similar = core.find_similar(query, texts, top_k=3)
    print(f"  Query: '{query}'")
    print(f"  Results:")
    for match in similar:
        print(f"    [{match['rank']}] {match['score']:.4f} - '{match['text'][:40]}...'")

    # Test 4: Health Check
    print("\n" + "-"*70)
    print("  TEST 4: Health Check")
    print("-"*70)

    health = core.health_check()
    print(f"  Status: {health['status']}")
    print(f"  Cache Hit Rate: {health['cache']['hit_rate']:.2%}")
    print(f"  Stats Tracked: {health['stats_tracked']}")
    print(f"  IF Model: {'Ready' if health['isolation_forest']['has_model'] else 'Not fitted'}")

    print("\n" + "="*70)
    print("  NEURAL CORE TEST COMPLETE")
    print("="*70)
