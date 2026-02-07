# HIGGS NEXUS - Signal Arbiter
# Combines Echo and Singularity signals with phase-aware weighting

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging

from .models import (
    MarketPhase,
    EngineAuthority,
    EngineContribution,
    ArbitratedSignal,
    PhaseState,
)

logger = logging.getLogger("HiggsNexus.SignalArbiter")


@dataclass
class ArbiterConfig:
    """Configuration for signal arbitration"""
    # Base weights (sum to 1.0)
    base_echo_weight: float = 0.5
    base_singularity_weight: float = 0.5

    # Phase-specific weight adjustments
    phase_weights: Dict[str, Tuple[float, float]] = None  # {phase: (echo_w, sing_w)}

    # Signal thresholds
    strong_signal_threshold: float = 0.4
    weak_signal_threshold: float = 0.15

    # Confidence adjustments
    min_confidence: float = 0.2
    max_confidence: float = 0.95

    # Swarm influence
    swarm_weight: float = 0.2              # How much swarm affects final signal
    swarm_veto_threshold: float = 0.8      # Swarm consensus to veto

    def __post_init__(self):
        if self.phase_weights is None:
            # Default phase-specific weights
            # Format: {phase: (echo_weight, singularity_weight)}
            self.phase_weights = {
                # Symmetric: balanced, slight singularity edge for patterns
                MarketPhase.SYMMETRIC.value: (0.45, 0.55),

                # Transition: Echo better at detecting propagation
                MarketPhase.TRANSITION.value: (0.6, 0.4),

                # Broken phases: Singularity better for pattern confirmation
                MarketPhase.BROKEN_BULLISH.value: (0.4, 0.6),
                MarketPhase.BROKEN_BEARISH.value: (0.4, 0.6),

                # Critical: Echo dominates for chaos detection
                MarketPhase.CRITICAL.value: (0.7, 0.3),

                # Chaotic: Heavy Echo for sensitivity analysis
                MarketPhase.CHAOTIC.value: (0.75, 0.25),
            }


