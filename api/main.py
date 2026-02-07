#!/usr/bin/env python3
"""
REVIEWSIGNAL MAIN API - Enterprise Customer-Facing API
System 5.0.8 - Production-Ready

This is the MAIN API for customers to:
- Access trading signals
- Get sentiment analysis
- Retrieve reports
- Manage subscriptions

Author: ReviewSignal Team
Version: 5.0.8
Date: February 2026
"""

import os
import time
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import structlog
import jwt
from functools import lru_cache

from config import DATABASE_URL, JWT_SECRET, PRICING_TIERS
from modules.enterprise_utils import (
    CircuitBreaker, CircuitBreakerConfig, retry, RetryConfig,
    HealthChecker, check_postgres, check_redis, RateLimiter
)

# Import GDPR API router
from api.gdpr_api import router as gdpr_router

logger = structlog.get_logger()

# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI APP CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="ReviewSignal API",
    description="""
    # ReviewSignal.ai - Alternative Data for Hedge Funds

    Quantum-inspired sentiment analysis delivering alpha signals from consumer reviews.

    ## Features
    - **Trading Signals**: BUY/HOLD/SELL recommendations with confidence scores
    - **Sentiment Analysis**: Real-time brand sentiment tracking
    - **Anomaly Detection**: Early warning system for sentiment shifts
    - **Monte Carlo Simulations**: Risk assessment through chaos analysis

    ## Authentication
    All endpoints require an API key in the `X-API-Key` header.

    ## Rate Limits
    - Trial: 100 requests/day
    - Starter: 1,000 requests/day
    - Pro: 10,000 requests/day
    - Enterprise: Unlimited

    ## Support
    Email: team@reviewsignal.ai
    """,
    version="5.0.8",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS for production
