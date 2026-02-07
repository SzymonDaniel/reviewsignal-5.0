# HIGGS NEXUS - Core Orchestrator
# Main class that coordinates all Nexus components

import asyncio
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import uuid
import logging
import psutil

from .models import (
    MarketPhase,
    NexusInsight,
    NexusHealth,
    PhaseState,
    ArbitratedSignal,
    SwarmMetrics,
    SymmetryBreaking,
)
from .phase_detector import PhaseDetector, PhaseDetectorConfig
from .field_dynamics import HiggsFieldConfig
from .swarm_coordinator import SwarmCoordinator, SwarmConfig
from .signal_arbiter import SignalArbiter, ArbiterConfig

logger = logging.getLogger("HiggsNexus")


@dataclass
class NexusConfig:
    """Master configuration for Higgs Nexus"""
    # Component configs
    phase_config: Optional[PhaseDetectorConfig] = None
    field_config: Optional[HiggsFieldConfig] = None
    swarm_config: Optional[SwarmConfig] = None
    arbiter_config: Optional[ArbiterConfig] = None

    # Nexus settings
    tick_interval_sec: float = 1.0
    max_insights_history: int = 100
    enable_swarm: bool = True
    initial_swarm_nodes: int = 10

    # Resource limits
    max_cpu_percent: float = 60.0
    max_ram_gb: float = 4.0

    # Logging
    log_level: str = "INFO"


