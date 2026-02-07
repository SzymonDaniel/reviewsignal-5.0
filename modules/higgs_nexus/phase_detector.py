# HIGGS NEXUS - Phase Detector
# Detects and predicts market phase transitions

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging

from .models import (
    MarketPhase,
    PhaseTransition,
    PhaseState,
    TransitionType,
    FieldState,
    SymmetryBreaking,
)
from .field_dynamics import HiggsField, HiggsFieldConfig

logger = logging.getLogger("HiggsNexus.PhaseDetector")


@dataclass
class PhaseDetectorConfig:
    """Configuration for phase detection"""
    # Detection sensitivity
    transition_threshold: float = 0.3      # Change needed to trigger transition
    min_stability_window: int = 5          # Ticks before phase considered stable

    # Prediction
    lookback_window: int = 20              # History for trend analysis
    prediction_horizon_hours: float = 24   # How far to predict

    # Thresholds
    first_order_threshold: float = 0.5     # Abrupt change threshold
    critical_susceptibility: float = 0.8   # When to flag critical

    # Integration
    echo_chaos_weight: float = 0.4         # How much Echo chaos affects phase
    singularity_pattern_weight: float = 0.3  # How much Singularity patterns affect


class PhaseDetector:
    """
    Detects market phases and predicts transitions using Higgs field dynamics.

    Combines:
    - Mexican hat potential dynamics from HiggsField
    - Echo Engine chaos metrics
    - Singularity pattern signals

    To produce phase state and transition predictions.
    """

    def __init__(
        self,
        config: Optional[PhaseDetectorConfig] = None,
        field_config: Optional[HiggsFieldConfig] = None
    ):
        self.config = config or PhaseDetectorConfig()
        self.field = HiggsField(field_config)

        # State tracking
        self._current_phase = MarketPhase.SYMMETRIC
        self._phase_history: List[Tuple[MarketPhase, datetime]] = []
        self._stability_counter = 0
        self._last_transition: Optional[datetime] = None

        # Metrics history for trend analysis
        self._volatility_history: List[float] = []
        self._sentiment_history: List[float] = []
        self._echo_chaos_history: List[float] = []

        logger.info("PhaseDetector initialized")

    def update(
        self,
        # Market data
        location_sentiments: Dict[str, float],
        chain_sentiments: Dict[str, float],
        ratings: List[float],
        volatility: float,
        # Echo Engine data
        echo_chaos_index: Optional[float] = None,
        echo_stability: Optional[str] = None,
        echo_butterfly: Optional[float] = None,
        # Singularity data
        singularity_confidence: Optional[float] = None,
        singularity_patterns: Optional[List[str]] = None,
    ) -> PhaseState:
        """
        Update phase state with new market data.

        Returns complete PhaseState with current phase and any pending transitions.
        """
        # Extract sentiment list
        sentiments = list(location_sentiments.values()) if location_sentiments else []

        # Update field state
        field_state = self.field.update_from_market_data(
            sentiments=sentiments,
            ratings=ratings,
            volatility=volatility,
            chain_sentiments=chain_sentiments
        )

        # Store history
        self._volatility_history.append(volatility)
        if sentiments:
            self._sentiment_history.append(np.mean(sentiments))
        if echo_chaos_index is not None:
            self._echo_chaos_history.append(echo_chaos_index)

        # Trim histories
        max_history = self.config.lookback_window * 2
        self._volatility_history = self._volatility_history[-max_history:]
        self._sentiment_history = self._sentiment_history[-max_history:]
        self._echo_chaos_history = self._echo_chaos_history[-max_history:]

        # Determine phase with external inputs
        adjusted_phase = self._adjust_phase_with_engines(
            field_state.phase,
            echo_chaos_index,
            echo_stability,
            echo_butterfly,
            singularity_confidence,
            singularity_patterns
        )

        # Check for phase transition
        transition = self._detect_transition(adjusted_phase, field_state)

        # Update current phase
        if adjusted_phase != self._current_phase:
            if self._stability_counter >= self.config.min_stability_window:
                self._phase_history.append((self._current_phase, datetime.now()))
                self._current_phase = adjusted_phase
                self._last_transition = datetime.now()
                self._stability_counter = 0
                logger.info(f"Phase transition: {self._current_phase.value}")
            else:
                self._stability_counter += 1
        else:
            self._stability_counter = min(
                self._stability_counter + 1,
                self.config.min_stability_window * 2
            )

        # Check for symmetry breaking
        symmetry_breaking = self.field.detect_symmetry_breaking(
            location_sentiments,
            chain_sentiments
        )

        # Predict future transition
        pending_transition = self._predict_transition(field_state)
        if transition and transition.probability > (pending_transition.probability if pending_transition else 0):
            pending_transition = transition

        # Build phase state
        phase_state = PhaseState(
            current_phase=self._current_phase,
            field_state=field_state,
            pending_transition=pending_transition,
            stability_score=self._calculate_stability_score(field_state)
        )

        # Add to history
        phase_state.add_history(self._current_phase, datetime.now())

        return phase_state

    def _adjust_phase_with_engines(
        self,
        field_phase: MarketPhase,
        echo_chaos: Optional[float],
        echo_stability: Optional[str],
        echo_butterfly: Optional[float],
        singularity_confidence: Optional[float],
        singularity_patterns: Optional[List[str]]
    ) -> MarketPhase:
        """
        Adjust field-based phase with Echo and Singularity inputs.
        """
        adjusted = field_phase

        # Echo chaos override
        if echo_chaos is not None:
            if echo_chaos > 3.0:  # High chaos
                if field_phase in [MarketPhase.SYMMETRIC, MarketPhase.BROKEN_BULLISH, MarketPhase.BROKEN_BEARISH]:
                    adjusted = MarketPhase.CHAOTIC
            elif echo_stability == "critical":
                adjusted = MarketPhase.CRITICAL

        # Echo butterfly effect
        if echo_butterfly is not None and echo_butterfly > 0.8:
            if adjusted == MarketPhase.SYMMETRIC:
                adjusted = MarketPhase.CRITICAL  # High sensitivity means near transition

        # Singularity patterns
        if singularity_patterns:
            pattern_keywords = " ".join(singularity_patterns).lower()
            if "anomaly" in pattern_keywords or "divergence" in pattern_keywords:
                if adjusted not in [MarketPhase.CHAOTIC, MarketPhase.CRITICAL]:
                    adjusted = MarketPhase.TRANSITION

        return adjusted

    def _detect_transition(
        self,
        new_phase: MarketPhase,
        field_state: FieldState
    ) -> Optional[PhaseTransition]:
        """
        Detect if a phase transition is occurring.
        """
        if new_phase == self._current_phase:
            return None

        # Determine transition type
        if field_state.susceptibility > self.config.first_order_threshold:
            transition_type = TransitionType.FIRST_ORDER
        elif field_state.is_critical:
            transition_type = TransitionType.SECOND_ORDER
        else:
            transition_type = TransitionType.CROSSOVER

        # Calculate probability
        probability = min(0.9, field_state.susceptibility + 0.3)

        # Identify driving factors
        driving_factors = []
        if len(self._volatility_history) >= 3:
            vol_trend = self._volatility_history[-1] - np.mean(self._volatility_history[-3:])
            if vol_trend > 0.05:
                driving_factors.append("Increasing volatility")
            elif vol_trend < -0.05:
                driving_factors.append("Decreasing volatility")

        if len(self._sentiment_history) >= 3:
            sent_trend = self._sentiment_history[-1] - np.mean(self._sentiment_history[-3:])
            if sent_trend > 0.1:
                driving_factors.append("Sentiment improving")
            elif sent_trend < -0.1:
                driving_factors.append("Sentiment declining")

        if len(self._echo_chaos_history) >= 3:
            chaos_trend = self._echo_chaos_history[-1] - np.mean(self._echo_chaos_history[-3:])
            if chaos_trend > 0.5:
                driving_factors.append("Chaos increasing")

        if not driving_factors:
            driving_factors.append("Field dynamics")

        return PhaseTransition(
            transition_type=transition_type,
            from_phase=self._current_phase,
            to_phase=new_phase,
            probability=probability,
            estimated_time_hours=None,  # Already happening
            driving_factors=driving_factors,
            affected_chains=[],  # Would need chain data
            affected_cities=[],  # Would need city data
            confidence=probability * 0.8
        )

    def _predict_transition(self, field_state: FieldState) -> Optional[PhaseTransition]:
        """
        Predict future phase transitions based on trends.
        """
        if len(self._volatility_history) < self.config.lookback_window:
            return None

        # Calculate trends
        vol_recent = np.mean(self._volatility_history[-5:])
        vol_older = np.mean(self._volatility_history[-self.config.lookback_window:-5])
        vol_trend = vol_recent - vol_older

        sent_trend = 0
        if len(self._sentiment_history) >= self.config.lookback_window:
            sent_recent = np.mean(self._sentiment_history[-5:])
            sent_older = np.mean(self._sentiment_history[-self.config.lookback_window:-5])
            sent_trend = sent_recent - sent_older

        # Use field prediction
        prob, predicted_phase = self.field.predict_transition(vol_trend, sent_trend)

        if prob < 0.2:
            return None

        # Estimate time based on rate of change
        if abs(vol_trend) > 0.01:
            estimated_hours = min(
                self.config.prediction_horizon_hours,
                abs(0.1 / vol_trend) * 24  # Hours to significant change
            )
        else:
            estimated_hours = self.config.prediction_horizon_hours

        driving_factors = []
        if vol_trend > 0:
            driving_factors.append("Volatility trending up")
        elif vol_trend < 0:
            driving_factors.append("Volatility trending down")
        if sent_trend > 0:
            driving_factors.append("Sentiment improving")
        elif sent_trend < 0:
            driving_factors.append("Sentiment worsening")

        return PhaseTransition(
            transition_type=TransitionType.CROSSOVER,  # Predictions are usually gradual
            from_phase=self._current_phase,
            to_phase=predicted_phase,
            probability=prob,
            estimated_time_hours=estimated_hours,
            driving_factors=driving_factors,
            affected_chains=[],
            affected_cities=[],
            confidence=prob * 0.6  # Predictions less confident
        )

    def _calculate_stability_score(self, field_state: FieldState) -> float:
        """
        Calculate overall stability score 0-1.
        """
        # Base from field
        base_stability = field_state.phase_stability

        # Adjust for recent transitions
        if self._last_transition:
            hours_since = (datetime.now() - self._last_transition).total_seconds() / 3600
            if hours_since < 1:
                base_stability *= 0.5
            elif hours_since < 6:
                base_stability *= 0.8

        # Adjust for volatility trend
        if len(self._volatility_history) >= 5:
            vol_std = np.std(self._volatility_history[-5:])
            if vol_std > 0.1:
                base_stability *= 0.7

        return min(1.0, max(0.0, base_stability))

    def get_phase_summary(self) -> Dict:
        """Get summary of current phase state"""
        return {
            "current_phase": self._current_phase.value,
            "stability_counter": self._stability_counter,
            "last_transition": self._last_transition.isoformat() if self._last_transition else None,
            "phase_history_length": len(self._phase_history),
            "field_summary": self.field.get_field_summary()
        }
