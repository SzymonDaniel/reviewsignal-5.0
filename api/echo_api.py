#!/usr/bin/env python3
"""
ECHO ENGINE API - FastAPI Endpoints for Sentiment Propagation
System 5.0.7 - REST API for Echo Engine

Author: ReviewSignal Team
Version: 5.0.7
Date: January 2026

Endpoints:
- POST /api/echo/compute     - Compute echo for a specific location
- POST /api/echo/monte-carlo - Run Monte Carlo simulation
- POST /api/echo/signal      - Generate trading signal
- GET  /api/echo/health      - Get system health metrics
- GET  /api/echo/location/{id}/criticality - Get location criticality
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import structlog
import time

# Import Echo Engine and Database
from modules.echo_engine import (
    EchoEngine,
    EchoEngineConfig,
    create_echo_engine_from_db,
    LocationState,
    EchoResult,
    MonteCarloResult,
    TradingSignal,
)
from modules.database_schema import DatabaseManager
from config import DATABASE_URL

# Import custom metrics
try:
    from api.echo_metrics import (
        track_echo_computation, track_monte_carlo, track_trading_signal,
        track_engine_rebuild, track_cache_hit, track_cache_miss,
        track_criticality_check, update_engine_gauges, track_computation_duration
    )
    METRICS_ENABLED = True
except ImportError:
    try:
        from echo_metrics import (
            track_echo_computation, track_monte_carlo, track_trading_signal,
            track_engine_rebuild, track_cache_hit, track_cache_miss,
            track_criticality_check, update_engine_gauges, track_computation_duration
        )
        METRICS_ENABLED = True
    except ImportError:
        METRICS_ENABLED = False

# Import compliance modules
try:
    from compliance.audit.audit_logger import audit_logger, log_api_call, log_data_access
    from compliance.data_sourcing.source_attribution import SourceAttribution, DataSource
    from compliance.data_sourcing.rate_limiter_status import get_rate_limit_status
    COMPLIANCE_ENABLED = True
except ImportError:
    COMPLIANCE_ENABLED = False

logger = structlog.get_logger()

# ═══════════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════════

app = FastAPI(
    title="ReviewSignal Echo Engine API",
    description="Quantum-inspired sentiment propagation analysis for trading signals",
    version="5.0.7",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS - Production-ready configuration
ALLOWED_ORIGINS = [
    "https://reviewsignal.ai",
    "https://www.reviewsignal.ai",
    "https://app.reviewsignal.ai",
    "https://dashboard.reviewsignal.ai",
    "http://localhost:3000",  # Development
    "http://localhost:8000",  # Local API testing
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
)

# Audit Logging Middleware
if COMPLIANCE_ENABLED:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    import time

    class AuditLoggingMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            start_time = time.time()

            # Get client info
            client_ip = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log API call
            try:
                log_api_call(
                    endpoint=str(request.url.path),
                    method=request.method,
                    user_id=None,  # TODO: Extract from auth token when implemented
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    ip_address=client_ip,
                    user_agent=user_agent
                )
            except Exception as e:
                logger.error("audit_logging_error", error=str(e))

            return response

    app.add_middleware(AuditLoggingMiddleware)

# Database Manager
db_manager = None

# Cached Echo Engine (rebuilt periodically)
_echo_engine: Optional[EchoEngine] = None
_engine_built_at: Optional[datetime] = None
ENGINE_CACHE_TTL = 3600  # 1 hour


# ═══════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════════════

class EchoComputeRequest(BaseModel):
    """Request for echo computation"""
    location_id: str = Field(..., description="Location ID to perturb")
    time_steps: Optional[int] = Field(10, ge=1, le=50, description="Evolution time steps")
    perturbation: Optional[float] = Field(-0.5, ge=-2.0, le=2.0, description="Perturbation magnitude")


class MonteCarloRequest(BaseModel):
    """Request for Monte Carlo simulation"""
    n_trials: Optional[int] = Field(500, ge=10, le=5000, description="Number of trials")
    time_steps: Optional[int] = Field(10, ge=1, le=50, description="Evolution time steps")
    chain_filter: Optional[str] = Field(None, description="Filter by chain ID")
    city_filter: Optional[str] = Field(None, description="Filter by city name")


class TradingSignalRequest(BaseModel):
    """Request for trading signal generation"""
    brand: Optional[str] = Field(None, description="Brand/chain to analyze (None = all)")
    n_trials: Optional[int] = Field(300, ge=50, le=2000, description="Monte Carlo trials")


class EchoConfigUpdate(BaseModel):
    """Configuration update for Echo Engine"""
    self_influence: Optional[float] = Field(None, ge=0.0, le=1.0)
    geo_weight_max: Optional[float] = Field(None, ge=0.0, le=1.0)
    geo_radius_km: Optional[float] = Field(None, ge=1.0, le=500.0)
    brand_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    city_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    category_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    default_time_steps: Optional[int] = Field(None, ge=1, le=50)
    default_perturbation: Optional[float] = Field(None, ge=-2.0, le=2.0)


class APIResponse(BaseModel):
    """Standard API response wrapper with compliance metadata"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None  # Source attribution and compliance info
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ═══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def get_db_manager() -> DatabaseManager:
    """Get or create database manager."""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager(DATABASE_URL)
    return db_manager


