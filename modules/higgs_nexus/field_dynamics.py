# HIGGS NEXUS - Field Dynamics
# Mexican hat potential and symmetry breaking detection

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

from .models import (
    FieldPotential,
    FieldState,
    SymmetryBreaking,
    MarketPhase,
)

logger = logging.getLogger("HiggsNexus.FieldDynamics")


@dataclass
class HiggsFieldConfig:
    """Configuration for Higgs field dynamics"""
    # Mexican hat potential parameters
    mu_squared: float = 1.0           # Mass parameter (negative for SSB)
    lambda_coupling: float = 0.25     # Quartic coupling

    # Temperature/volatility mapping
    volatility_to_temp_scale: float = 10.0
    critical_volatility: float = 0.15  # Volatility at critical temperature

    # Phase detection thresholds
    symmetric_threshold: float = 0.2   # φ/v below this = symmetric
    vacuum_threshold: float = 0.8      # φ/v above this = in vacuum
    critical_band: float = 0.1         # Width of critical region

    # Dynamics
    field_dimensions: int = 8          # Dimensionality of order parameter
    relaxation_rate: float = 0.1       # How fast field moves to minimum


class HiggsField:
    """
    Implements Mexican hat potential dynamics for market phase detection.

    The potential: V(φ) = -μ²|φ|² + λ|φ|⁴

    - At high temperature (T > Tc): minimum at φ = 0 (symmetric phase)
    - At low temperature (T < Tc): minimum at |φ| = v = √(μ²/λ) (broken phase)

    Market mapping:
    - φ = order parameter (sentiment consensus direction)
    - T = effective temperature (market volatility)
    - v = vacuum expectation value (stable sentiment state)
    """

    def __init__(self, config: Optional[HiggsFieldConfig] = None):
        self.config = config or HiggsFieldConfig()
        self.c = self.config

        # Vacuum expectation value
        self.vev = np.sqrt(self.c.mu_squared / self.c.lambda_coupling)

        # Current field state
        self._position = np.zeros(self.c.field_dimensions)
        self._velocity = np.zeros(self.c.field_dimensions)
        self._temperature = 1.0

        # History for transition detection
        self._position_history: List[np.ndarray] = []
        self._max_history = 100

        logger.info(f"HiggsField initialized with VEV = {self.vev:.4f}")

    def compute_potential(self, phi: np.ndarray) -> float:
        """
        Compute Mexican hat potential V(φ) = -μ²|φ|² + λ|φ|⁴
        """
        phi_squared = np.sum(phi ** 2)
        return -self.c.mu_squared * phi_squared + self.c.lambda_coupling * (phi_squared ** 2)

    def compute_gradient(self, phi: np.ndarray) -> np.ndarray:
        """
        Compute gradient ∇V(φ) = -2μ²φ + 4λ|φ|²φ
        """
        phi_squared = np.sum(phi ** 2)
        return -2 * self.c.mu_squared * phi + 4 * self.c.lambda_coupling * phi_squared * phi

    def compute_curvature(self, phi: np.ndarray) -> float:
        """
        Compute effective mass (curvature) at position φ.
        At origin: m² = -2μ² (tachyonic, unstable)
        At vacuum: m² = 4μ² (stable)
        """
        phi_squared = np.sum(phi ** 2)
        return -2 * self.c.mu_squared + 12 * self.c.lambda_coupling * phi_squared

    def update_from_market_data(
        self,
        sentiments: List[float],
        ratings: List[float],
        volatility: float,
        chain_sentiments: Dict[str, float]
    ) -> FieldState:
        """
        Update field state from market data.

        Maps market observables to field theory:
        - Sentiment distribution → field position (order parameter)
        - Volatility → temperature
        - Chain sentiments → directional components
        """
        # Calculate effective temperature from volatility
        self._temperature = volatility * self.c.volatility_to_temp_scale
        critical_temp = self.c.critical_volatility * self.c.volatility_to_temp_scale

        # Calculate order parameter from sentiment consensus
        if sentiments:
            mean_sentiment = np.mean(sentiments)
            sentiment_std = np.std(sentiments) if len(sentiments) > 1 else 0.1

            # Map to field position
            # Direction from mean sentiment, magnitude from consensus
            consensus = 1 - min(1, sentiment_std / 0.5)  # High std = low consensus

            # Build position vector from chain sentiments
            position = np.zeros(self.c.field_dimensions)
            chain_list = list(chain_sentiments.items())[:self.c.field_dimensions]

            for i, (chain, sent) in enumerate(chain_list):
                position[i] = sent * consensus * self.vev

            # Fill remaining dimensions with aggregate
            for i in range(len(chain_list), self.c.field_dimensions):
                position[i] = mean_sentiment * consensus * self.vev * 0.5

            # Normalize to reasonable range
            norm = np.linalg.norm(position)
            if norm > 2 * self.vev:
                position = position * (2 * self.vev / norm)

            self._position = position

        # Store history
        self._position_history.append(self._position.copy())
        if len(self._position_history) > self._max_history:
            self._position_history.pop(0)

        # Compute field state
        return self._compute_field_state(critical_temp)

    def _compute_field_state(self, critical_temp: float) -> FieldState:
        """Compute complete field state"""
        phi = self._position
        phi_magnitude = np.linalg.norm(phi)

        # Potential at current position
        potential = FieldPotential(
            position=phi.copy(),
            potential_value=self.compute_potential(phi),
            gradient=self.compute_gradient(phi),
            curvature=self.compute_curvature(phi),
            distance_from_minimum=abs(phi_magnitude - self.vev),
            vacuum_expectation_value=self.vev
        )

        # Determine phase
        phase = self._determine_phase(phi_magnitude, self._temperature, critical_temp)

        # Order parameter: 0 at origin, 1 at vacuum
        order_parameter = min(1.0, phi_magnitude / self.vev)

        # Susceptibility: high near critical point
        if abs(self._temperature - critical_temp) < 0.1 * critical_temp:
            susceptibility = 1.0  # Diverges at critical point
        else:
            susceptibility = 1.0 / abs(self._temperature - critical_temp + 0.1)
        susceptibility = min(1.0, susceptibility)

        # Correlation length: also diverges near critical point
        correlation_length = 1.0 / (abs(phi_magnitude - self.vev) + 0.1)
        correlation_length = min(10.0, correlation_length)

        return FieldState(
            potential=potential,
            phase=phase,
            temperature=self._temperature,
            critical_temperature=critical_temp,
            order_parameter=order_parameter,
            susceptibility=susceptibility,
            correlation_length=correlation_length
        )

    def _determine_phase(
        self,
        phi_magnitude: float,
        temperature: float,
        critical_temp: float
    ) -> MarketPhase:
        """Determine current market phase from field configuration"""
        relative_phi = phi_magnitude / self.vev
        relative_temp = temperature / critical_temp

        # Check for chaotic state (high variance in recent history)
        if len(self._position_history) >= 10:
            recent = self._position_history[-10:]
            magnitudes = [np.linalg.norm(p) for p in recent]
            if np.std(magnitudes) > 0.3 * self.vev:
                return MarketPhase.CHAOTIC

        # Near critical temperature
        if abs(relative_temp - 1.0) < self.c.critical_band:
            return MarketPhase.CRITICAL

        # High temperature: symmetric phase
        if relative_temp > 1.0 + self.c.critical_band:
            if relative_phi < self.c.symmetric_threshold:
                return MarketPhase.SYMMETRIC
            else:
                return MarketPhase.TRANSITION

        # Low temperature: broken symmetry
        if relative_phi > self.c.vacuum_threshold:
            # Determine direction
            if len(self._position_history) >= 3:
                recent_mean = np.mean(self._position_history[-3:], axis=0)
                direction = np.sum(recent_mean)  # Simple sum for direction
                if direction > 0:
                    return MarketPhase.BROKEN_BULLISH
                else:
                    return MarketPhase.BROKEN_BEARISH
            return MarketPhase.BROKEN_BULLISH  # Default

        # In transition
        return MarketPhase.TRANSITION

    def detect_symmetry_breaking(
        self,
        location_sentiments: Dict[str, float],
        chain_sentiments: Dict[str, float]
    ) -> Optional[SymmetryBreaking]:
        """
        Detect if symmetry breaking has occurred and identify trigger.
        """
        if len(self._position_history) < 5:
            return None

        # Check for recent transition from symmetric to broken
        recent_magnitudes = [np.linalg.norm(p) for p in self._position_history[-5:]]
        older_magnitudes = [np.linalg.norm(p) for p in self._position_history[-10:-5]] if len(self._position_history) >= 10 else [0]

        recent_avg = np.mean(recent_magnitudes)
        older_avg = np.mean(older_magnitudes)

        # Symmetry breaking if recent magnitude significantly larger
        if recent_avg > 0.5 * self.vev and older_avg < 0.3 * self.vev:
            # Find trigger
            trigger_chain = None
            trigger_location = None
            max_deviation = 0

            for chain, sent in chain_sentiments.items():
                if abs(sent) > max_deviation:
                    max_deviation = abs(sent)
                    trigger_chain = chain

            for loc_id, sent in location_sentiments.items():
                if abs(sent) > max_deviation:
                    max_deviation = abs(sent)
                    trigger_location = loc_id
                    trigger_chain = None

            # Direction
            direction = "bullish" if np.sum(self._position) > 0 else "bearish"

            # Cascade risk based on susceptibility
            cascade_risk = min(1.0, recent_avg / self.vev)

            return SymmetryBreaking(
                occurred=True,
                direction=direction,
                magnitude=recent_avg / self.vev,
                trigger_time=datetime.now(),
                trigger_location=trigger_location,
                trigger_chain=trigger_chain,
                cascade_risk=cascade_risk
            )

        return None

    def predict_transition(
        self,
        volatility_trend: float,  # Positive = increasing
        sentiment_momentum: float
    ) -> Tuple[float, MarketPhase]:
        """
        Predict probability and direction of phase transition.

        Returns:
            (probability, predicted_phase)
        """
        current_magnitude = np.linalg.norm(self._position)
        relative_phi = current_magnitude / self.vev

        # If volatility increasing, moving toward symmetric phase
        if volatility_trend > 0.1:
            if relative_phi > 0.5:
                # Currently in broken phase, might transition to symmetric
                probability = min(0.9, 0.3 + volatility_trend * 2)
                return probability, MarketPhase.TRANSITION

        # If volatility decreasing, moving toward broken phase
        if volatility_trend < -0.1:
            if relative_phi < 0.5:
                # Currently near symmetric, might break
                probability = min(0.9, 0.3 + abs(volatility_trend) * 2)
                if sentiment_momentum > 0:
                    return probability, MarketPhase.BROKEN_BULLISH
                else:
                    return probability, MarketPhase.BROKEN_BEARISH

        # Near critical point
        if abs(self._temperature - self.c.critical_volatility * self.c.volatility_to_temp_scale) < 0.5:
            return 0.5, MarketPhase.CRITICAL

        return 0.1, MarketPhase.SYMMETRIC

    def get_field_summary(self) -> Dict[str, any]:
        """Get summary of current field state"""
        magnitude = np.linalg.norm(self._position)
        return {
            "position_magnitude": magnitude,
            "position_normalized": magnitude / self.vev,
            "temperature": self._temperature,
            "potential_value": self.compute_potential(self._position),
            "curvature": self.compute_curvature(self._position),
            "vev": self.vev,
            "history_length": len(self._position_history)
        }
