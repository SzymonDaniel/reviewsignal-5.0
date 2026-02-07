# HIGGS NEXUS Layer v1.0
# Orchestration layer connecting Echo Engine and Singularity Engine
# with phase transition detection and adaptive signal weighting

from .core import HiggsNexus, NexusConfig
from .phase_detector import PhaseDetector, MarketPhase, PhaseTransition
from .field_dynamics import HiggsField, FieldState, SymmetryBreaking
from .swarm_coordinator import SwarmCoordinator, NexusNode, NodePool
from .signal_arbiter import SignalArbiter, ArbitratedSignal
from .models import (
    NexusInsight,
    PhaseState,
    FieldPotential,
    SwarmMetrics,
    NexusHealth,
)

__all__ = [
    # Core
    "HiggsNexus",
    "NexusConfig",
    # Phase Detection
    "PhaseDetector",
    "MarketPhase",
    "PhaseTransition",
    # Field Dynamics
    "HiggsField",
    "FieldState",
    "SymmetryBreaking",
    # Swarm Coordination
    "SwarmCoordinator",
    "NexusNode",
    "NodePool",
    # Signal Arbitration
    "SignalArbiter",
    "ArbitratedSignal",
    # Models
    "NexusInsight",
    "PhaseState",
    "FieldPotential",
    "SwarmMetrics",
    "NexusHealth",
]

__version__ = "1.0.0"