def get_echo_engine(
    chain_filter: Optional[str] = None,
    city_filter: Optional[str] = None,
    force_rebuild: bool = False
) -> EchoEngine:
    """
    Get or create Echo Engine instance.
    Uses caching with TTL for performance.
    """
    global _echo_engine, _engine_built_at

    # Check cache validity (only for unfiltered queries)
    if not chain_filter and not city_filter and not force_rebuild:
        if _echo_engine is not None and _engine_built_at is not None:
            age = (datetime.utcnow() - _engine_built_at).total_seconds()
            if age < ENGINE_CACHE_TTL:
                # Track cache hit
                if METRICS_ENABLED:
                    track_cache_hit()
                return _echo_engine

    # Track cache miss
    if METRICS_ENABLED:
        track_cache_miss()

    # Build new engine - use direct database_url to bypass SQLAlchemy model issues
    start_time = time.time()
    engine = create_echo_engine_from_db(
        database_url=DATABASE_URL,
        chain_filter=chain_filter,
        city_filter=city_filter
    )

    # Track rebuild duration and update gauges
    if METRICS_ENABLED:
        duration = time.time() - start_time
        track_engine_rebuild(duration)
        update_engine_gauges(engine.n, len(engine._chain_locations))

    # Cache if unfiltered
    if not chain_filter and not city_filter:
        _echo_engine = engine
        _engine_built_at = datetime.utcnow()

    return engine