ALLOWED_ORIGINS = [
    "https://reviewsignal.ai",
    "https://www.reviewsignal.ai",
    "https://app.reviewsignal.ai",
    "https://dashboard.reviewsignal.ai",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# Include GDPR router
app.include_router(gdpr_router, prefix="/api/v1")


# ═══════════════════════════════════════════════════════════════════════════════
# CIRCUIT BREAKERS FOR EXTERNAL SERVICES
# ═══════════════════════════════════════════════════════════════════════════════

echo_engine_breaker = CircuitBreaker(
    "echo_engine",
    CircuitBreakerConfig(failure_threshold=3, timeout_seconds=30)
)

singularity_breaker = CircuitBreaker(
    "singularity_engine",
    CircuitBreakerConfig(failure_threshold=3, timeout_seconds=30)
)


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECKER
# ═══════════════════════════════════════════════════════════════════════════════

health_checker = HealthChecker()
health_checker.add_check("postgres", check_postgres)
health_checker.add_check("redis", check_redis)


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class APIKeyInfo(BaseModel):
    """API Key information"""
    api_key: str
    user_id: str
    tier: str
    rate_limit: int
    rate_limit_remaining: int
    valid_until: Optional[str]


class TradingSignalRequest(BaseModel):
    """Request for trading signal"""
    brand: str = Field(..., description="Brand to analyze (e.g., 'starbucks')")
    city: Optional[str] = Field(None, description="Optional city filter")
    period_days: int = Field(30, ge=7, le=90, description="Analysis period")


class TradingSignalResponse(BaseModel):
    """Trading signal response"""
    brand: str
    signal: str  # BUY, HOLD, SELL
    confidence: float
    risk_level: str
    chaos_index: float
    recommendation: str
    critical_locations: List[Dict[str, Any]]
    generated_at: str
    data_quality: Dict[str, Any]


class SentimentRequest(BaseModel):
    """Request for sentiment analysis"""
    brands: List[str] = Field(..., min_items=1, max_items=10)
    cities: Optional[List[str]] = None
    period_days: int = Field(30, ge=1, le=365)


class SentimentResponse(BaseModel):
    """Sentiment analysis response"""
    brands: Dict[str, Dict[str, Any]]
    overall_sentiment: float
    trend: str  # improving, stable, declining
    anomalies: List[Dict[str, Any]]
    generated_at: str


class AnomalyResponse(BaseModel):
    """Anomaly detection response"""
    anomalies: List[Dict[str, Any]]
    total_count: int
    severity_distribution: Dict[str, int]
    generated_at: str


class MonteCarloRequest(BaseModel):
    """Request for Monte Carlo simulation"""
    brand: Optional[str] = None
    n_trials: int = Field(500, ge=100, le=2000)


class MonteCarloResponse(BaseModel):
    """Monte Carlo simulation response"""
    mean_echo: float
    std_echo: float
    chaos_index: float
    percentile_95: float
    percentile_99: float
    stability_distribution: Dict[str, float]
    critical_locations: List[Dict[str, Any]]
    generated_at: str


class HealthResponse(BaseModel):
    """System health response"""
    status: str
    version: str
    services: Dict[str, Dict[str, Any]]
    uptime_seconds: float
    checked_at: str


# ═══════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION & RATE LIMITING
# ═══════════════════════════════════════════════════════════════════════════════

# Rate limiters per tier
rate_limiters = {
    "trial": RateLimiter("trial", rate=100, per_seconds=86400),
    "starter": RateLimiter("starter", rate=1000, per_seconds=86400),
    "pro": RateLimiter("pro", rate=10000, per_seconds=86400),
    "enterprise": RateLimiter("enterprise", rate=1000000, per_seconds=86400),
}


async def verify_api_key(
    x_api_key: str = Header(..., description="API Key for authentication")
) -> APIKeyInfo:
    """Verify API key and return user info"""
    from sqlalchemy import create_engine, text

    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT ak.id, ak.key_hash, ak.user_id, ak.tier, ak.is_active, ak.expires_at,
                       u.email, u.company_name
                FROM api_keys ak
                JOIN users u ON ak.user_id = u.id
                WHERE ak.key_hash = :key_hash AND ak.is_active = true
            """),
            {"key_hash": x_api_key}  # In production, hash the key first
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=401,
            detail="Invalid or inactive API key"
        )

    key_id, key_hash, user_id, tier, is_active, expires_at, email, company = row

    # Check expiration
    if expires_at and expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=401,
            detail="API key has expired"
        )

    # Check rate limit
    limiter = rate_limiters.get(tier, rate_limiters["trial"])
    tier_info = PRICING_TIERS.get(tier, PRICING_TIERS["trial"])
    rate_limit = tier_info.get("api_calls_limit", 100)

    if not limiter.allow():
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Your tier ({tier}) allows {rate_limit} requests/day."
        )

    return APIKeyInfo(
        api_key=x_api_key[:8] + "...",
        user_id=str(user_id),
        tier=tier,
        rate_limit=rate_limit,
        rate_limit_remaining=limiter.get_remaining(),
        valid_until=expires_at.isoformat() if expires_at else None
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENGINE LOADERS (with caching)
# ═══════════════════════════════════════════════════════════════════════════════

_echo_engine_cache = {}
_echo_engine_cache_time = None
CACHE_TTL = 3600  # 1 hour


@lru_cache(maxsize=1)
def get_echo_engine():
    """Get or create Echo Engine (cached)"""
    from modules.echo_engine import create_echo_engine_from_db

    with echo_engine_breaker:
        return create_echo_engine_from_db(database_url=DATABASE_URL)


def get_singularity_engine(chain_filter: str = None, days: int = 30):
    """Get Singularity Engine for specific query"""
    from modules.singularity_engine.core import create_singularity_engine_from_db

    with singularity_breaker:
        engine, _ = create_singularity_engine_from_db(
            chain_filter=chain_filter,
            days_back=days,
            include_echo=False
        )
        return engine


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/", include_in_schema=False)
async def root():
    """API root - redirect to docs"""
    return {
        "name": "ReviewSignal API",
        "version": "5.0.8",
        "docs": "/docs",
        "status": "operational"
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    System health check.

    Returns status of all system components including databases and engines.
    """
    start_time = time.time()
    results = health_checker.check_all()

    overall_status = "healthy"
    if any(r.status == "unhealthy" for r in results.values()):
        overall_status = "unhealthy"
    elif any(r.status == "degraded" for r in results.values()):
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version="5.0.8",
        services={name: {"status": r.status, "latency_ms": r.latency_ms} for name, r in results.items()},
        uptime_seconds=time.time() - app.state.start_time if hasattr(app.state, 'start_time') else 0,
        checked_at=datetime.utcnow().isoformat()
    )


