#!/usr/bin/env python3
"""
NEURAL API - REST API for Neural Core
Exposes MiniLM embeddings, statistics, and anomaly detection via HTTP.

Port: 8005
Endpoints:
    POST /api/neural/embed - Generate embedding for text
    POST /api/neural/embed-batch - Generate embeddings for multiple texts
    POST /api/neural/similar - Find similar texts
    POST /api/neural/stats/update - Update incremental statistics
    GET  /api/neural/stats/{entity_id} - Get statistics for entity
    POST /api/neural/anomaly/check - Check if value is anomalous
    POST /api/neural/analyze-review - Complete review analysis
    GET  /api/neural/health - Health check
    POST /api/neural/refit - Trigger manual refit

Author: ReviewSignal Team
Version: 5.1.0
Date: February 2026
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import numpy as np
from datetime import datetime
import structlog

# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

logger = structlog.get_logger()

# ═══════════════════════════════════════════════════════════════════
# PROMETHEUS METRICS
# ═══════════════════════════════════════════════════════════════════

EMBEDDINGS_COMPUTED = Counter(
    'neural_embeddings_computed_total',
    'Total embeddings computed',
    ['from_cache']
)

SIMILARITY_SEARCHES = Counter(
    'neural_similarity_searches_total',
    'Total similarity searches'
)

STATS_UPDATES = Counter(
    'neural_stats_updates_total',
    'Total statistics updates',
    ['entity_type']
)

ANOMALIES_DETECTED = Counter(
    'neural_anomalies_detected_total',
    'Total anomalies detected'
)

REQUEST_DURATION = Histogram(
    'neural_request_duration_seconds',
    'Request duration in seconds',
    ['endpoint']
)

CACHE_HIT_RATE = Gauge(
    'neural_cache_hit_rate',
    'Cache hit rate'
)

STATS_TRACKED = Gauge(
    'neural_stats_tracked',
    'Number of entities with tracked statistics'
)

# ═══════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════════════

class EmbedRequest(BaseModel):
    text: str = Field(..., description="Text to embed")
    use_cache: bool = Field(True, description="Whether to use cache")


class EmbedBatchRequest(BaseModel):
    texts: List[str] = Field(..., description="Texts to embed")
    use_cache: bool = Field(True, description="Whether to use cache")


class SimilarRequest(BaseModel):
    query: str = Field(..., description="Query text")
    candidates: List[str] = Field(..., description="Candidate texts to search")
    top_k: int = Field(5, description="Number of top matches to return")
    threshold: float = Field(0.5, description="Minimum similarity threshold")


class StatsUpdateRequest(BaseModel):
    entity_id: str = Field(..., description="Entity identifier")
    value: float = Field(..., description="Value to update with")
    entity_type: str = Field("location", description="Type of entity")


class AnomalyCheckRequest(BaseModel):
    entity_id: str = Field(..., description="Entity identifier")
    value: float = Field(..., description="Value to check")
    threshold_sigma: Optional[float] = Field(None, description="Custom threshold")


class ReviewAnalysisRequest(BaseModel):
    review_text: str = Field(..., description="Review text content")
    rating: float = Field(..., description="Rating value (1-5)")
    location_id: str = Field(..., description="Location identifier")


class EmbedResponse(BaseModel):
    embedding: List[float]
    dimension: int
    model: str
    from_cache: bool
    computed_at: str


class SimilarResponse(BaseModel):
    query: str
    matches: List[Dict[str, Any]]
    total_candidates: int
    search_time_ms: float


class StatsResponse(BaseModel):
    entity_id: str
    entity_type: str
    count: int
    mean: float
    std: float
    trend_direction: str
    momentum_7d: float
    momentum_30d: float
    last_updated: str


class AnomalyResponse(BaseModel):
    entity_id: str
    value: float
    is_anomaly: bool
    anomaly_score: float
    deviation_sigma: float
    context: Dict[str, Any]


# ═══════════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════════

app = FastAPI(
    title="ReviewSignal Neural API",
    description="MiniLM Embeddings + Incremental Statistics + Anomaly Detection",
    version="5.1.0"
)

# CORS - production whitelist
ALLOWED_ORIGINS = [
    "https://reviewsignal.ai",
    "https://www.reviewsignal.ai",
    "https://app.reviewsignal.ai",
    "https://dashboard.reviewsignal.ai",
    "http://localhost:3000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# Neural Core instance (lazy loaded)
_neural_core = None


def get_core():
    """Get or create Neural Core instance"""
    global _neural_core
    if _neural_core is None:
        from modules.neural_core import get_neural_core
        _neural_core = get_neural_core()
    return _neural_core


# ═══════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy", "service": "neural-api", "port": 8005}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    core = get_core()
    health = core.health_check()

    # Update gauges
    CACHE_HIT_RATE.set(health["cache"]["hit_rate"])
    STATS_TRACKED.set(health["stats_tracked"])

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/neural/health")
async def neural_health():
    """Detailed Neural Core health check"""
    core = get_core()
    return core.health_check()


# ─────────────────────────────────────────────────────────────
# EMBEDDING ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.post("/api/neural/embed", response_model=EmbedResponse)
async def embed_text(request: EmbedRequest):
    """Generate embedding for single text"""
    import time
    start = time.time()

    core = get_core()
    result = core.embeddings.embed(request.text, use_cache=request.use_cache)

    EMBEDDINGS_COMPUTED.labels(from_cache=str(result.from_cache)).inc()
    REQUEST_DURATION.labels(endpoint="embed").observe(time.time() - start)

    return EmbedResponse(
        embedding=result.embedding.tolist(),
        dimension=len(result.embedding),
        model=result.model,
        from_cache=result.from_cache,
        computed_at=result.computed_at
    )


@app.post("/api/neural/embed-batch")
async def embed_batch(request: EmbedBatchRequest):
    """Generate embeddings for multiple texts"""
    import time
    start = time.time()

    if len(request.texts) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 texts per batch")

    core = get_core()
    results = core.embeddings.embed_batch(request.texts, use_cache=request.use_cache)

    for r in results:
        EMBEDDINGS_COMPUTED.labels(from_cache=str(r.from_cache)).inc()

    REQUEST_DURATION.labels(endpoint="embed_batch").observe(time.time() - start)

    return {
        "embeddings": [r.embedding.tolist() for r in results],
        "count": len(results),
        "dimension": results[0].embedding.shape[0] if results else 0,
        "model": results[0].model if results else None,
        "cache_hits": sum(1 for r in results if r.from_cache)
    }


@app.post("/api/neural/similar", response_model=SimilarResponse)
async def find_similar(request: SimilarRequest):
    """Find similar texts using semantic search"""
    import time
    start = time.time()

    if len(request.candidates) > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 candidates")

    core = get_core()
    result = core.embeddings.find_similar(
        request.query,
        request.candidates,
        top_k=request.top_k,
        threshold=request.threshold
    )

    SIMILARITY_SEARCHES.inc()
    REQUEST_DURATION.labels(endpoint="similar").observe(time.time() - start)

    return SimilarResponse(
        query=result.query,
        matches=result.matches,
        total_candidates=result.total_candidates,
        search_time_ms=result.search_time_ms
    )


# ─────────────────────────────────────────────────────────────
# STATISTICS ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.post("/api/neural/stats/update", response_model=StatsResponse)
async def update_stats(request: StatsUpdateRequest):
    """Update incremental statistics for entity"""
    core = get_core()
    stats = core.update_stats(
        request.entity_id,
        request.value,
        request.entity_type
    )

    STATS_UPDATES.labels(entity_type=request.entity_type).inc()

    return StatsResponse(
        entity_id=stats.entity_id,
        entity_type=stats.entity_type,
        count=stats.count,
        mean=round(stats.mean, 4),
        std=round(stats.std, 4),
        trend_direction=stats.trend_direction,
        momentum_7d=round(stats.momentum_7d, 4),
        momentum_30d=round(stats.momentum_30d, 4),
        last_updated=stats.last_updated
    )


@app.get("/api/neural/stats/{entity_id}", response_model=StatsResponse)
async def get_stats(entity_id: str):
    """Get statistics for entity"""
    core = get_core()
    stats = core.get_stats(entity_id)

    if stats is None:
        raise HTTPException(status_code=404, detail=f"No statistics found for {entity_id}")

    return StatsResponse(
        entity_id=stats.entity_id,
        entity_type=stats.entity_type,
        count=stats.count,
        mean=round(stats.mean, 4),
        std=round(stats.std, 4),
        trend_direction=stats.trend_direction,
        momentum_7d=round(stats.momentum_7d, 4),
        momentum_30d=round(stats.momentum_30d, 4),
        last_updated=stats.last_updated
    )


# ─────────────────────────────────────────────────────────────
# ANOMALY ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.post("/api/neural/anomaly/check", response_model=AnomalyResponse)
async def check_anomaly(request: AnomalyCheckRequest):
    """Check if value is anomalous"""
    core = get_core()

    if request.threshold_sigma:
        prediction = core.stats.is_anomaly(
            request.entity_id,
            request.value,
            request.threshold_sigma
        )
    else:
        prediction = core.check_anomaly(request.entity_id, request.value)

    if prediction.is_anomaly:
        ANOMALIES_DETECTED.inc()

    return AnomalyResponse(
        entity_id=prediction.entity_id,
        value=prediction.value,
        is_anomaly=prediction.is_anomaly,
        anomaly_score=prediction.anomaly_score,
        deviation_sigma=prediction.deviation_sigma,
        context=prediction.context
    )


# ─────────────────────────────────────────────────────────────
# COMBINED ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.post("/api/neural/analyze-review")
async def analyze_review(request: ReviewAnalysisRequest):
    """Complete analysis of a single review"""
    import time
    start = time.time()

    core = get_core()
    result = core.analyze_review(
        request.review_text,
        request.rating,
        request.location_id
    )

    REQUEST_DURATION.labels(endpoint="analyze_review").observe(time.time() - start)

    return result


# ─────────────────────────────────────────────────────────────
# ADMIN ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.post("/api/neural/refit")
async def trigger_refit(background_tasks: BackgroundTasks):
    """Trigger manual Isolation Forest refit"""
    def do_refit():
        core = get_core()
        return core.weekly_refit()

    background_tasks.add_task(do_refit)

    return {
        "status": "refit_scheduled",
        "message": "Isolation Forest refit scheduled in background"
    }


@app.get("/api/neural/model-info")
async def model_info():
    """Get Isolation Forest model information"""
    core = get_core()
    return core.isolation_forest.get_model_info()


@app.post("/api/neural/reload")
async def reload_model():
    """
    Reload Isolation Forest model from Redis cache.
    Call this after cron job refit to sync the running service.
    """
    core = get_core()
    result = core.reload_model()
    return result


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*60)
    print("  NEURAL API - ReviewSignal Intelligence Hub")
    print("  Port: 8005")
    print("="*60 + "\n")

    uvicorn.run(
        "neural_api:app",
        host="0.0.0.0",
        port=8005,
        reload=False,
        workers=1,
        log_level="info"
    )
