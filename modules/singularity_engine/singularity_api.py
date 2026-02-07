# ═══════════════════════════════════════════════════════════════════════════════
# SINGULARITY ENGINE - FastAPI Endpoints
# REST API for accessing Singularity Engine capabilities
# ═══════════════════════════════════════════════════════════════════════════════

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from pydantic import BaseModel, Field
import structlog

from .core import SingularityEngine, create_singularity_engine_from_db
from .models import (
    SingularityConfig,
    SingularityResult,
    SingularityInsight,
    CausalGraph,
    TimeFold,
)
from .utils import generate_analysis_id

logger = structlog.get_logger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

router = APIRouter(
    prefix="/singularity",
    tags=["singularity"],
    responses={404: {"description": "Not found"}}
)


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class AnalysisRequest(BaseModel):
    """Request model for full analysis"""
    chain_filter: Optional[str] = Field(None, description="Filter by chain name (e.g., 'starbucks')")
    city_filter: Optional[str] = Field(None, description="Filter by city (e.g., 'new york')")
    days_back: int = Field(30, ge=1, le=365, description="Days of data to analyze")
    modules: Optional[List[str]] = Field(
        None,
        description="Modules to run: temporal, semantic, causal, topology, echo"
    )
    max_depth: int = Field(7, ge=1, le=10, description="Max depth for causal archaeology")
    include_echo: bool = Field(True, description="Include Echo Engine analysis")


class CausalRequest(BaseModel):
    """Request model for causal analysis"""
    chain_filter: Optional[str] = None
    symptom: str = Field(..., description="Symptom to investigate (e.g., 'rating dropped 20%')")
    max_depth: int = Field(7, ge=1, le=10)


class TemporalRequest(BaseModel):
    """Request model for temporal analysis"""
    chain_filter: Optional[str] = None
    city_filter: Optional[str] = None
    days_back: int = Field(30, ge=1, le=365)
    fold_type: str = Field("weekly", description="Fold type: weekly, monthly, seasonal, lunar")


class ComparisonRequest(BaseModel):
    """Request model for chain comparison"""
    chain_a: str = Field(..., description="First chain to compare")
    chain_b: str = Field(..., description="Second chain to compare")
    days_back: int = Field(30, ge=1, le=365)


class InsightResponse(BaseModel):
    """Simplified insight response"""
    insight_id: str
    confidence: str
    confidence_score: float
    synthesis: str
    trading_action: str
    trading_confidence: float
    key_drivers: List[str]
    warning_signals: List[str]
    action_items: List[str]
    risk_factors: List[str]


class AnalysisResponse(BaseModel):
    """Response model for analysis"""
    analysis_id: str
    status: str
    chain_filter: Optional[str]
    city_filter: Optional[str]
    total_reviews: int
    total_locations: int
    modules_used: List[str]
    processing_time_ms: int
    overall_confidence: float
    insights: List[InsightResponse]
    warnings: List[str]
    errors: List[str]


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    modules_available: List[str]
    database_connected: bool


# ═══════════════════════════════════════════════════════════════════════════════
# BACKGROUND TASK STORAGE
# ═══════════════════════════════════════════════════════════════════════════════