class SignalArbiter:
    """
    Arbitrates between Echo Engine and Singularity Engine signals.

    Key responsibilities:
    - Phase-aware weight assignment
    - Signal combination and normalization
    - Confidence calibration
    - Swarm consensus integration
    - Final action determination
    """

    def __init__(self, config: Optional[ArbiterConfig] = None):
        self.config = config or ArbiterConfig()
        self._last_arbitration: Optional[datetime] = None
        self._signal_history: List[ArbitratedSignal] = []

        logger.info("SignalArbiter initialized")

    def arbitrate(
        self,
        # Echo Engine inputs
        echo_signal: str,                    # BUY, HOLD, SELL
        echo_confidence: float,
        echo_chaos_index: float,
        echo_butterfly: float,
        echo_stability: str,
        echo_insights: List[str],
        echo_risk_factors: List[str],
        echo_raw: Dict[str, Any],

        # Singularity Engine inputs
        singularity_action: str,             # STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL
        singularity_confidence: float,
        singularity_signal_strength: float,
        singularity_insights: List[str],
        singularity_risk_factors: List[str],
        singularity_raw: Dict[str, Any],

        # Phase state
        phase_state: PhaseState,

        # Swarm inputs
        swarm_opinion: float,
        swarm_confidence: float,
        swarm_consensus: bool,
        swarm_dissent: List[str],

    ) -> ArbitratedSignal:
        """
        Arbitrate between engine signals to produce final recommendation.
        """
        self._last_arbitration = datetime.now()
        phase = phase_state.current_phase

        # Convert signals to numeric
        echo_strength = self._signal_to_strength(echo_signal)
        sing_strength = singularity_signal_strength

        # Get phase-specific weights
        echo_weight, sing_weight = self._get_phase_weights(phase)

        # Adjust weights based on engine health/confidence
        echo_weight, sing_weight = self._adjust_weights_by_confidence(
            echo_weight, sing_weight,
            echo_confidence, singularity_confidence
        )

        # Determine authority
        authority = self._determine_authority(
            echo_weight, sing_weight,
            echo_stability, phase
        )

        # Combine signals
        combined_strength = (
            echo_strength * echo_weight +
            sing_strength * sing_weight
        )

        # Apply swarm influence
        combined_strength, swarm_adjusted = self._apply_swarm_influence(
            combined_strength,
            swarm_opinion, swarm_confidence, swarm_consensus
        )

        # Calculate combined confidence
        combined_confidence = self._calculate_combined_confidence(
            echo_confidence, singularity_confidence,
            echo_weight, sing_weight,
            swarm_confidence if swarm_consensus else 0.5,
            phase_state.stability_score
        )

        # Determine final action
        action = self._strength_to_action(combined_strength, combined_confidence)

        # Check for phase-based adjustments
        action, phase_adjusted, adjustment_reason = self._apply_phase_adjustments(
            action, combined_strength, combined_confidence,
            phase, echo_stability, echo_butterfly
        )

        # Build contributions
        echo_contribution = EngineContribution(
            engine_name="echo",
            signal_strength=echo_strength,
            confidence=echo_confidence,
            weight=echo_weight,
            key_insights=echo_insights[:3],
            risk_factors=echo_risk_factors[:3],
            raw_data={"chaos_index": echo_chaos_index, "butterfly": echo_butterfly, "stability": echo_stability}
        )

        singularity_contribution = EngineContribution(
            engine_name="singularity",
            signal_strength=sing_strength,
            confidence=singularity_confidence,
            weight=sing_weight,
            key_insights=singularity_insights[:3],
            risk_factors=singularity_risk_factors[:3],
            raw_data=singularity_raw
        )

        # Build result
        signal = ArbitratedSignal(
            action=action,
            confidence=combined_confidence,
            signal_strength=combined_strength,
            echo_contribution=echo_contribution,
            singularity_contribution=singularity_contribution,
            authority=authority,
            market_phase=phase,
            phase_adjusted=phase_adjusted or swarm_adjusted,
            phase_adjustment_reason=adjustment_reason,
            swarm_consensus=swarm_confidence if swarm_consensus else 0.0,
            swarm_dissent_reasons=swarm_dissent
        )

        # Store in history
        self._signal_history.append(signal)
        if len(self._signal_history) > 100:
            self._signal_history.pop(0)

        logger.info(
            f"Arbitrated: {action} (conf={combined_confidence:.2f}, "
            f"phase={phase.value}, authority={authority.value})"
        )

        return signal

    def _signal_to_strength(self, signal: str) -> float:
        """Convert signal string to numeric strength"""
        mapping = {
            "STRONG_BUY": 0.8,
            "BUY": 0.4,
            "HOLD": 0.0,
            "SELL": -0.4,
            "STRONG_SELL": -0.8,
        }
        return mapping.get(signal.upper(), 0.0)

    def _strength_to_action(self, strength: float, confidence: float) -> str:
        """Convert numeric strength to action string"""
        # Require higher confidence for strong signals
        strong_threshold = self.config.strong_signal_threshold
        weak_threshold = self.config.weak_signal_threshold

        if strength > strong_threshold and confidence > 0.6:
            return "STRONG_BUY"
        elif strength > weak_threshold:
            return "BUY"
        elif strength < -strong_threshold and confidence > 0.6:
            return "STRONG_SELL"
        elif strength < -weak_threshold:
            return "SELL"
        else:
            return "HOLD"

    def _get_phase_weights(self, phase: MarketPhase) -> Tuple[float, float]:
        """Get phase-specific weights for Echo and Singularity"""
        weights = self.config.phase_weights.get(
            phase.value,
            (self.config.base_echo_weight, self.config.base_singularity_weight)
        )
        return weights

    def _adjust_weights_by_confidence(
        self,
        echo_weight: float,
        sing_weight: float,
        echo_conf: float,
        sing_conf: float
    ) -> Tuple[float, float]:
        """Adjust weights based on engine confidence levels"""
        # If one engine is much more confident, give it more weight
        total_conf = echo_conf + sing_conf
        if total_conf > 0:
            conf_ratio = echo_conf / total_conf

            # Blend base weights with confidence-based weights
            echo_adjusted = 0.7 * echo_weight + 0.3 * conf_ratio
            sing_adjusted = 0.7 * sing_weight + 0.3 * (1 - conf_ratio)

            # Normalize
            total = echo_adjusted + sing_adjusted
            return echo_adjusted / total, sing_adjusted / total

        return echo_weight, sing_weight

    def _determine_authority(
        self,
        echo_weight: float,
        sing_weight: float,
        echo_stability: str,
        phase: MarketPhase
    ) -> EngineAuthority:
        """Determine which engine has primary authority"""
        # Critical stability = Nexus override
        if echo_stability == "critical" and phase in [MarketPhase.CRITICAL, MarketPhase.CHAOTIC]:
            return EngineAuthority.NEXUS_OVERRIDE

        # Check weight dominance
        weight_diff = echo_weight - sing_weight
        if weight_diff > 0.15:
            return EngineAuthority.ECHO_DOMINANT
        elif weight_diff < -0.15:
            return EngineAuthority.SINGULARITY_DOMINANT
        else:
            return EngineAuthority.BALANCED

    def _apply_swarm_influence(
        self,
        combined_strength: float,
        swarm_opinion: float,
        swarm_confidence: float,
        swarm_consensus: bool
    ) -> Tuple[float, bool]:
        """Apply swarm collective intelligence to signal"""
        adjusted = False

        if swarm_consensus and swarm_confidence > 0.5:
            # Swarm has strong consensus - incorporate
            swarm_weight = self.config.swarm_weight * swarm_confidence

            # Check for potential veto
            if swarm_confidence > self.config.swarm_veto_threshold:
                if np.sign(swarm_opinion) != np.sign(combined_strength) and abs(swarm_opinion) > 0.3:
                    # Swarm strongly disagrees - move toward neutral
                    combined_strength *= 0.5
                    adjusted = True
                    logger.warning("Swarm veto applied - signal moderated")

            # Blend with swarm
            new_strength = (1 - swarm_weight) * combined_strength + swarm_weight * swarm_opinion
            if abs(new_strength - combined_strength) > 0.1:
                adjusted = True
            combined_strength = new_strength

        return combined_strength, adjusted

    def _calculate_combined_confidence(
        self,
        echo_conf: float,
        sing_conf: float,
        echo_weight: float,
        sing_weight: float,
        swarm_conf: float,
        stability_score: float
    ) -> float:
        """Calculate combined confidence from all sources"""
        # Weighted average of engine confidences
        engine_conf = echo_conf * echo_weight + sing_conf * sing_weight

        # Incorporate swarm and stability
        swarm_factor = 0.1  # Small influence
        stability_factor = 0.2

        combined = (
            (1 - swarm_factor - stability_factor) * engine_conf +
            swarm_factor * swarm_conf +
            stability_factor * stability_score
        )

        # Clamp to valid range
        return max(self.config.min_confidence, min(self.config.max_confidence, combined))

    def _apply_phase_adjustments(
        self,
        action: str,
        strength: float,
        confidence: float,
        phase: MarketPhase,
        stability: str,
        butterfly: float
    ) -> Tuple[str, bool, Optional[str]]:
        """Apply phase-based adjustments to final action"""
        adjusted = False
        reason = None

        # Critical phase: be more conservative
        if phase == MarketPhase.CRITICAL:
            if action in ["STRONG_BUY", "STRONG_SELL"]:
                action = "BUY" if "BUY" in action else "SELL"
                adjusted = True
                reason = "Moderated due to critical phase"

        # Chaotic phase: high butterfly = reduce confidence in direction
        if phase == MarketPhase.CHAOTIC and butterfly > 0.7:
            if action != "HOLD" and confidence < 0.7:
                action = "HOLD"
                adjusted = True
                reason = "High sensitivity in chaotic phase"

        # Stability critical: strongly advise caution
        if stability == "critical":
            if action in ["STRONG_BUY", "BUY"]:
                action = "HOLD"
                adjusted = True
                reason = "System stability critical - caution advised"

        # Transition phase: don't commit strongly
        if phase == MarketPhase.TRANSITION:
            if action in ["STRONG_BUY", "STRONG_SELL"] and confidence < 0.8:
                action = "BUY" if "BUY" in action else "SELL"
                adjusted = True
                reason = "Phase transition in progress"

        return action, adjusted, reason

    def get_arbitration_stats(self) -> Dict[str, Any]:
        """Get statistics on recent arbitrations"""
        if not self._signal_history:
            return {"count": 0}

        actions = [s.action for s in self._signal_history]
        confidences = [s.confidence for s in self._signal_history]
        phase_adjusted = sum(1 for s in self._signal_history if s.phase_adjusted)

        return {
            "count": len(self._signal_history),
            "action_distribution": {
                a: actions.count(a) / len(actions)
                for a in set(actions)
            },
            "avg_confidence": np.mean(confidences),
            "phase_adjustment_rate": phase_adjusted / len(self._signal_history),
            "last_arbitration": self._last_arbitration.isoformat() if self._last_arbitration else None
        }
