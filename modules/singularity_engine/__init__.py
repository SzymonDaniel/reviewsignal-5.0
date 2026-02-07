# ═══════════════════════════════════════════════════════════════════════════════
# SINGULARITY ENGINE - Emergent Causality Matrix
# Advanced analytics combining temporal, semantic, causal, and topological analysis
# Created for ReviewSignal by Claude AI
# ═══════════════════════════════════════════════════════════════════════════════

"""
Singularity Engine - Beyond Human Cognition Analytics

This module provides advanced analytics capabilities:
- Temporal Manifold: Fold time to find hidden patterns
- Semantic Resonance: Detect unexpected correlations between reviews
- Causal Archaeology: Dig deep into root causes (7+ levels)
- Topological Analysis: Find "holes" in data representing opportunities/risks

Usage:
    from modules.singularity_engine import (
        SingularityEngine,
        create_singularity_engine_from_db,
        TimeFold,
        SingularityResult
    )

    # Create engine from database
    engine, echo = create_singularity_engine_from_db(
        chain_filter="starbucks",
        include_echo=True
    )

    # Run full analysis
    result = engine.analyze(
        modules=['temporal', 'semantic', 'causal', 'topology'],
        max_depth=7
    )

    # Get synthesized insights
    for insight in result.synthesized_insights:
        print(f"[{insight.confidence.value}] {insight.synthesis}")
"""

from .models import (
    # Enums
    TimeFold,
    ResonanceType,
    CausalLevel,
    TopologyFeature,
    InsightConfidence,
    # Dataclasses
    TemporalPattern,
    SemanticResonance,
    CausalNode,
    CausalGraph,
    TopologicalInsight,
    SingularityInsight,
    SingularityResult,
    SingularityConfig,
    ReviewData,
)

from .core import (
    SingularityEngine,
    create_singularity_engine_from_db,
)

from .temporal_manifold import TemporalManifold
from .semantic_resonance import SemanticResonanceField
from .causal_archaeology import CausalArchaeologist
from .topological_analyzer import TopologicalAnalyzer
from .integration import EchoSingularityIntegration
from .signal_synthesizer import SignalSynthesizer

__all__ = [
    # Main Engine
    'SingularityEngine',
    'create_singularity_engine_from_db',
    # Enums
    'TimeFold',
    'ResonanceType',
    'CausalLevel',
    'TopologyFeature',
    'InsightConfidence',
    # Dataclasses
    'TemporalPattern',
    'SemanticResonance',
    'CausalNode',
    'CausalGraph',
    'TopologicalInsight',
    'SingularityInsight',
    'SingularityResult',
    'SingularityConfig',
    'ReviewData',
    # Components
    'TemporalManifold',
    'SemanticResonanceField',
    'CausalArchaeologist',
    'TopologicalAnalyzer',
    'EchoSingularityIntegration',
    'SignalSynthesizer',
]

__version__ = '1.0.0'
__author__ = 'Claude AI for ReviewSignal'