class HiggsNexus:
    """
    HIGGS NEXUS - Quantum Field Intelligence Orchestration Layer

    This is the main class that coordinates:
    - Phase detection using Mexican hat potential dynamics
    - Swarm-based collective intelligence
    - Signal arbitration between Echo and Singularity engines

    Usage:
        nexus = HiggsNexus()
        await nexus.start()

        # Process market data
        insight = await nexus.analyze(
            echo_results={...},
            singularity_results={...},
            market_data={...}
        )

        nexus.stop()
    """

    def __init__(self, config: Optional[NexusConfig] = None):
        self.config = config or NexusConfig()
        self._setup_logging()

        # Initialize components
        self.phase_detector = PhaseDetector(
            config=self.config.phase_config,
            field_config=self.config.field_config
        )
        self.signal_arbiter = SignalArbiter(
            config=self.config.arbiter_config
        )

        # Swarm is optional
        self.swarm: Optional[SwarmCoordinator] = None
        if self.config.enable_swarm:
            self.swarm = SwarmCoordinator(
                config=self.config.swarm_config
            )

        # State
        self._is_running = False
        self._start_time: Optional[datetime] = None
        self._insights_history: List[NexusInsight] = []
        self._current_phase_state: Optional[PhaseState] = None
        self._last_symmetry_breaking: Optional[SymmetryBreaking] = None

        # Callbacks
        self._on_phase_change: Optional[Callable] = None
        self._on_symmetry_breaking: Optional[Callable] = None

        logger.info("HiggsNexus initialized")

    def _setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    async def start(self):
        """Start the Nexus system"""
        self._is_running = True
        self._start_time = datetime.now()

        # Start swarm if enabled
        if self.swarm:
            await self.swarm.start(self.config.initial_swarm_nodes)

        logger.info("HiggsNexus started")

    def stop(self):
        """Stop the Nexus system"""
        self._is_running = False

        if self.swarm:
            self.swarm.stop()

        logger.info("HiggsNexus stopped")

    async def analyze(
        self,
        # Echo Engine results
        echo_results: Dict[str, Any],

        # Singularity Engine results
        singularity_results: Dict[str, Any],

        # Market data
        market_data: Dict[str, Any],

    ) -> NexusInsight:
        """
        Main analysis method - combines all inputs to produce unified insight.

        Args:
            echo_results: Output from Echo Engine (TradingSignal, MonteCarloResult)
            singularity_results: Output from Singularity Engine (SingularityInsight)
            market_data: Raw market data (sentiments, ratings, volatility)

        Returns:
            NexusInsight with arbitrated signal and phase analysis
        """
        # Extract market data
        location_sentiments = market_data.get("location_sentiments", {})
        chain_sentiments = market_data.get("chain_sentiments", {})
        ratings = market_data.get("ratings", [])
        volatility = market_data.get("volatility", 0.1)

        # Extract Echo data
        echo_signal = echo_results.get("signal", "HOLD")
        echo_confidence = echo_results.get("confidence", 0.5)
        echo_chaos_index = echo_results.get("chaos_index", 1.0)
        echo_butterfly = echo_results.get("butterfly_coefficient", 0.5)
        echo_stability = echo_results.get("stability", "stable")
        echo_insights = echo_results.get("insights", [])
        echo_risk_factors = echo_results.get("risk_factors", [])

        # Extract Singularity data
        sing_action = singularity_results.get("trading_action", "HOLD")
        sing_confidence = singularity_results.get("confidence", 0.5)
        sing_strength = singularity_results.get("signal_strength", 0.0)
        sing_insights = singularity_results.get("insights", [])
        sing_risk_factors = singularity_results.get("risk_factors", [])
        sing_patterns = singularity_results.get("patterns", [])

        # Update phase detector
        phase_state = self.phase_detector.update(
            location_sentiments=location_sentiments,
            chain_sentiments=chain_sentiments,
            ratings=ratings,
            volatility=volatility,
            echo_chaos_index=echo_chaos_index,
            echo_stability=echo_stability,
            echo_butterfly=echo_butterfly,
            singularity_confidence=sing_confidence,
            singularity_patterns=sing_patterns
        )

        # Check for phase change
        if self._current_phase_state and phase_state.current_phase != self._current_phase_state.current_phase:
            if self._on_phase_change:
                await self._on_phase_change(
                    self._current_phase_state.current_phase,
                    phase_state.current_phase
                )

        self._current_phase_state = phase_state

        # Check for symmetry breaking
        symmetry_breaking = self.phase_detector.field.detect_symmetry_breaking(
            location_sentiments, chain_sentiments
        )
        if symmetry_breaking and symmetry_breaking.occurred:
            self._last_symmetry_breaking = symmetry_breaking
            if self._on_symmetry_breaking:
                await self._on_symmetry_breaking(symmetry_breaking)

        # Process through swarm if enabled
        swarm_opinion = 0.0
        swarm_confidence = 0.0
        swarm_consensus = False
        swarm_dissent: List[str] = []
        swarm_metrics: Optional[SwarmMetrics] = None

        if self.swarm and self._is_running:
            # Scale swarm for current phase
            self.swarm.scale_for_phase(phase_state.current_phase)

            # Process data through swarm
            swarm_input = self._prepare_swarm_input(
                location_sentiments, chain_sentiments, ratings, volatility,
                echo_results, singularity_results
            )

            swarm_result = self.swarm.process_batch(
                swarm_input,
                context={"phase": phase_state.current_phase}
            )

            swarm_opinion = swarm_result["opinion"]
            swarm_confidence = swarm_result["confidence"]
            swarm_consensus = swarm_result["consensus"]
            swarm_dissent = swarm_result.get("dissent_reasons", [])
            swarm_metrics = self.swarm.get_metrics()

        # Arbitrate signals
        arbitrated_signal = self.signal_arbiter.arbitrate(
            # Echo
            echo_signal=echo_signal,
            echo_confidence=echo_confidence,
            echo_chaos_index=echo_chaos_index,
            echo_butterfly=echo_butterfly,
            echo_stability=echo_stability,
            echo_insights=echo_insights,
            echo_risk_factors=echo_risk_factors,
            echo_raw=echo_results,
            # Singularity
            singularity_action=sing_action,
            singularity_confidence=sing_confidence,
            singularity_signal_strength=sing_strength,
            singularity_insights=sing_insights,
            singularity_risk_factors=sing_risk_factors,
            singularity_raw=singularity_results,
            # Phase
            phase_state=phase_state,
            # Swarm
            swarm_opinion=swarm_opinion,
            swarm_confidence=swarm_confidence,
            swarm_consensus=swarm_consensus,
            swarm_dissent=swarm_dissent
        )

        # Build complete insight
        insight = self._build_insight(
            phase_state=phase_state,
            symmetry_breaking=symmetry_breaking,
            signal=arbitrated_signal,
            swarm_metrics=swarm_metrics or self._get_default_swarm_metrics(),
            echo_results=echo_results,
            singularity_results=singularity_results
        )

        # Store in history
        self._insights_history.append(insight)
        if len(self._insights_history) > self.config.max_insights_history:
            self._insights_history.pop(0)

        return insight

    def _prepare_swarm_input(
        self,
        location_sentiments: Dict[str, float],
        chain_sentiments: Dict[str, float],
        ratings: List[float],
        volatility: float,
        echo_results: Dict[str, Any],
        singularity_results: Dict[str, Any]
    ) -> List[np.ndarray]:
        """Prepare input vectors for swarm processing"""
        inputs = []

        # Location sentiment vectors
        for loc_id, sent in list(location_sentiments.items())[:20]:  # Limit
            vec = np.array([
                sent,
                volatility,
                echo_results.get("chaos_index", 1.0) / 5.0,
                singularity_results.get("signal_strength", 0.0),
            ])
            inputs.append(vec)

        # Chain summary vectors
        for chain, sent in chain_sentiments.items():
            vec = np.array([
                sent,
                volatility,
                echo_results.get("butterfly_coefficient", 0.5),
                echo_results.get("confidence", 0.5),
            ])
            inputs.append(vec)

        # Ensure at least one input
        if not inputs:
            inputs.append(np.array([0.0, volatility, 0.5, 0.5]))

        return inputs

    def _build_insight(
        self,
        phase_state: PhaseState,
        symmetry_breaking: Optional[SymmetryBreaking],
        signal: ArbitratedSignal,
        swarm_metrics: SwarmMetrics,
        echo_results: Dict[str, Any],
        singularity_results: Dict[str, Any]
    ) -> NexusInsight:
        """Build complete NexusInsight from components"""

        # Generate narrative
        narrative = self._generate_narrative(phase_state, signal, symmetry_breaking)

        # Determine risk assessment
        risk = self._assess_risk(phase_state, signal, echo_results)

        # Generate action items
        action_items = self._generate_action_items(phase_state, signal, echo_results)

        # Generate watch list
        watch_list = self._generate_watch_list(phase_state, singularity_results)

        # Primary recommendation
        recommendation = self._generate_recommendation(signal, phase_state)

        return NexusInsight(
            insight_id=str(uuid.uuid4())[:12],
            timestamp=datetime.now(),
            phase_state=phase_state,
            symmetry_breaking=symmetry_breaking,
            signal=signal,
            swarm_metrics=swarm_metrics,
            primary_recommendation=recommendation,
            risk_assessment=risk,
            action_items=action_items,
            watch_list=watch_list,
            market_narrative=narrative,
            technical_details={
                "field_summary": self.phase_detector.field.get_field_summary(),
                "arbiter_stats": self.signal_arbiter.get_arbitration_stats(),
                "phase_summary": self.phase_detector.get_phase_summary()
            }
        )

    def _generate_narrative(
        self,
        phase_state: PhaseState,
        signal: ArbitratedSignal,
        symmetry_breaking: Optional[SymmetryBreaking]
    ) -> str:
        """Generate human-readable market narrative"""
        phase = phase_state.current_phase
        parts = []

        # Phase description
        phase_descriptions = {
            MarketPhase.SYMMETRIC: "Market is in equilibrium with balanced sentiment",
            MarketPhase.TRANSITION: "Market is transitioning between states",
            MarketPhase.BROKEN_BULLISH: "Market shows bullish bias with positive momentum",
            MarketPhase.BROKEN_BEARISH: "Market shows bearish bias with negative momentum",
            MarketPhase.CRITICAL: "Market is at critical point - high sensitivity to changes",
            MarketPhase.CHAOTIC: "Market is in chaotic state with unpredictable dynamics"
        }
        parts.append(phase_descriptions.get(phase, "Market state uncertain"))

        # Pending transition
        if phase_state.pending_transition and phase_state.pending_transition.probability > 0.5:
            pt = phase_state.pending_transition
            parts.append(
                f"Phase transition to {pt.to_phase.value} likely "
                f"({pt.probability:.0%} probability)"
            )

        # Symmetry breaking
        if symmetry_breaking and symmetry_breaking.occurred:
            parts.append(
                f"Symmetry breaking detected: {symmetry_breaking.direction} "
                f"(cascade risk: {symmetry_breaking.cascade_risk:.0%})"
            )

        # Signal summary
        parts.append(
            f"Recommendation: {signal.action} "
            f"(confidence: {signal.confidence:.0%}, {signal.authority.value})"
        )

        return ". ".join(parts) + "."

    def _assess_risk(
        self,
        phase_state: PhaseState,
        signal: ArbitratedSignal,
        echo_results: Dict[str, Any]
    ) -> str:
        """Assess overall risk level"""
        risk_score = 0

        # Phase risk
        phase_risks = {
            MarketPhase.SYMMETRIC: 0,
            MarketPhase.TRANSITION: 2,
            MarketPhase.BROKEN_BULLISH: 1,
            MarketPhase.BROKEN_BEARISH: 1,
            MarketPhase.CRITICAL: 3,
            MarketPhase.CHAOTIC: 4
        }
        risk_score += phase_risks.get(phase_state.current_phase, 2)

        # Echo stability risk
        stability = echo_results.get("stability", "stable")
        if stability == "critical":
            risk_score += 3
        elif stability == "unstable":
            risk_score += 1

        # Butterfly risk
        butterfly = echo_results.get("butterfly_coefficient", 0.5)
        if butterfly > 0.8:
            risk_score += 2
        elif butterfly > 0.6:
            risk_score += 1

        # Confidence risk (low confidence = higher risk)
        if signal.confidence < 0.4:
            risk_score += 2
        elif signal.confidence < 0.6:
            risk_score += 1

        # Map to level
        if risk_score >= 7:
            return "CRITICAL"
        elif risk_score >= 5:
            return "HIGH"
        elif risk_score >= 3:
            return "MEDIUM"
        else:
            return "LOW"

    def _generate_action_items(
        self,
        phase_state: PhaseState,
        signal: ArbitratedSignal,
        echo_results: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations"""
        items = []

        # Signal-based actions
        if signal.action in ["STRONG_BUY", "BUY"]:
            items.append("Consider increasing exposure to monitored chains")
        elif signal.action in ["STRONG_SELL", "SELL"]:
            items.append("Consider reducing exposure or hedging positions")
            items.append("Monitor for further deterioration")

        # Phase-based actions
        if phase_state.current_phase == MarketPhase.CRITICAL:
            items.append("Increase monitoring frequency")
            items.append("Prepare contingency plans for phase transition")
        elif phase_state.current_phase == MarketPhase.CHAOTIC:
            items.append("Reduce position sizes due to high uncertainty")
            items.append("Wait for phase stabilization before major decisions")

        # Pending transition actions
        if phase_state.pending_transition and phase_state.pending_transition.is_imminent:
            items.append(f"Prepare for transition to {phase_state.pending_transition.to_phase.value}")

        # Echo-specific actions
        critical_locs = echo_results.get("critical_locations", [])
        if critical_locs:
            items.append(f"Monitor high-impact locations: {', '.join(l.get('name', 'unknown')[:20] for l in critical_locs[:3])}")

        return items[:5]  # Limit to 5

    def _generate_watch_list(
        self,
        phase_state: PhaseState,
        singularity_results: Dict[str, Any]
    ) -> List[str]:
        """Generate list of things to monitor"""
        watch = []

        # Phase-related
        watch.append(f"Phase stability (current: {phase_state.stability_score:.0%})")

        if phase_state.pending_transition:
            for factor in phase_state.pending_transition.driving_factors[:2]:
                watch.append(factor)

        # Singularity patterns
        patterns = singularity_results.get("patterns", [])
        for p in patterns[:2]:
            watch.append(f"Pattern: {p}")

        # Warning signals
        warnings = singularity_results.get("warning_signals", [])
        for w in warnings[:2]:
            watch.append(f"Warning: {w}")

        return watch[:5]

    def _generate_recommendation(
        self,
        signal: ArbitratedSignal,
        phase_state: PhaseState
    ) -> str:
        """Generate primary recommendation string"""
        action_text = {
            "STRONG_BUY": "Strong positive outlook - consider aggressive positioning",
            "BUY": "Positive outlook - consider increasing exposure",
            "HOLD": "Neutral outlook - maintain current positions",
            "SELL": "Negative outlook - consider reducing exposure",
            "STRONG_SELL": "Strong negative outlook - consider defensive positioning"
        }

        base = action_text.get(signal.action, "Monitor situation")

        # Add phase context
        if phase_state.current_phase in [MarketPhase.CRITICAL, MarketPhase.CHAOTIC]:
            base += " (with caution due to market uncertainty)"

        if signal.phase_adjusted and signal.phase_adjustment_reason:
            base += f". Note: {signal.phase_adjustment_reason}"

        return base

    def _get_default_swarm_metrics(self) -> SwarmMetrics:
        """Get default swarm metrics when swarm is disabled"""
        return SwarmMetrics(
            active_nodes=0,
            hibernating_nodes=0,
            total_nodes=0,
            cpu_usage_percent=psutil.cpu_percent(),
            ram_usage_gb=psutil.Process().memory_info().rss / (1024 ** 3),
            average_node_energy=0,
            collective_intelligence_score=0,
            convergence_rate=0,
            diversity_index=0
        )

    def get_health(self) -> NexusHealth:
        """Get health status of the Nexus system"""
        cpu = psutil.cpu_percent()
        ram = psutil.Process().memory_info().rss / (1024 ** 3)

        warnings = []
        if cpu > self.config.max_cpu_percent:
            warnings.append(f"CPU usage high: {cpu:.1f}%")
        if ram > self.config.max_ram_gb:
            warnings.append(f"RAM usage high: {ram:.2f}GB")

        # Check component health
        phase_healthy = self._current_phase_state is not None or not self._is_running
        swarm_healthy = self.swarm is None or len(self.swarm.pool.active) > 0

        # Determine overall status
        if not self._is_running:
            status = "stopped"
        elif warnings:
            status = "degraded"
        elif not phase_healthy or not swarm_healthy:
            status = "degraded"
        else:
            status = "healthy"

        uptime = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0

        return NexusHealth(
            status=status,
            uptime_seconds=uptime,
            echo_engine_healthy=True,  # Assumed - Nexus doesn't manage Echo
            singularity_engine_healthy=True,  # Assumed - Nexus doesn't manage Singularity
            phase_detector_healthy=phase_healthy,
            swarm_coordinator_healthy=swarm_healthy,
            cpu_percent=cpu,
            ram_gb=ram,
            avg_latency_ms=0,  # Would need actual measurement
            signals_per_minute=len(self._insights_history) / max(1, uptime / 60),
            warnings=warnings
        )

    def get_current_phase(self) -> Optional[MarketPhase]:
        """Get current market phase"""
        return self._current_phase_state.current_phase if self._current_phase_state else None

    def get_recent_insights(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent insights as dictionaries"""
        return [i.to_dict() for i in self._insights_history[-count:]]

    def on_phase_change(self, callback: Callable):
        """Register callback for phase changes"""
        self._on_phase_change = callback

    def on_symmetry_breaking(self, callback: Callable):
        """Register callback for symmetry breaking events"""
        self._on_symmetry_breaking = callback


# Factory function for database integration
async def create_nexus_from_db(
    db_connection,
    config: Optional[NexusConfig] = None
) -> HiggsNexus:
    """
    Create HiggsNexus instance with database connection.

    This factory function can be extended to load initial state
    from database if needed.
    """
    nexus = HiggsNexus(config=config)
    await nexus.start()
    return nexus
