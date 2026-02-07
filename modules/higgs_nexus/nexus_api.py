# HIGGS NEXUS - REST API
# FastAPI router for Nexus endpoints

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from .core import HiggsNexus, NexusConfig
from .models import MarketPhase

logger = logging.getLogger("HiggsNexus.API")

# Create router
router = APIRouter(prefix="/nexus", tags=["Higgs Nexus"])

# Global Nexus instance (initialized on startup)
_nexus: Optional[HiggsNexus] = None


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class AnalyzeRequest(BaseModel):
    """Request model for /nexus/analyze"""
    echo_results: Dict[str, Any] = Field(
        ...,
        description="Results from Echo Engine",
        example={
            "signal": "HOLD",
            "confidence": 0.7,
            "chaos_index": 1.5,
            "butterfly_coefficient": 0.4,
            "stability": "stable",
            "insights": ["System stable", "Low propagation risk"],
            "risk_factors": []
        }
    )
    singularity_results: Dict[str, Any] = Field(
        ...,
        description="Results from Singularity Engine",
        example={
            "trading_action": "BUY",
            "confidence": 0.65,
            "signal_strength": 0.3,
            "insights": ["Positive temporal trend", "Strong semantic resonance"],
            "risk_factors": ["Volatility increasing"],
            "patterns": ["weekly_positive"]
        }
    )
    market_data: Dict[str, Any] = Field(
        ...,
        description="Market data for analysis",
        example={
            "location_sentiments": {"loc1": 0.5, "loc2": 0.3},
            "chain_sentiments": {"starbucks": 0.4, "mcdonalds": 0.2},
            "ratings": [4.2, 4.5, 3.8],
            "volatility": 0.12
        }
    )


class NexusInsightResponse(BaseModel):
    """Response model for analysis results"""
    insight_id: str
    timestamp: str
    phase: str
    signal: Dict[str, Any]
    recommendation: str
    risk: str
    narrative: str
    action_items: List[str]
    watch_list: List[str]


class PhaseStateResponse(BaseModel):
    """Response model for phase state"""
    current_phase: str
    stability_score: float
    pending_transition: Optional[Dict[str, Any]]
    field_summary: Dict[str, Any]


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    uptime_seconds: float
    cpu_percent: float
    ram_gb: float
    components: Dict[str, bool]
    warnings: List[str]


class SwarmMetricsResponse(BaseModel):
    """Response model for swarm metrics"""
    active_nodes: int
    hibernating_nodes: int
    total_nodes: int
    cpu_usage_percent: float
    ram_usage_gb: float
    collective_intelligence_score: float
    health_score: float


# ============================================================================
# LIFECYCLE ENDPOINTS
# ============================================================================

@router.on_event("startup")
async def startup():
    """Initialize Nexus on API startup"""
    global _nexus
    _nexus = HiggsNexus(config=NexusConfig())
    await _nexus.start()
    logger.info("Nexus API started")


@router.on_event("shutdown")
async def shutdown():
    """Cleanup on API shutdown"""
    global _nexus
    if _nexus:
        _nexus.stop()
    logger.info("Nexus API shutdown")


def get_nexus() -> HiggsNexus:
    """Get the Nexus instance"""
    if _nexus is None:
        raise HTTPException(status_code=503, detail="Nexus not initialized")
    return _nexus


# ============================================================================
# ANALYSIS ENDPOINTS
# ============================================================================

@router.post("/analyze", response_model=NexusInsightResponse)
async def analyze(request: AnalyzeRequest):
    """
    Main analysis endpoint - combines Echo and Singularity results.

    Returns unified insight with:
    - Arbitrated trading signal
    - Phase analysis
    - Risk assessment
    - Action items
    """
    nexus = get_nexus()

    try:
        insight = await nexus.analyze(
            echo_results=request.echo_results,
            singularity_results=request.singularity_results,
            market_data=request.market_data
        )

        return NexusInsightResponse(
            insight_id=insight.insight_id,
            timestamp=insight.timestamp.isoformat(),
            phase=insight.phase_state.current_phase.value,
            signal=insight.signal.to_dict(),
            recommendation=insight.primary_recommendation,
            risk=insight.risk_assessment,
            narrative=insight.market_narrative,
            action_items=insight.action_items,
            watch_list=insight.watch_list
        )

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/phase", response_model=PhaseStateResponse)
async def get_phase():
    """
    Get current market phase state.

    Returns:
    - Current phase (symmetric, transition, broken_bullish, etc.)
    - Stability score
    - Any pending transitions
    - Field dynamics summary
    """
    nexus = get_nexus()

    phase_state = nexus._current_phase_state
    if phase_state is None:
        raise HTTPException(
            status_code=404,
            detail="No phase state available - run analysis first"
        )

    return PhaseStateResponse(
        current_phase=phase_state.current_phase.value,
        stability_score=phase_state.stability_score,
        pending_transition=phase_state.pending_transition.__dict__ if phase_state.pending_transition else None,
        field_summary=nexus.phase_detector.get_phase_summary()
    )


@router.get("/insights", response_model=List[Dict[str, Any]])
async def get_insights(count: int = 10):
    """
    Get recent insights history.

    Args:
        count: Number of recent insights to return (default 10, max 100)
    """
    nexus = get_nexus()
    count = min(count, 100)
    return nexus.get_recent_insights(count)


# ============================================================================
# SWARM ENDPOINTS
# ============================================================================

@router.get("/swarm/metrics", response_model=SwarmMetricsResponse)
async def get_swarm_metrics():
    """
    Get current swarm metrics.

    Returns node counts, resource usage, and collective intelligence score.
    """
    nexus = get_nexus()

    if nexus.swarm is None:
        raise HTTPException(status_code=404, detail="Swarm not enabled")

    metrics = nexus.swarm.get_metrics()

    return SwarmMetricsResponse(
        active_nodes=metrics.active_nodes,
        hibernating_nodes=metrics.hibernating_nodes,
        total_nodes=metrics.total_nodes,
        cpu_usage_percent=metrics.cpu_usage_percent,
        ram_usage_gb=metrics.ram_usage_gb,
        collective_intelligence_score=metrics.collective_intelligence_score,
        health_score=metrics.health_score
    )


@router.post("/swarm/scale")
async def scale_swarm(target_nodes: int):
    """
    Manually scale the swarm to target node count.

    Args:
        target_nodes: Desired number of active nodes
    """
    nexus = get_nexus()

    if nexus.swarm is None:
        raise HTTPException(status_code=404, detail="Swarm not enabled")

    current = len(nexus.swarm.pool.active)

    if target_nodes > current:
        # Scale up
        for _ in range(target_nodes - current):
            if nexus.swarm.pool.hibernating:
                node_id = next(iter(nexus.swarm.pool.hibernating.keys()))
                nexus.swarm.pool.wake_node(node_id)
            else:
                nexus.swarm.pool.spawn()
    elif target_nodes < current:
        # Scale down
        for _ in range(current - target_nodes):
            if len(nexus.swarm.pool.active) > nexus.swarm.config.min_active_nodes:
                lowest = min(nexus.swarm.pool.active.values(), key=lambda n: n.energy)
                nexus.swarm.pool.hibernate_node(lowest.node_id)

    return {
        "previous_count": current,
        "new_count": len(nexus.swarm.pool.active),
        "target": target_nodes
    }


# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns overall status and component health.
    """
    nexus = get_nexus()
    health = nexus.get_health()

    return HealthResponse(
        status=health.status,
        uptime_seconds=health.uptime_seconds,
        cpu_percent=health.cpu_percent,
        ram_gb=health.ram_gb,
        components={
            "echo_engine": health.echo_engine_healthy,
            "singularity_engine": health.singularity_engine_healthy,
            "phase_detector": health.phase_detector_healthy,
            "swarm_coordinator": health.swarm_coordinator_healthy
        },
        warnings=health.warnings
    )


@router.get("/status")
async def get_status():
    """
    Get detailed Nexus status.
    """
    nexus = get_nexus()
    health = nexus.get_health()

    return {
        "nexus_version": "1.0.0",
        "status": health.status,
        "is_running": nexus._is_running,
        "current_phase": nexus.get_current_phase().value if nexus.get_current_phase() else None,
        "insights_count": len(nexus._insights_history),
        "uptime_seconds": health.uptime_seconds,
        "resource_usage": {
            "cpu_percent": health.cpu_percent,
            "ram_gb": health.ram_gb
        },
        "arbiter_stats": nexus.signal_arbiter.get_arbitration_stats(),
        "phase_summary": nexus.phase_detector.get_phase_summary()
    }


# ============================================================================
# INTEGRATION HELPER
# ============================================================================

def create_nexus_router(nexus_instance: Optional[HiggsNexus] = None) -> APIRouter:
    """
    Create router with optional pre-initialized Nexus instance.

    Use this when integrating with existing FastAPI app that already
    has database connections and other services.
    """
    global _nexus
    if nexus_instance:
        _nexus = nexus_instance
    return router