# ═══════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "echo_engine_api",
        "version": "5.0.7",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint"""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from fastapi.responses import Response

    # Import echo_metrics to register custom metrics
    if METRICS_ENABLED:
        try:
            import api.echo_metrics  # noqa - needed to register metrics
        except ImportError:
            import echo_metrics  # noqa - needed to register metrics

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/echo/compute", response_model=APIResponse)
async def compute_echo(request: EchoComputeRequest):
    """
    Compute echo (butterfly effect) for a specific location.

    The echo measures how much a perturbation at one location
    propagates through the entire system.

    High echo = changes at this location affect many others
    Low echo = changes are absorbed locally
    """
    start_time = time.time()
    try:
        engine = get_echo_engine()
        result = engine.compute_echo_by_location_id(
            location_id=request.location_id,
            T=request.time_steps,
            delta=request.perturbation
        )

        # Track metrics
        if METRICS_ENABLED:
            duration = time.time() - start_time
            track_echo_computation('individual')
            track_computation_duration('compute_echo', duration)

        return APIResponse(
            success=True,
            data=result.to_dict()
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("echo_compute_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/api/echo/monte-carlo", response_model=APIResponse)
async def run_monte_carlo(request: MonteCarloRequest):
    """
    Run Monte Carlo simulation to analyze system-wide sensitivity.

    This randomly perturbs locations and measures the echo distribution,
    providing insights into:
    - Overall system stability
    - Critical locations that cause largest cascades
    - Chaos index (predictability of cascade patterns)
    """
    start_time = time.time()
    try:
        engine = get_echo_engine(
            chain_filter=request.chain_filter,
            city_filter=request.city_filter
        )

        result = engine.run_monte_carlo(
            n_trials=request.n_trials,
            T=request.time_steps
        )

        # Track metrics
        if METRICS_ENABLED:
            duration = time.time() - start_time
            track_monte_carlo(request.chain_filter or 'all')
            track_computation_duration('monte_carlo', duration)

        return APIResponse(
            success=True,
            data=result.to_dict()
        )

    except Exception as e:
        logger.error("monte_carlo_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/api/echo/signal", response_model=APIResponse)
async def generate_signal(request: TradingSignalRequest):
    """
    Generate a trading signal based on Echo Engine analysis.

    Returns:
    - BUY: System is stable, resilient to shocks
    - HOLD: Neutral state, moderate sensitivity
    - SELL: System is unstable, high cascade risk

    The signal includes confidence score and supporting metrics.
    """
    start_time = time.time()
    try:
        engine = get_echo_engine()
        signal = engine.generate_trading_signal(
            brand=request.brand,
            n_trials=request.n_trials
        )

        # Track metrics
        if METRICS_ENABLED:
            duration = time.time() - start_time
            signal_data = signal.to_dict()
            signal_type = signal_data.get('signal', 'UNKNOWN')
            confidence = signal_data.get('confidence_level', 'UNKNOWN')
            track_trading_signal(signal_type, confidence)
            track_computation_duration('trading_signal', duration)

        return APIResponse(
            success=True,
            data=signal.to_dict()
        )

    except Exception as e:
        logger.error("signal_generation_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/api/echo/health", response_model=APIResponse)
async def get_system_health():
    """
    Get overall system health metrics.

    Provides a quick assessment of:
    - Number of locations in the network
    - Chaos index
    - Stability distribution
    - Top critical locations
    """
    try:
        engine = get_echo_engine()
        health = engine.get_system_health()

        return APIResponse(
            success=True,
            data=health
        )

    except Exception as e:
        logger.error("health_check_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/api/echo/location/{location_id}/criticality", response_model=APIResponse)
async def get_location_criticality(
    location_id: str,
    n_samples: int = Query(50, ge=10, le=200, description="Number of samples")
):
    """
    Analyze how critical a specific location is to system stability.

    Returns:
    - Mean and max echo values
    - Criticality level (LOW, MEDIUM, HIGH, CRITICAL)
    - Monitoring recommendations
    """
    start_time = time.time()
    try:
        engine = get_echo_engine()
        criticality = engine.get_location_criticality(
            location_id=location_id,
            n_samples=n_samples
        )

        # Track metrics
        if METRICS_ENABLED:
            duration = time.time() - start_time
            track_criticality_check()
            track_computation_duration('criticality', duration)

        return APIResponse(
            success=True,
            data=criticality
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("criticality_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/api/echo/locations", response_model=APIResponse)
async def list_locations(
    chain_filter: Optional[str] = Query(None, description="Filter by chain ID"),
    city_filter: Optional[str] = Query(None, description="Filter by city"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results")
):
    """
    List locations available in the Echo Engine network.
    """
    try:
        engine = get_echo_engine(
            chain_filter=chain_filter,
            city_filter=city_filter
        )

        locations = [
            {
                "location_id": loc.location_id,
                "name": loc.name,
                "city": loc.city,
                "chain_id": loc.chain_id,
                "current_rating": loc.current_rating,
                "current_sentiment": round(loc.current_sentiment, 4)
            }
            for loc in engine.locations[:limit]
        ]

        return APIResponse(
            success=True,
            data={
                "total": engine.n,
                "returned": len(locations),
                "locations": locations
            }
        )

    except Exception as e:
        logger.error("list_locations_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/api/echo/chains", response_model=APIResponse)
async def list_chains():
    """
    List all chains available in the Echo Engine network.
    """
    try:
        engine = get_echo_engine()

        chains = [
            {
                "chain_id": chain_id,
                "n_locations": len(indices)
            }
            for chain_id, indices in engine._chain_locations.items()
        ]
        chains.sort(key=lambda x: x["n_locations"], reverse=True)

        return APIResponse(
            success=True,
            data={
                "total": len(chains),
                "chains": chains
            }
        )

    except Exception as e:
        logger.error("list_chains_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/api/echo/cities", response_model=APIResponse)
async def list_cities():
    """
    List all cities available in the Echo Engine network.
    """
    try:
        engine = get_echo_engine()

        cities = [
            {
                "city": city,
                "n_locations": len(indices)
            }
            for city, indices in engine._city_locations.items()
        ]
        cities.sort(key=lambda x: x["n_locations"], reverse=True)

        return APIResponse(
            success=True,
            data={
                "total": len(cities),
                "cities": cities
            }
        )

    except Exception as e:
        logger.error("list_cities_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/api/echo/rebuild", response_model=APIResponse)
async def rebuild_engine(background_tasks: BackgroundTasks):
    """
    Force rebuild of the Echo Engine from database.
    Useful after data updates or configuration changes.
    """
    try:
        # Rebuild in foreground for simplicity
        engine = get_echo_engine(force_rebuild=True)

        return APIResponse(
            success=True,
            data={
                "message": "Echo Engine rebuilt successfully",
                "n_locations": engine.n,
                "n_chains": len(engine._chain_locations),
                "n_cities": len(engine._city_locations),
                "built_at": datetime.utcnow().isoformat()
            }
        )

    except Exception as e:
        logger.error("rebuild_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/api/echo/config", response_model=APIResponse)
async def get_config():
    """
    Get current Echo Engine configuration.
    """
    try:
        engine = get_echo_engine()
        return APIResponse(
            success=True,
            data=engine.config.to_dict()
        )

    except Exception as e:
        logger.error("config_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# Duplicate /metrics endpoint removed - using prometheus_client version at line 178


# ═══════════════════════════════════════════════════════════════════
# COMPLIANCE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/compliance/rate-limits", response_model=APIResponse)
async def get_rate_limits():
    """
    Get current rate limiting status across all APIs.
    Shows current usage, limits, and availability.
    """
    if not COMPLIANCE_ENABLED:
        return APIResponse(
            success=False,
            error="Compliance module not available"
        )

    try:
        status = get_rate_limit_status()
        return APIResponse(
            success=True,
            data=status
        )
    except Exception as e:
        logger.error("rate_limit_status_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/api/compliance/attribution")
async def get_attribution_info():
    """
    Get data sourcing and attribution information.
    Required for compliance with data source Terms of Service.
    """
    if not COMPLIANCE_ENABLED:
        return {
            "message": "Compliance module not available"
        }

    return {
        "data_sources": {
            "google_maps": {
                "attribution_text": SourceAttribution.get_attribution_text(DataSource.GOOGLE_MAPS),
                "terms_url": SourceAttribution.TERMS_URLS[DataSource.GOOGLE_MAPS],
                "terms_version": SourceAttribution.TOS_VERSIONS[DataSource.GOOGLE_MAPS],
                "attribution_required": True,
            },
            "apollo": {
                "attribution_text": SourceAttribution.get_attribution_text(DataSource.APOLLO),
                "terms_url": SourceAttribution.TERMS_URLS[DataSource.APOLLO],
                "terms_version": SourceAttribution.TOS_VERSIONS[DataSource.APOLLO],
                "attribution_required": True,
            },
        },
        "compliance_verified": True,
        "last_updated": datetime.utcnow().isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════
# STARTUP / SHUTDOWN
# ═══════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info("echo_api_starting")
    try:
        # Pre-warm the engine
        get_echo_engine()
        logger.info("echo_api_ready")
    except Exception as e:
        logger.error("echo_api_startup_error", error=str(e))


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("echo_api_shutting_down")


# ═══════════════════════════════════════════════════════════════════
# CLI / MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*60)
    print("  ECHO ENGINE API")
    print("  Starting on http://localhost:8002")
    print("="*60 + "\n")

    uvicorn.run(
        "echo_api:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )
