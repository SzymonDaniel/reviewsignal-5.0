# ═══════════════════════════════════════════════════════════════════════════════
# SINGULARITY ENGINE - Data Models
# All dataclasses, enums, and type definitions
# ═══════════════════════════════════════════════════════════════════════════════

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Optional, Any, Tuple, Union
from datetime import datetime
import numpy as np


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class TimeFold(Enum):
    """Types of temporal folding for pattern detection"""
    WEEKLY = "weekly"               # All Mondays together, all Tuesdays together...
    MONTHLY = "monthly"             # All 1st of month together, all 15th together...
    SEASONAL = "seasonal"           # Q1, Q2, Q3, Q4
    LUNAR = "lunar"                 # Moon phases (new, waxing, full, waning)
    EVENT_ALIGNED = "event_aligned" # Days relative to events (earnings, launches)
    COMPETITIVE = "competitive"     # Days relative to competitor actions


class ResonanceType(Enum):
    """Types of semantic resonance detected between reviews"""
    CROSS_BRAND = "cross_brand"     # Different brands, similar sentiment patterns
    CROSS_CITY = "cross_city"       # Different cities, similar patterns
    PROPHETIC = "prophetic"         # Reviews that predicted future events
    EMERGENT = "emergent"           # Unexpected theme correlations


class CausalLevel(Enum):
    """Depth levels in causal archaeology"""
    SYMPTOM = 0        # Level 0: Observable effect (rating dropped)
    PROXIMATE = 1      # Level 1: Immediate cause (bad service)
    INTERMEDIATE = 2   # Level 2-3: Behind the scenes (staff issues)
    STRUCTURAL = 3     # Level 4-5: Organizational (management, budget)
    SYSTEMIC = 4       # Level 6: Industry-wide (sector pressure)
    MACRO = 5          # Level 7+: Macro-economic forces


class TopologyFeature(Enum):
    """Topological features detected in data"""
    HOLE = "hole"           # Missing pattern (gap in data)
    CLUSTER = "cluster"     # Dense region (H0 feature)
    LOOP = "loop"           # Cyclic pattern (H1 feature)
    VOID = "void"           # Empty region (H2 feature)
    BRIDGE = "bridge"       # Connecting structure


class InsightConfidence(Enum):
    """Confidence levels for synthesized insights"""
    LOW = "low"                     # 1 module agrees (< 50%)
    MEDIUM = "medium"               # 2 modules agree (50-70%)
    HIGH = "high"                   # 3 modules agree (70-85%)
    VERY_HIGH = "very_high"         # 4+ modules agree (85%+)


