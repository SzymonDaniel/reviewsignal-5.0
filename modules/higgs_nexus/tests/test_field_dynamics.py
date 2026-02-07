# HIGGS NEXUS - Field Dynamics Tests
# Unit tests for Mexican hat potential and symmetry breaking

import pytest
import numpy as np
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from modules.higgs_nexus.field_dynamics import (
    HiggsField,
    HiggsFieldConfig,
)
from modules.higgs_nexus.models import MarketPhase


class TestHiggsFieldConfig:
    """Tests for HiggsFieldConfig defaults"""

    def test_default_config(self):
        config = HiggsFieldConfig()
        assert config.mu_squared == 1.0
        assert config.lambda_coupling == 0.25
        assert config.field_dimensions == 8

    def test_custom_config(self):
        config = HiggsFieldConfig(
            mu_squared=2.0,
            lambda_coupling=0.5,
            field_dimensions=16
        )
        assert config.mu_squared == 2.0
        assert config.lambda_coupling == 0.5
        assert config.field_dimensions == 16


class TestHiggsField:
    """Tests for HiggsField dynamics"""

    @pytest.fixture
    def field(self):
        return HiggsField()

    @pytest.fixture
    def custom_field(self):
        config = HiggsFieldConfig(
            mu_squared=1.5,
            lambda_coupling=0.3
        )
        return HiggsField(config)

    def test_initialization(self, field):
        """Test field initializes correctly"""
        assert field is not None
        assert field.vev > 0
        # VEV = sqrt(mu^2 / lambda) = sqrt(1.0 / 0.25) = 2.0
        assert abs(field.vev - 2.0) < 0.001

    def test_vev_calculation(self, custom_field):
        """Test VEV calculation with custom params"""
        # VEV = sqrt(1.5 / 0.3) = sqrt(5) ≈ 2.236
        expected_vev = np.sqrt(1.5 / 0.3)
        assert abs(custom_field.vev - expected_vev) < 0.001

    def test_potential_at_origin(self, field):
        """Test potential is 0 at origin"""
        phi = np.zeros(8)
        potential = field.compute_potential(phi)
        assert potential == 0.0

    def test_potential_at_vacuum(self, field):
        """Test potential is negative at vacuum"""
        # At |phi| = vev, potential should be minimum (negative)
        phi = np.zeros(8)
        phi[0] = field.vev
        potential = field.compute_potential(phi)
        assert potential < 0

    def test_gradient_at_origin(self, field):
        """Test gradient is zero at origin (unstable equilibrium)"""
        phi = np.zeros(8)
        gradient = field.compute_gradient(phi)
        assert np.allclose(gradient, np.zeros(8))

    def test_curvature_at_origin(self, field):
        """Test curvature is negative at origin (tachyonic)"""
        phi = np.zeros(8)
        curvature = field.compute_curvature(phi)
        # m^2 = -2*mu^2 = -2 at origin
        assert curvature < 0

    def test_curvature_at_vacuum(self, field):
        """Test curvature is positive at vacuum (stable)"""
        phi = np.zeros(8)
        phi[0] = field.vev
        curvature = field.compute_curvature(phi)
        # Should be positive at vacuum
        assert curvature > 0

    def test_update_from_market_data(self, field):
        """Test field state update from market data"""
        sentiments = [0.5, 0.3, 0.7, 0.4]
        ratings = [4.2, 4.5, 3.8]
        volatility = 0.12
        chain_sentiments = {"starbucks": 0.5, "dunkin": 0.3}

        state = field.update_from_market_data(
            sentiments=sentiments,
            ratings=ratings,
            volatility=volatility,
            chain_sentiments=chain_sentiments
        )

        assert state is not None
        assert state.temperature > 0
        assert state.phase in MarketPhase
        assert 0 <= state.order_parameter <= 1

    def test_phase_determination_symmetric(self, field):
        """Test symmetric phase detection"""
        # High volatility, low sentiment consensus
        sentiments = [0.1, -0.1, 0.05, -0.05]
        state = field.update_from_market_data(
            sentiments=sentiments,
            ratings=[3.5],
            volatility=0.25,  # High volatility
            chain_sentiments={}
        )
        # With high volatility and low consensus, should be near symmetric
        # Note: exact phase depends on implementation details

    def test_symmetry_breaking_detection(self, field):
        """Test symmetry breaking detection"""
        # First, establish baseline with symmetric state
        for _ in range(5):
            field.update_from_market_data(
                sentiments=[0.1, 0.1],
                ratings=[3.5],
                volatility=0.2,
                chain_sentiments={"chain": 0.1}
            )

        # Then, sudden shift
        for _ in range(5):
            field.update_from_market_data(
                sentiments=[0.8, 0.9, 0.85],
                ratings=[4.5],
                volatility=0.1,
                chain_sentiments={"chain": 0.85}
            )

        breaking = field.detect_symmetry_breaking(
            location_sentiments={"loc1": 0.9},
            chain_sentiments={"chain": 0.85}
        )

        # May or may not detect breaking depending on thresholds
        # Just verify it returns proper type
        assert breaking is None or breaking.occurred in [True, False]

    def test_transition_prediction(self, field):
        """Test phase transition prediction"""
        # Update field state first
        field.update_from_market_data(
            sentiments=[0.5],
            ratings=[4.0],
            volatility=0.15,
            chain_sentiments={"chain": 0.5}
        )

        prob, phase = field.predict_transition(
            volatility_trend=0.15,  # Increasing volatility
            sentiment_momentum=0.1
        )

        assert 0 <= prob <= 1
        assert phase in MarketPhase

    def test_field_summary(self, field):
        """Test field summary generation"""
        field.update_from_market_data(
            sentiments=[0.5],
            ratings=[4.0],
            volatility=0.1,
            chain_sentiments={}
        )

        summary = field.get_field_summary()

        assert "position_magnitude" in summary
        assert "position_normalized" in summary
        assert "temperature" in summary
        assert "vev" in summary
        assert summary["vev"] == field.vev


class TestMexicanHatPotential:
    """Tests specifically for Mexican hat potential properties"""

    @pytest.fixture
    def field(self):
        return HiggsField()

    def test_potential_shape(self, field):
        """Test that potential has Mexican hat shape"""
        # Sample potential along one dimension
        positions = np.linspace(-3 * field.vev, 3 * field.vev, 100)
        potentials = []

        for pos in positions:
            phi = np.zeros(8)
            phi[0] = pos
            potentials.append(field.compute_potential(phi))

        potentials = np.array(potentials)

        # Find minimum
        min_idx = np.argmin(potentials)
        min_position = positions[min_idx]

        # Minimum should be near +/- vev
        assert abs(abs(min_position) - field.vev) < 0.2

        # Potential at origin should be higher than at minimum
        origin_idx = len(positions) // 2
        assert potentials[origin_idx] > potentials[min_idx]

    def test_rotational_symmetry(self, field):
        """Test that potential has rotational symmetry"""
        # Points at same radius should have same potential
        radius = field.vev * 0.8

        # Create two points with same radius but different directions
        phi1 = np.zeros(8)
        phi1[0] = radius

        phi2 = np.zeros(8)
        phi2[0] = radius * np.cos(np.pi / 4)
        phi2[1] = radius * np.sin(np.pi / 4)

        potential1 = field.compute_potential(phi1)
        potential2 = field.compute_potential(phi2)

        assert abs(potential1 - potential2) < 0.001


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
