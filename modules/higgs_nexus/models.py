# HIGGS NEXUS - Data Models
# All dataclasses and enums for the Nexus layer

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any
import numpy as np


# ============================================================================
# ENUMS
# ============================================================================

class MarketPhase(Enum):
    """Market phase states based on Higgs field dynamics"""
    SYMMETRIC = "symmetric"          # Stable, predictable - field at origin
    TRANSITION = "transition"        # Phase transition in progress
    BROKEN_BULLISH = "broken_bullish"   # Symmetry broken - bullish vacuum
    BROKEN_BEARISH = "broken_bearish"   # Symmetry broken - bearish vacuum
    CRITICAL = "critical"            # Near phase transition point
    CHAOTIC = "chaotic"              # Multiple competing phases


class EngineAuthority(Enum):
    """Which engine has primary authority in current phase"""
    ECHO_DOMINANT = "echo_dominant"          # Chaos detection needed
    SINGULARITY_DOMINANT = "singularity"     # Pattern analysis needed
    BALANCED = "balanced"                     # Equal weight
    NEXUS_OVERRIDE = "nexus_override"        # Nexus takes control


class NodeState(Enum):
    """State of a swarm node"""
    ACTIVE = "active"
    HIBERNATING = "hibernating"
    SPAWNING = "spawning"
    TERMINATING = "terminating"


class TransitionType(Enum):
    """Type of phase transition"""
    FIRST_ORDER = "first_order"      # Abrupt, discontinuous
    SECOND_ORDER = "second_order"    # Smooth, continuous
    CROSSOVER = "crossover"          # Gradual shift


# ============================================================================
# FIELD DYNAMICS MODELS
# ============================================================================

@dataclass
class FieldPotential:
    """Mexican hat potential state"""
    position: np.ndarray              # Current field position
    potential_value: float            # V(φ) at current position
    gradient: np.ndarray              # ∇V(φ) - direction of steepest descent
    curvature: float                  # Local curvature (mass term)
    distance_from_minimum: float      # Distance to nearest vacuum
    vacuum_expectation_value: float   # v = √(μ²/λ)

    def is_at_origin(self, threshold: float = 0.1) -> bool:
        """Check if field is near symmetric point"""
        return np.linalg.norm(self.position) < threshold * self.vacuum_expectation_value

    def is_in_vacuum(self, threshold: float = 0.1) -> bool:
        """Check if field is near a vacuum state"""
        return self.distance_from_minimum < threshold * self.vacuum_expectation_value


@dataclass
class FieldState:
    """Complete state of the Higgs field"""
    potential: FieldPotential
    phase: MarketPhase
    temperature: float                # Effective temperature (volatility)
    critical_temperature: float       # Tc where phase transition occurs
    order_parameter: float            # 0 = symmetric, 1 = fully broken
    susceptibility: float             # Response to perturbations
    correlation_length: float         # Spatial correlation of fluctuations
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_critical(self) -> bool:
        """Check if near critical point"""
        return abs(self.temperature - self.critical_temperature) / self.critical_temperature < 0.1

    @property
    def phase_stability(self) -> float:
        """0 = unstable, 1 = stable"""
        if self.phase == MarketPhase.TRANSITION:
            return 0.2
        elif self.phase == MarketPhase.CRITICAL:
            return 0.3
        elif self.phase == MarketPhase.CHAOTIC:
            return 0.1
        else:
            return min(1.0, 0.5 + 0.5 * (1 - self.susceptibility))


@dataclass
class SymmetryBreaking:
    """Details of symmetry breaking event"""
    occurred: bool
    direction: str                    # "bullish" or "bearish"
    magnitude: float                  # Strength of breaking
    trigger_time: Optional[datetime]
    trigger_location: Optional[str]   # Location ID that triggered
    trigger_chain: Optional[str]      # Chain that triggered
    cascade_risk: float               # 0-1, risk of cascade


# ============================================================================
# PHASE TRANSITION MODELS
# ============================================================================

@dataclass
class PhaseTransition:
    """Detected or predicted phase transition"""
    transition_type: TransitionType
    from_phase: MarketPhase
    to_phase: MarketPhase
    probability: float                # 0-1
    estimated_time_hours: Optional[float]
    driving_factors: List[str]
    affected_chains: List[str]
    affected_cities: List[str]
    confidence: float

    @property
    def is_imminent(self) -> bool:
        return self.probability > 0.7 and (
            self.estimated_time_hours is None or
            self.estimated_time_hours < 24
        )