# ═══════════════════════════════════════════════════════════════════════════════
# AUTHENTICATED ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/signal", response_model=TradingSignalResponse, tags=["Trading Signals"])
async def get_trading_signal(
    request: TradingSignalRequest,
    api_key: APIKeyInfo = Depends(verify_api_key)
):
    """
    Generate trading signal for a brand.

    Returns BUY, HOLD, or SELL recommendation with confidence score
    based on Echo Engine analysis of sentiment propagation patterns.

    **Signal Types:**
    - `BUY`: System is stable, resilient to shocks
    - `HOLD`: Neutral state, monitor situation
    - `SELL`: High cascade risk, sentiment deterioration likely

    **Confidence Levels:**
    - 0.0 - 0.4: Low confidence
    - 0.4 - 0.7: Medium confidence
    - 0.7 - 1.0: High confidence
    """
    logger.info(
        "trading_signal_requested",
        brand=request.brand,
        user=api_key.user_id,
        tier=api_key.tier
    )

    try:
        engine = get_echo_engine()
        signal = engine.generate_trading_signal(
            brand=request.brand,
            n_trials=300
        )

        signal_dict = signal.to_dict()

        return TradingSignalResponse(
            brand=request.brand,
            signal=signal_dict['signal'],
            confidence=signal_dict['confidence'],
            risk_level=signal_dict['risk_level'],
            chaos_index=signal_dict['chaos_index'],
            recommendation=signal_dict['recommendation'],
            critical_locations=signal_dict['critical_locations'][:5],
            generated_at=signal_dict['generated_at'],
            data_quality={
                "locations_analyzed": engine.n,
                "chains_in_network": len(engine._chain_locations),
                "data_freshness": "real-time"
            }
        )

    except Exception as e:
        logger.error("trading_signal_error", error=str(e), brand=request.brand)
        raise HTTPException(status_code=500, detail=f"Signal generation failed: {str(e)}")


@app.post("/api/v1/sentiment", response_model=SentimentResponse, tags=["Sentiment Analysis"])
async def get_sentiment(
    request: SentimentRequest,
    api_key: APIKeyInfo = Depends(verify_api_key)
):
    """
    Get sentiment analysis for multiple brands.

    Analyzes review sentiment trends and identifies anomalies.
    """
    logger.info(
        "sentiment_requested",
        brands=request.brands,
        user=api_key.user_id
    )

    from sqlalchemy import create_engine, text

    engine_db = create_engine(DATABASE_URL)

    brands_data = {}
    all_sentiments = []

    with engine_db.connect() as conn:
        for brand in request.brands:
            result = conn.execute(
                text("""
                    SELECT
                        AVG(r.sentiment_score) as avg_sentiment,
                        AVG(r.rating) as avg_rating,
                        COUNT(*) as review_count,
                        STDDEV(r.sentiment_score) as sentiment_std
                    FROM reviews r
                    JOIN locations l ON r.location_id = l.id
                    WHERE LOWER(l.chain_id) LIKE :brand
                    AND r.review_time >= :start_date
                """),
                {
                    "brand": f"%{brand.lower()}%",
                    "start_date": datetime.utcnow() - timedelta(days=request.period_days)
                }
            )
            row = result.fetchone()

            avg_sentiment = float(row[0]) if row[0] else 0.0
            all_sentiments.append(avg_sentiment)

            brands_data[brand] = {
                "sentiment": avg_sentiment,
                "rating": float(row[1]) if row[1] else 0.0,
                "review_count": int(row[2]) if row[2] else 0,
                "volatility": float(row[3]) if row[3] else 0.0
            }

    # Calculate overall sentiment
    overall = sum(all_sentiments) / len(all_sentiments) if all_sentiments else 0.0

    # Determine trend (simplified)
    trend = "stable"
    if overall > 0.2:
        trend = "improving"
    elif overall < -0.2:
        trend = "declining"

    return SentimentResponse(
        brands=brands_data,
        overall_sentiment=overall,
        trend=trend,
        anomalies=[],  # Would be populated by ML anomaly detector
        generated_at=datetime.utcnow().isoformat()
    )


@app.get("/api/v1/anomalies", response_model=AnomalyResponse, tags=["Anomaly Detection"])
async def get_anomalies(
    brand: Optional[str] = Query(None, description="Filter by brand"),
    days: int = Query(7, ge=1, le=30, description="Lookback period"),
    api_key: APIKeyInfo = Depends(verify_api_key)
):
    """
    Get detected anomalies in sentiment data.

    Returns list of anomalies with severity levels:
    - `critical`: Major sentiment shift, immediate attention needed
    - `high`: Significant change, monitor closely
    - `medium`: Notable deviation, worth watching
    - `low`: Minor fluctuation
    """
    logger.info(
        "anomalies_requested",
        brand=brand,
        days=days,
        user=api_key.user_id
    )

    from modules.ml_anomaly_detector import MLAnomalyDetector

    # This would normally query real anomalies from database
    # For now, return structure
    return AnomalyResponse(
        anomalies=[],
        total_count=0,
        severity_distribution={"critical": 0, "high": 0, "medium": 0, "low": 0},
        generated_at=datetime.utcnow().isoformat()
    )