# Simple in-memory storage for async results
_analysis_results: Dict[str, Any] = {}


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint

    Returns status of Singularity Engine and its dependencies.
    """
    # Check database connection
    db_connected = False
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            database="reviewsignal",
            user="reviewsignal",
            password="reviewsignal2026",
            connect_timeout=5
        )
        conn.close()
        db_connected = True
    except Exception:
        pass

    return HealthResponse(
        status="healthy" if db_connected else "degraded",
        version="1.0.0",
        modules_available=["temporal", "semantic", "causal", "topology", "echo"],
        database_connected=db_connected
    )


@router.post("/analyze", response_model=AnalysisResponse)
async def run_analysis(request: AnalysisRequest):
    """
    Run full Singularity Engine analysis

    Analyzes reviews using all enabled modules and returns synthesized insights.

    **Modules:**
    - `temporal`: Time-based pattern detection
    - `semantic`: Cross-review correlation and prophetic review detection
    - `causal`: Root cause archaeology (7+ levels deep)
    - `topology`: Topological data analysis for market gaps
    - `echo`: Echo Engine integration for system dynamics
    """
    try:
        # Create engine from database
        engine, echo = create_singularity_engine_from_db(
            chain_filter=request.chain_filter,
            city_filter=request.city_filter,
            days_back=request.days_back,
            include_echo=request.include_echo
        )

        # Run analysis
        result = engine.analyze(
            modules=request.modules,
            chain_filter=request.chain_filter,
            city_filter=request.city_filter,
            max_depth=request.max_depth
        )

        # Convert to response
        return _convert_result_to_response(result)

    except Exception as e:
        logger.error("analysis_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/async")
async def run_analysis_async(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks
):
    """
    Run analysis asynchronously

    Returns immediately with analysis_id. Poll /analyze/status/{id} for results.
    """
    analysis_id = generate_analysis_id()

    # Store pending status
    _analysis_results[analysis_id] = {
        'status': 'processing',
        'started_at': datetime.utcnow().isoformat()
    }

    # Add background task
    background_tasks.add_task(
        _run_analysis_background,
        analysis_id,
        request
    )

    return {
        'analysis_id': analysis_id,
        'status': 'processing',
        'poll_url': f'/singularity/analyze/status/{analysis_id}'
    }


@router.get("/analyze/status/{analysis_id}")
async def get_analysis_status(analysis_id: str):
    """
    Get status of async analysis

    Returns current status and results if complete.
    """
    if analysis_id not in _analysis_results:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return _analysis_results[analysis_id]


@router.post("/causal")
async def run_causal_analysis(request: CausalRequest):
    """
    Run deep causal archaeology analysis

    Investigates a specific symptom to find root causes up to 7+ levels deep.

    **Example symptoms:**
    - "rating dropped 20%"
    - "service complaints increased"
    - "long wait times reported"
    """
    try:
        engine, _ = create_singularity_engine_from_db(
            chain_filter=request.chain_filter,
            include_echo=False
        )

        graph = engine.analyze_symptom(
            symptom=request.symptom,
            max_depth=request.max_depth
        )

        return graph.to_dict()

    except Exception as e:
        logger.error("causal_analysis_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/temporal")
async def run_temporal_analysis(request: TemporalRequest):
    """
    Run temporal manifold analysis

    Folds time to discover hidden patterns.

    **Fold types:**
    - `weekly`: Compare days of week
    - `monthly`: Compare weeks of month
    - `seasonal`: Compare quarters
    - `lunar`: Compare lunar phases
    """
    try:
        engine, _ = create_singularity_engine_from_db(
            chain_filter=request.chain_filter,
            city_filter=request.city_filter,
            days_back=request.days_back,
            include_echo=False
        )

        # Get fold type
        fold_map = {
            'weekly': TimeFold.WEEKLY,
            'monthly': TimeFold.MONTHLY,
            'seasonal': TimeFold.SEASONAL,
            'lunar': TimeFold.LUNAR
        }
        fold_type = fold_map.get(request.fold_type, TimeFold.WEEKLY)

        # Run analysis
        result = engine.temporal_manifold.analyze_fold(
            engine.reviews,
            fold_type
        )

        return result.to_dict()

    except Exception as e:
        logger.error("temporal_analysis_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_chains(request: ComparisonRequest):
    """
    Compare two chains across multiple dimensions

    Compares temporal patterns, causal issues, and overall sentiment.
    """
    try:
        engine, _ = create_singularity_engine_from_db(
            days_back=request.days_back,
            include_echo=False
        )

        # Temporal comparison
        temporal_comparison = engine.temporal_manifold.compare_chains_temporal(
            request.chain_a,
            request.chain_b
        )

        # Causal comparison
        causal_comparison = engine.causal_archaeologist.compare_chains_causal(
            request.chain_a,
            request.chain_b
        )

        # Basic stats
        stats = engine.get_review_stats()

        return {
            'chain_a': request.chain_a,
            'chain_b': request.chain_b,
            'temporal_comparison': temporal_comparison,
            'causal_comparison': causal_comparison,
            'overall_stats': stats
        }

    except Exception as e:
        logger.error("comparison_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prophetic")
async def find_prophetic_reviews(
    chain_filter: Optional[str] = None,
    days_back: int = Query(90, ge=30, le=365)
):
    """
    Find prophetic reviews

    Identifies reviews that predicted future events or trends.
    """
    try:
        engine, _ = create_singularity_engine_from_db(
            chain_filter=chain_filter,
            days_back=days_back,
            include_echo=False
        )

        prophetic = engine.find_prophetic_reviews(lookback_days=days_back)

        return {
            'count': len(prophetic),
            'prophetic_reviews': [p.to_dict() for p in prophetic]
        }

    except Exception as e:
        logger.error("prophetic_search_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/themes")
async def detect_emergent_themes(
    chain_filter: Optional[str] = None,
    min_reviews: int = Query(5, ge=2, le=50),
    growth_threshold: float = Query(0.2, ge=0.0, le=2.0)
):
    """
    Detect emergent themes

    Finds new topics that are gaining traction in reviews.
    """
    try:
        engine, _ = create_singularity_engine_from_db(
            chain_filter=chain_filter,
            include_echo=False
        )

        themes = engine.detect_emergent_themes(
            min_reviews=min_reviews,
            growth_threshold=growth_threshold
        )

        return {
            'count': len(themes),
            'themes': [t.to_dict() for t in themes]
        }

    except Exception as e:
        logger.error("theme_detection_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topology")
async def run_topology_analysis(
    chain_filter: Optional[str] = None,
    city_filter: Optional[str] = None,
    days_back: int = Query(30, ge=7, le=365)
):
    """
    Run topological analysis

    Finds market gaps (holes), clusters, and structural patterns.
    """
    try:
        engine, _ = create_singularity_engine_from_db(
            chain_filter=chain_filter,
            city_filter=city_filter,
            days_back=days_back,
            include_echo=False
        )

        insights = engine.topological_analyzer.analyze(engine.reviews)

        return {
            'count': len(insights),
            'insights': [i.to_dict() for i in insights],
            'summary': {
                'holes': len([i for i in insights if i.feature_type.value == 'hole']),
                'clusters': len([i for i in insights if i.feature_type.value == 'cluster']),
                'voids': len([i for i in insights if i.feature_type.value == 'void']),
                'bridges': len([i for i in insights if i.feature_type.value == 'bridge'])
            }
        }

    except Exception as e:
        logger.error("topology_analysis_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quick/{chain}")
async def quick_analysis(
    chain: str,
    city: Optional[str] = None,
    days: int = Query(14, ge=7, le=90)
):
    """
    Quick analysis for a chain

    Lightweight analysis returning key metrics and signals.
    """
    try:
        engine, _ = create_singularity_engine_from_db(
            chain_filter=chain,
            city_filter=city,
            days_back=days,
            include_echo=False
        )

        # Get basic stats
        stats = engine.get_review_stats()

        # Run lightweight analysis
        result = engine.analyze(
            modules=['temporal'],
            chain_filter=chain,
            city_filter=city
        )

        # Extract key insight
        primary_insight = result.synthesized_insights[0] if result.synthesized_insights else None

        return {
            'chain': chain,
            'city': city,
            'days': days,
            'review_count': stats.get('count', 0),
            'avg_rating': stats.get('avg_rating'),
            'avg_sentiment': stats.get('avg_sentiment'),
            'signal': primary_insight.trading_action.value if primary_insight else 'hold',
            'confidence': primary_insight.confidence_score if primary_insight else 0.5,
            'summary': primary_insight.synthesis if primary_insight else 'Insufficient data'
        }

    except Exception as e:
        logger.error("quick_analysis_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _convert_result_to_response(result: SingularityResult) -> AnalysisResponse:
    """Convert SingularityResult to API response"""
    insights = []
    for insight in result.synthesized_insights:
        insights.append(InsightResponse(
            insight_id=insight.insight_id,
            confidence=insight.confidence.value,
            confidence_score=insight.confidence_score,
            synthesis=insight.synthesis,
            trading_action=insight.trading_action.value,
            trading_confidence=insight.trading_confidence,
            key_drivers=insight.key_drivers,
            warning_signals=insight.warning_signals,
            action_items=insight.action_items,
            risk_factors=insight.risk_factors
        ))

    return AnalysisResponse(
        analysis_id=result.analysis_id,
        status="complete",
        chain_filter=result.chain_filter,
        city_filter=result.city_filter,
        total_reviews=result.total_reviews_analyzed,
        total_locations=result.total_locations_analyzed,
        modules_used=result.modules_used,
        processing_time_ms=result.processing_time_ms,
        overall_confidence=result.overall_confidence,
        insights=insights,
        warnings=result.warnings,
        errors=result.errors
    )


async def _run_analysis_background(
    analysis_id: str,
    request: AnalysisRequest
):
    """Background task for async analysis"""
    try:
        engine, echo = create_singularity_engine_from_db(
            chain_filter=request.chain_filter,
            city_filter=request.city_filter,
            days_back=request.days_back,
            include_echo=request.include_echo
        )

        result = engine.analyze(
            modules=request.modules,
            chain_filter=request.chain_filter,
            city_filter=request.city_filter,
            max_depth=request.max_depth
        )

        response = _convert_result_to_response(result)

        _analysis_results[analysis_id] = {
            'status': 'complete',
            'completed_at': datetime.utcnow().isoformat(),
            'result': response.dict()
        }

    except Exception as e:
        logger.error("background_analysis_failed", analysis_id=analysis_id, error=str(e))
        _analysis_results[analysis_id] = {
            'status': 'failed',
            'error': str(e),
            'failed_at': datetime.utcnow().isoformat()
        }


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE SERVER
# ═══════════════════════════════════════════════════════════════════════════════

def create_app():
    """Create FastAPI app with Singularity router"""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(
        title="Singularity Engine API",
        description="Beyond Human Cognition Analytics for ReviewSignal",
        version="1.0.0"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.get("/")
    async def root():
        return {
            "name": "Singularity Engine",
            "version": "1.0.0",
            "docs": "/docs"
        }

    return app


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8002)