@dataclass
class PhaseState:
    """Complete phase state of the market"""
    current_phase: MarketPhase
    field_state: FieldState
    pending_transition: Optional[PhaseTransition]
    phase_history: List[Dict[str, Any]] = field(default_factory=list)
    stability_score: float = 0.5

    def add_history(self, phase: MarketPhase, timestamp: datetime):
        self.phase_history.append({
            "phase": phase.value,
            "timestamp": timestamp.isoformat()
        })
        # Keep last 100 entries
        if len(self.phase_history) > 100:
            self.phase_history = self.phase_history[-100:]


# ============================================================================
# SWARM MODELS
# ============================================================================

@dataclass
class SwarmMetrics:
    """Metrics from the swarm coordinator"""
    active_nodes: int
    hibernating_nodes: int
    total_nodes: int
    cpu_usage_percent: float
    ram_usage_gb: float
    average_node_energy: float
    collective_intelligence_score: float
    convergence_rate: float           # How fast swarm reaches consensus
    diversity_index: float            # Variance in node opinions

    @property
    def health_score(self) -> float:
        """Overall swarm health 0-1"""
        cpu_health = max(0, 1 - self.cpu_usage_percent / 100)
        ram_health = max(0, 1 - self.ram_usage_gb / 8)  # Assume 8GB limit
        node_ratio = self.active_nodes / max(1, self.total_nodes)
        return (cpu_health + ram_health + node_ratio + self.collective_intelligence_score) / 4


# ============================================================================
# SIGNAL MODELS
# ============================================================================

@dataclass
class EngineContribution:
    """Contribution from a single engine"""
    engine_name: str                  # "echo" or "singularity"
    signal_strength: float            # -1 (bearish) to 1 (bullish)
    confidence: float                 # 0-1
    weight: float                     # Assigned weight in current phase
    key_insights: List[str]
    risk_factors: List[str]
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ArbitratedSignal:
    """Final arbitrated signal from Nexus"""
    # Core signal
    action: str                       # STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL
    confidence: float                 # 0-1
    signal_strength: float            # -1 to 1

    # Engine contributions
    echo_contribution: EngineContribution
    singularity_contribution: EngineContribution
    authority: EngineAuthority

    # Phase context
    market_phase: MarketPhase
    phase_adjusted: bool              # Was signal adjusted due to phase?
    phase_adjustment_reason: Optional[str]

    # Swarm consensus
    swarm_consensus: float            # 0-1, how much swarm agrees
    swarm_dissent_reasons: List[str]

    # Meta
    timestamp: datetime = field(default_factory=datetime.now)
    nexus_version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "confidence": self.confidence,
            "signal_strength": self.signal_strength,
            "market_phase": self.market_phase.value,
            "authority": self.authority.value,
            "echo_weight": self.echo_contribution.weight,
            "singularity_weight": self.singularity_contribution.weight,
            "swarm_consensus": self.swarm_consensus,
            "phase_adjusted": self.phase_adjusted,
            "timestamp": self.timestamp.isoformat()
        }


# ============================================================================
# NEXUS INSIGHT
# ============================================================================

@dataclass
class NexusInsight:
    """Complete insight from Higgs Nexus"""
    insight_id: str
    timestamp: datetime

    # Phase analysis
    phase_state: PhaseState
    symmetry_breaking: Optional[SymmetryBreaking]

    # Arbitrated signal
    signal: ArbitratedSignal

    # Swarm metrics
    swarm_metrics: SwarmMetrics

    # Actionable intelligence
    primary_recommendation: str
    risk_assessment: str              # LOW, MEDIUM, HIGH, CRITICAL
    action_items: List[str]
    watch_list: List[str]             # Things to monitor

    # Narrative
    market_narrative: str             # Human-readable summary
    technical_details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "timestamp": self.timestamp.isoformat(),
            "phase": self.phase_state.current_phase.value,
            "signal": self.signal.to_dict(),
            "recommendation": self.primary_recommendation,
            "risk": self.risk_assessment,
            "narrative": self.market_narrative,
            "action_items": self.action_items,
            "watch_list": self.watch_list
        }


# ============================================================================
# NEXUS HEALTH
# ============================================================================

@dataclass
class NexusHealth:
    """Health status of the entire Nexus system"""
    status: str                       # "healthy", "degraded", "critical"
    uptime_seconds: float

    # Component health
    echo_engine_healthy: bool
    singularity_engine_healthy: bool
    phase_detector_healthy: bool
    swarm_coordinator_healthy: bool

    # Resource usage
    cpu_percent: float
    ram_gb: float

    # Performance
    avg_latency_ms: float
    signals_per_minute: float

    # Warnings
    warnings: List[str]

    @property
    def all_healthy(self) -> bool:
        return all([
            self.echo_engine_healthy,
            self.singularity_engine_healthy,
            self.phase_detector_healthy,
            self.swarm_coordinator_healthy
        ])