class TradingAction(Enum):
    """Trading recommendations"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SingularityConfig:
    """Configuration for Singularity Engine"""
    # Temporal Manifold settings
    temporal_lookback_days: int = 90
    temporal_min_samples: int = 10
    temporal_anomaly_threshold: float = 2.0  # Z-score threshold

    # Semantic Resonance settings
    semantic_min_similarity: float = 0.75
    semantic_embedding_model: str = "all-MiniLM-L6-v2"
    semantic_batch_size: int = 64
    semantic_max_reviews: int = 10000

    # Causal Archaeology settings
    causal_max_depth: int = 7
    causal_min_evidence: int = 3
    causal_confidence_threshold: float = 0.5
    causal_use_llm: bool = True

    # Topological Analysis settings
    topology_max_dimension: int = 2
    topology_persistence_threshold: float = 0.1
    topology_use_ripser: bool = True

    # Integration settings
    convergence_threshold: float = 0.7
    min_modules_for_high_confidence: int = 3

    # Performance settings
    max_processing_time_seconds: int = 300
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════════
# INPUT DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReviewData:
    """Standardized review data for Singularity Engine"""
    review_id: str
    location_id: str
    text: str
    rating: float                   # 1-5 scale
    sentiment_score: Optional[float] = None  # -1 to 1
    sentiment_label: Optional[str] = None    # positive/negative/neutral
    topics: List[str] = field(default_factory=list)
    review_time: Optional[datetime] = None
    chain_id: Optional[str] = None
    city: Optional[str] = None
    location_name: Optional[str] = None
    embedding: Optional[np.ndarray] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.review_time:
            result['review_time'] = self.review_time.isoformat()
        if self.embedding is not None:
            result['embedding'] = None  # Don't serialize large embeddings
        return result


@dataclass
class EventData:
    """External event data for temporal alignment"""
    event_id: str
    event_type: str                 # earnings, product_launch, competitor_action
    chain_id: Optional[str] = None
    event_date: datetime = None
    description: Optional[str] = None
    impact_score: Optional[float] = None  # -1 to 1

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.event_date:
            result['event_date'] = self.event_date.isoformat()
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPORAL MANIFOLD MODELS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TemporalPattern:
    """Pattern detected in folded time"""
    pattern_id: str
    fold_type: TimeFold
    fold_key: str                   # e.g., "Monday", "Q1", "lunar_full", "-5_days"
    mean_sentiment: float
    std_sentiment: float
    sample_count: int
    baseline_mean: float            # Overall mean for comparison
    baseline_std: float             # Overall std for comparison
    deviation_from_baseline: float  # Difference from overall mean
    z_score: float                  # Statistical significance
    is_anomaly: bool
    trend_direction: str = "stable" # up, down, stable
    peak_periods: List[str] = field(default_factory=list)
    trough_periods: List[str] = field(default_factory=list)
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['fold_type'] = self.fold_type.value
        return data


@dataclass
class TemporalFoldResult:
    """Complete result from temporal folding"""
    fold_type: TimeFold
    patterns: List[TemporalPattern]
    anomaly_count: int
    strongest_pattern: Optional[TemporalPattern]
    insight_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'fold_type': self.fold_type.value,
            'patterns': [p.to_dict() for p in self.patterns],
            'anomaly_count': self.anomaly_count,
            'strongest_pattern': self.strongest_pattern.to_dict() if self.strongest_pattern else None,
            'insight_summary': self.insight_summary
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SEMANTIC RESONANCE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SemanticResonance:
    """Detected resonance between reviews"""
    resonance_id: str
    resonance_type: ResonanceType
    source_review_ids: List[str]
    target_review_ids: List[str]
    cosine_similarity: float
    temporal_lag_days: int          # Days between source and target
    brand_a: Optional[str] = None
    brand_b: Optional[str] = None
    city_a: Optional[str] = None
    city_b: Optional[str] = None
    shared_themes: List[str] = field(default_factory=list)
    predicted_outcome: Optional[str] = None
    prediction_confidence: float = 0.0
    evidence_text_snippets: List[str] = field(default_factory=list)
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['resonance_type'] = self.resonance_type.value
        return data


@dataclass
class PropheticReview:
    """Review that predicted a future event"""
    review_id: str
    review_text: str
    review_date: datetime
    predicted_event: str
    event_date: datetime
    lead_time_days: int
    prediction_accuracy: float      # How accurate was the prediction
    similar_current_reviews: int    # Count of similar reviews now
    chain_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['review_date'] = self.review_date.isoformat()
        data['event_date'] = self.event_date.isoformat()
        return data


@dataclass
class EmergentTheme:
    """Theme that emerged from clustering"""
    theme_id: str
    keywords: List[str]
    review_count: int
    avg_sentiment: float
    growth_rate: float              # Change over time
    representative_reviews: List[str]
    related_chains: List[str]
    related_cities: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════════
# CAUSAL ARCHAEOLOGY MODELS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CausalNode:
    """Single node in causal graph"""
    node_id: str
    level: CausalLevel
    description: str
    evidence_count: int             # Number of reviews supporting this
    confidence: float               # 0-1 confidence in this cause
    source_reviews: List[str] = field(default_factory=list)  # Review IDs
    extracted_quotes: List[str] = field(default_factory=list)
    inferred: bool = False          # True if inferred by LLM, not from reviews

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['level'] = self.level.value
        return data


@dataclass
class CausalEdge:
    """Edge connecting two causal nodes"""
    source_id: str
    target_id: str
    weight: float                   # Strength of causal relationship
    evidence: str                   # Description of evidence

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CausalGraph:
    """Complete causal archaeology result"""
    graph_id: str
    root_symptom: str               # The symptom we're investigating
    max_depth_reached: int
    nodes: Dict[str, CausalNode]
    edges: List[CausalEdge]
    critical_path: List[str]        # Node IDs of most significant chain
    root_causes: List[str]          # Node IDs at deepest level
    total_evidence_count: int
    overall_confidence: float
    insight_summary: str
    computed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'graph_id': self.graph_id,
            'root_symptom': self.root_symptom,
            'max_depth_reached': self.max_depth_reached,
            'nodes': {k: v.to_dict() for k, v in self.nodes.items()},
            'edges': [e.to_dict() for e in self.edges],
            'critical_path': self.critical_path,
            'root_causes': self.root_causes,
            'total_evidence_count': self.total_evidence_count,
            'overall_confidence': self.overall_confidence,
            'insight_summary': self.insight_summary,
            'computed_at': self.computed_at
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TOPOLOGICAL ANALYSIS MODELS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PersistencePair:
    """Single persistence pair from TDA"""
    birth: float
    death: float
    persistence: float              # death - birth
    dimension: int                  # H0, H1, H2

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TopologicalInsight:
    """Interpreted topological feature"""
    insight_id: str
    feature_type: TopologyFeature
    dimension: int                  # 0 = clusters, 1 = loops/holes, 2 = voids
    persistence: float              # How significant the feature is
    birth: float
    death: float
    significance: float             # Normalized significance score
    interpretation: str             # Human-readable explanation
    business_meaning: str           # What this means for business
    affected_locations: List[str] = field(default_factory=list)
    opportunity_score: float = 0.0  # For holes: opportunity magnitude
    risk_score: float = 0.0         # For holes: risk magnitude
    recommended_action: Optional[str] = None
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['feature_type'] = self.feature_type.value
        return data


# ═══════════════════════════════════════════════════════════════════════════════
# SYNTHESIZED INSIGHT MODELS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ModuleContribution:
    """Contribution from a single analysis module"""
    module_name: str                # temporal, semantic, causal, topology
    signal_strength: float          # -1 to 1 (bearish to bullish)
    confidence: float               # 0 to 1
    key_finding: str
    supporting_evidence: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SingularityInsight:
    """Synthesized insight from multiple modules"""
    insight_id: str
    confidence: InsightConfidence
    confidence_score: float         # Numeric 0-1
    contributing_modules: List[ModuleContribution]

    # Component insights (optional, for detail)
    temporal_patterns: List[TemporalPattern] = field(default_factory=list)
    semantic_resonances: List[SemanticResonance] = field(default_factory=list)
    causal_summary: Optional[str] = None
    topological_insights: List[TopologicalInsight] = field(default_factory=list)

    # Echo Engine integration
    echo_butterfly_coefficient: Optional[float] = None
    echo_system_stability: Optional[str] = None

    # Synthesis
    synthesis: str = ""             # Human-readable synthesis of all findings
    key_drivers: List[str] = field(default_factory=list)
    warning_signals: List[str] = field(default_factory=list)

    # Recommendations
    trading_action: TradingAction = TradingAction.HOLD
    trading_confidence: float = 0.5
    action_items: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)

    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'insight_id': self.insight_id,
            'confidence': self.confidence.value,
            'confidence_score': round(self.confidence_score, 4),
            'contributing_modules': [m.to_dict() for m in self.contributing_modules],
            'temporal_patterns': [p.to_dict() for p in self.temporal_patterns],
            'semantic_resonances': [r.to_dict() for r in self.semantic_resonances],
            'causal_summary': self.causal_summary,
            'topological_insights': [t.to_dict() for t in self.topological_insights],
            'echo_butterfly_coefficient': self.echo_butterfly_coefficient,
            'echo_system_stability': self.echo_system_stability,
            'synthesis': self.synthesis,
            'key_drivers': self.key_drivers,
            'warning_signals': self.warning_signals,
            'trading_action': self.trading_action.value,
            'trading_confidence': round(self.trading_confidence, 4),
            'action_items': self.action_items,
            'risk_factors': self.risk_factors,
            'generated_at': self.generated_at
        }


# ═══════════════════════════════════════════════════════════════════════════════
# FINAL RESULT MODEL
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SingularityResult:
    """Complete result from Singularity Engine analysis"""
    analysis_id: str
    chain_filter: Optional[str]
    city_filter: Optional[str]
    analysis_period_days: int

    # Module results
    temporal_results: List[TemporalFoldResult] = field(default_factory=list)
    semantic_resonances: List[SemanticResonance] = field(default_factory=list)
    prophetic_reviews: List[PropheticReview] = field(default_factory=list)
    emergent_themes: List[EmergentTheme] = field(default_factory=list)
    causal_graphs: List[CausalGraph] = field(default_factory=list)
    topological_insights: List[TopologicalInsight] = field(default_factory=list)

    # Synthesized output
    synthesized_insights: List[SingularityInsight] = field(default_factory=list)

    # Metrics
    overall_confidence: float = 0.0
    modules_used: List[str] = field(default_factory=list)
    total_reviews_analyzed: int = 0
    total_locations_analyzed: int = 0
    processing_time_ms: int = 0

    # Status
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    computed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'analysis_id': self.analysis_id,
            'chain_filter': self.chain_filter,
            'city_filter': self.city_filter,
            'analysis_period_days': self.analysis_period_days,
            'temporal_results': [t.to_dict() for t in self.temporal_results],
            'semantic_resonances': [s.to_dict() for s in self.semantic_resonances],
            'prophetic_reviews': [p.to_dict() for p in self.prophetic_reviews],
            'emergent_themes': [e.to_dict() for e in self.emergent_themes],
            'causal_graphs': [g.to_dict() for g in self.causal_graphs],
            'topological_insights': [t.to_dict() for t in self.topological_insights],
            'synthesized_insights': [i.to_dict() for i in self.synthesized_insights],
            'overall_confidence': round(self.overall_confidence, 4),
            'modules_used': self.modules_used,
            'total_reviews_analyzed': self.total_reviews_analyzed,
            'total_locations_analyzed': self.total_locations_analyzed,
            'processing_time_ms': self.processing_time_ms,
            'warnings': self.warnings,
            'errors': self.errors,
            'computed_at': self.computed_at
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TYPE ALIASES
# ═══════════════════════════════════════════════════════════════════════════════

# For type hints
EmbeddingVector = np.ndarray
PersistenceDiagram = Dict[int, np.ndarray]
FoldedData = Dict[str, List[ReviewData]]