@app.post("/api/v1/monte-carlo", response_model=MonteCarloResponse, tags=["Risk Analysis"])
async def run_monte_carlo(
    request: MonteCarloRequest,
    api_key: APIKeyInfo = Depends(verify_api_key)
):
    """
    Run Monte Carlo simulation for risk assessment.

    Simulates random perturbations across the network to measure:
    - System stability
    - Cascade risk
    - Critical locations that amplify changes

    Higher chaos index = more unpredictable cascade patterns
    """
    # Check tier permissions
    if api_key.tier == "trial":
        raise HTTPException(
            status_code=403,
            detail="Monte Carlo simulation requires Starter tier or higher"
        )

    logger.info(
        "monte_carlo_requested",
        brand=request.brand,
        trials=request.n_trials,
        user=api_key.user_id
    )

    try:
        engine = get_echo_engine()
        result = engine.run_monte_carlo(n_trials=request.n_trials)
        result_dict = result.to_dict()

        return MonteCarloResponse(
            mean_echo=result_dict['mean_echo'],
            std_echo=result_dict['std_echo'],
            chaos_index=result_dict['system_chaos_index'],
            percentile_95=result_dict['percentile_95'],
            percentile_99=result_dict['percentile_99'],
            stability_distribution=result_dict['stability_distribution'],
            critical_locations=result_dict['critical_locations'][:10],
            generated_at=result_dict['computed_at']
        )

    except Exception as e:
        logger.error("monte_carlo_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")


@app.get("/api/v1/brands", tags=["Data"])
async def list_brands(
    api_key: APIKeyInfo = Depends(verify_api_key)
):
    """
    List all available brands in the system.

    Returns brands with location counts.
    """
    engine = get_echo_engine()

    brands = [
        {"brand": chain_id, "locations": len(indices)}
        for chain_id, indices in engine._chain_locations.items()
    ]
    brands.sort(key=lambda x: x["locations"], reverse=True)

    return {
        "total": len(brands),
        "brands": brands
    }


@app.get("/api/v1/cities", tags=["Data"])
async def list_cities(
    api_key: APIKeyInfo = Depends(verify_api_key)
):
    """
    List all cities with coverage.
    """
    engine = get_echo_engine()

    cities = [
        {"city": city, "locations": len(indices)}
        for city, indices in engine._city_locations.items()
    ]
    cities.sort(key=lambda x: x["locations"], reverse=True)

    return {
        "total": len(cities),
        "cities": cities
    }


@app.get("/api/v1/account", tags=["Account"])
async def get_account_info(
    api_key: APIKeyInfo = Depends(verify_api_key)
):
    """
    Get account information and usage statistics.
    """
    tier_info = PRICING_TIERS.get(api_key.tier, PRICING_TIERS["trial"])

    return {
        "user_id": api_key.user_id,
        "tier": api_key.tier,
        "tier_name": tier_info.get("name", api_key.tier),
        "rate_limit": api_key.rate_limit,
        "rate_limit_remaining": api_key.rate_limit_remaining,
        "features": {
            "trading_signals": True,
            "sentiment_analysis": True,
            "anomaly_detection": api_key.tier != "trial",
            "monte_carlo": api_key.tier not in ["trial"],
            "api_export": api_key.tier in ["pro", "enterprise"],
            "custom_reports": api_key.tier == "enterprise",
        },
        "valid_until": api_key.valid_until
    }


# ═══════════════════════════════════════════════════════════════════════════════
# STARTUP / SHUTDOWN
# ═══════════════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    app.state.start_time = time.time()
    logger.info("main_api_starting", version="5.0.8")

    # Pre-warm engines
    try:
        get_echo_engine()
        logger.info("echo_engine_warmed")
    except Exception as e:
        logger.error("echo_engine_warmup_failed", error=str(e))


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("main_api_shutting_down")


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc)
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if os.getenv("DEBUG") else "An error occurred"
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CLI / MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*60)
    print("  REVIEWSIGNAL MAIN API")
    print("  Starting on http://localhost:8000")
    print("  Docs: http://localhost:8000/docs")
    print("="*60 + "\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
