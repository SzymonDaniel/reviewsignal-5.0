#!/usr/bin/env python3
"""
Unit tests for Echo Engine - Quantum-Inspired Sentiment Propagation
Tests core functionality without database dependency.
"""

import pytest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.echo_engine import (
    EchoEngine,
    EchoEngineConfig,
    LocationState,
    EchoResult,
    MonteCarloResult,
    TradingSignal,
    SystemStability,
    SignalType,
    PropagationType,
    haversine_distance,
    normalize_sentiment,
)


# ═══════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_locations():
    """Create sample locations for testing."""
    np.random.seed(42)

    chains = ["starbucks", "mcdonalds", "kfc"]
    cities = ["New York, NY, USA", "Los Angeles, CA, USA"]
    categories = ["coffee", "fast_food", "fast_food"]

    city_coords = {
        "New York, NY, USA": (40.7128, -74.0060),
        "Los Angeles, CA, USA": (34.0522, -118.2437),
    }

    locations = []
    loc_id = 0

    for chain_idx, chain in enumerate(chains):
        for city in cities:
            base_lat, base_lon = city_coords[city]
            for i in range(3):
                lat = base_lat + np.random.uniform(-0.05, 0.05)
                lon = base_lon + np.random.uniform(-0.05, 0.05)
                rating = np.random.uniform(2.5, 5.0)

                state = LocationState(
                    location_id=f"loc_{loc_id:04d}",
                    name=f"{chain.title()} - {city.split(',')[0]} #{i+1}",
                    latitude=lat,
                    longitude=lon,
                    chain_id=chain,
                    city=city,
                    category=categories[chain_idx],
                    current_sentiment=normalize_sentiment(rating),
                    current_rating=rating,
                    review_count=np.random.randint(50, 500)
                )
                locations.append(state)
                loc_id += 1

    return locations


@pytest.fixture
def echo_engine(sample_locations):
    """Create Echo Engine instance."""
    return EchoEngine(sample_locations)


@pytest.fixture
def custom_config():
    """Create custom configuration."""
    return EchoEngineConfig(
        self_influence=0.6,
        geo_weight_max=0.2,
        geo_radius_km=30.0,
        brand_weight=0.25,
        city_weight=0.1,
        category_weight=0.08,
        default_time_steps=5,
        default_perturbation=-0.3
    )


# ═══════════════════════════════════════════════════════════════════
# HELPER FUNCTION TESTS
# ═══════════════════════════════════════════════════════════════════

class TestHelperFunctions:
    """Tests for helper functions."""

    def test_haversine_distance_same_point(self):
        """Distance between same point should be 0."""
        dist = haversine_distance(40.7128, -74.0060, 40.7128, -74.0060)
        assert dist == 0.0

    def test_haversine_distance_nyc_to_la(self):
        """NYC to LA is approximately 3944 km."""
        dist = haversine_distance(40.7128, -74.0060, 34.0522, -118.2437)
        assert 3900 < dist < 4000  # ~3944 km

    def test_haversine_distance_short(self):
        """Short distance test (< 1 km)."""
        dist = haversine_distance(40.7128, -74.0060, 40.7138, -74.0070)
        assert 0 < dist < 2  # Should be less than 2 km

    def test_normalize_sentiment_middle(self):
        """Rating of 3 should give sentiment of 0."""
        sentiment = normalize_sentiment(3.0, 1.0, 5.0)
        assert sentiment == 0.0

    def test_normalize_sentiment_high(self):
        """Rating of 5 should give sentiment of 1."""
        sentiment = normalize_sentiment(5.0, 1.0, 5.0)
        assert sentiment == 1.0

    def test_normalize_sentiment_low(self):
        """Rating of 1 should give sentiment of -1."""
        sentiment = normalize_sentiment(1.0, 1.0, 5.0)
        assert sentiment == -1.0


# ═══════════════════════════════════════════════════════════════════
# LOCATION STATE TESTS
# ═══════════════════════════════════════════════════════════════════

class TestLocationState:
    """Tests for LocationState dataclass."""

    def test_location_state_creation(self):
        """Test basic LocationState creation."""
        state = LocationState(
            location_id="test_001",
            name="Test Location",
            latitude=40.7128,
            longitude=-74.0060,
            chain_id="starbucks",
            city="New York, NY, USA",
            category="coffee",
            current_sentiment=0.5,
            current_rating=4.0,
            review_count=100
        )

        assert state.location_id == "test_001"
        assert state.name == "Test Location"
        assert state.current_rating == 4.0

    def test_location_state_to_dict(self):
        """Test LocationState serialization."""
        state = LocationState(
            location_id="test_001",
            name="Test Location",
            latitude=40.7128,
            longitude=-74.0060,
            chain_id="starbucks",
            city="New York, NY, USA",
            category="coffee",
            current_sentiment=0.5,
            current_rating=4.0,
            review_count=100
        )

        data = state.to_dict()
        assert isinstance(data, dict)
        assert data["location_id"] == "test_001"
        assert data["current_rating"] == 4.0


# ═══════════════════════════════════════════════════════════════════
# ECHO ENGINE TESTS
# ═══════════════════════════════════════════════════════════════════

class TestEchoEngineInitialization:
    """Tests for Echo Engine initialization."""

    def test_engine_initialization(self, sample_locations):
        """Test basic engine initialization."""
        engine = EchoEngine(sample_locations)

        assert engine.n == len(sample_locations)
        assert len(engine._chain_locations) == 3
        assert len(engine._city_locations) == 2

    def test_engine_with_custom_config(self, sample_locations, custom_config):
        """Test engine with custom configuration."""
        engine = EchoEngine(sample_locations, config=custom_config)

        assert engine.config.self_influence == 0.6
        assert engine.config.brand_weight == 0.25

    def test_location_index_map(self, echo_engine):
        """Test location index mapping."""
        assert "loc_0000" in echo_engine._location_idx_map
        assert echo_engine._location_idx_map["loc_0000"] == 0


class TestEchoEngineStateVector:
    """Tests for state vector operations."""

    def test_get_state_vector(self, echo_engine):
        """Test state vector generation."""
        x = echo_engine.get_state_vector()

        assert x.shape == (echo_engine.n,)
        assert x.dtype == np.float64

    def test_state_vector_normalized(self, echo_engine):
        """Test that state vector is normalized."""
        x = echo_engine.get_state_vector()

        # Z-scored: mean should be ~0, std should be ~1
        assert abs(np.mean(x)) < 0.01
        # Std might not be exactly 1 due to small sample
        assert 0.5 < np.std(x) < 1.5


class TestPropagationMatrix:
    """Tests for propagation matrix."""

    def test_propagation_matrix_shape(self, echo_engine):
        """Test propagation matrix dimensions."""
        F = echo_engine._build_propagation_matrix()

        assert F.shape == (echo_engine.n, echo_engine.n)

    def test_propagation_matrix_row_normalized(self, echo_engine):
        """Test that rows sum to 1 (stochastic matrix)."""
        F = echo_engine._build_propagation_matrix()
        row_sums = np.array(F.sum(axis=1)).flatten()

        np.testing.assert_array_almost_equal(row_sums, np.ones(echo_engine.n), decimal=5)

    def test_propagation_matrix_sparse(self, echo_engine):
        """Test that matrix is sparse (not fully dense)."""
        F = echo_engine._build_propagation_matrix()

        # For small test datasets, density can be high due to many connections
        # In real datasets with 22k+ locations, density will be much lower
        density = F.nnz / (echo_engine.n ** 2)
        # Just check it's not fully dense (all non-zero)
        assert density < 1.0  # Not fully dense


class TestEvolution:
    """Tests for forward/backward evolution."""

    def test_forward_evolution(self, echo_engine):
        """Test forward evolution."""
        x = echo_engine.get_state_vector()
        x_evolved = echo_engine.evolve_forward(x, T=5)

        assert x_evolved.shape == x.shape

    def test_forward_evolution_changes_state(self, echo_engine):
        """Evolution should change the state."""
        x = echo_engine.get_state_vector()
        x_evolved = echo_engine.evolve_forward(x, T=5)

        # States should differ (unless perfectly uniform)
        assert not np.allclose(x, x_evolved)

    def test_backward_evolution(self, echo_engine):
        """Test backward evolution."""
        x = echo_engine.get_state_vector()
        x_T = echo_engine.evolve_forward(x, T=5)
        x_back = echo_engine.evolve_backward(x_T, T=5)

        assert x_back.shape == x.shape


class TestPerturbation:
    """Tests for perturbation injection."""

    def test_inject_perturbation(self, echo_engine):
        """Test perturbation injection."""
        x = echo_engine.get_state_vector()
        x_pert = echo_engine.inject_perturbation(x, location_idx=0, delta=-0.5)

        assert x_pert[0] == x[0] - 0.5
        # Other values should be unchanged
        assert np.allclose(x_pert[1:], x[1:])

    def test_perturbation_does_not_modify_original(self, echo_engine):
        """Perturbation should not modify original array."""
        x = echo_engine.get_state_vector()
        x_original = x.copy()

        _ = echo_engine.inject_perturbation(x, location_idx=0, delta=-0.5)

        np.testing.assert_array_equal(x, x_original)


class TestEchoComputation:
    """Tests for echo computation."""

    def test_compute_echo_returns_result(self, echo_engine):
        """Test that compute_echo returns EchoResult."""
        result = echo_engine.compute_echo(location_idx=0)

        assert isinstance(result, EchoResult)

    def test_echo_result_has_required_fields(self, echo_engine):
        """Test EchoResult has all required fields."""
        result = echo_engine.compute_echo(location_idx=0)

        assert result.echo_value >= 0
        assert result.source_location is not None
        assert result.source_location_id is not None
        assert result.butterfly_coefficient >= 0
        assert isinstance(result.system_stability, SystemStability)
        assert isinstance(result.top_affected_locations, list)

    def test_compute_echo_by_location_id(self, echo_engine):
        """Test echo computation by location ID."""
        result = echo_engine.compute_echo_by_location_id("loc_0000")

        assert result.source_location_id == "loc_0000"

    def test_compute_echo_invalid_location_id(self, echo_engine):
        """Test error on invalid location ID."""
        with pytest.raises(ValueError):
            echo_engine.compute_echo_by_location_id("invalid_id")

    def test_echo_result_to_dict(self, echo_engine):
        """Test EchoResult serialization."""
        result = echo_engine.compute_echo(location_idx=0)
        data = result.to_dict()

        assert isinstance(data, dict)
        assert "echo_value" in data
        assert "system_stability" in data
        assert data["system_stability"] in ["stable", "unstable", "chaotic"]


class TestMonteCarloSimulation:
    """Tests for Monte Carlo simulation."""

    def test_monte_carlo_returns_result(self, echo_engine):
        """Test Monte Carlo returns MonteCarloResult."""
        result = echo_engine.run_monte_carlo(n_trials=20, parallel=False)

        assert isinstance(result, MonteCarloResult)

    def test_monte_carlo_statistics(self, echo_engine):
        """Test Monte Carlo statistics are reasonable."""
        result = echo_engine.run_monte_carlo(n_trials=50, parallel=False)

        assert result.n_trials == 50
        assert result.mean_echo >= 0
        assert result.std_echo >= 0
        assert result.max_echo >= result.mean_echo
        assert result.min_echo <= result.mean_echo

    def test_monte_carlo_stability_distribution(self, echo_engine):
        """Test stability distribution sums to 1."""
        result = echo_engine.run_monte_carlo(n_trials=50, parallel=False)

        total = sum(result.stability_distribution.values())
        assert abs(total - 1.0) < 0.01

    def test_monte_carlo_critical_locations(self, echo_engine):
        """Test critical locations are identified."""
        result = echo_engine.run_monte_carlo(n_trials=50, parallel=False)

        assert isinstance(result.critical_locations, list)
        if result.critical_locations:
            assert "location_id" in result.critical_locations[0]
            assert "mean_echo" in result.critical_locations[0]


class TestTradingSignal:
    """Tests for trading signal generation."""

    def test_generate_trading_signal(self, echo_engine):
        """Test trading signal generation."""
        signal = echo_engine.generate_trading_signal(n_trials=30)

        assert isinstance(signal, TradingSignal)

    def test_trading_signal_fields(self, echo_engine):
        """Test trading signal has required fields."""
        signal = echo_engine.generate_trading_signal(n_trials=30)

        assert signal.brand is not None
        assert isinstance(signal.signal, SignalType)
        assert 0 <= signal.confidence <= 1
        assert signal.chaos_index >= 0
        assert signal.recommendation is not None

    def test_trading_signal_for_brand(self, echo_engine):
        """Test trading signal for specific brand."""
        signal = echo_engine.generate_trading_signal(brand="starbucks", n_trials=30)

        assert signal.brand == "starbucks"

    def test_trading_signal_unknown_brand(self, echo_engine):
        """Test trading signal for unknown brand."""
        signal = echo_engine.generate_trading_signal(brand="nonexistent", n_trials=30)

        assert signal.signal == SignalType.HOLD
        assert signal.confidence == 0.0

    def test_trading_signal_to_dict(self, echo_engine):
        """Test TradingSignal serialization."""
        signal = echo_engine.generate_trading_signal(n_trials=30)
        data = signal.to_dict()

        assert isinstance(data, dict)
        assert data["signal"] in ["buy", "hold", "sell"]


class TestLocationCriticality:
    """Tests for location criticality analysis."""

    def test_get_location_criticality(self, echo_engine):
        """Test location criticality analysis."""
        result = echo_engine.get_location_criticality("loc_0000", n_samples=20)

        assert isinstance(result, dict)
        assert result["location_id"] == "loc_0000"
        assert "mean_echo" in result
        assert "criticality" in result

    def test_criticality_levels(self, echo_engine):
        """Test criticality level is valid."""
        result = echo_engine.get_location_criticality("loc_0000", n_samples=20)

        assert result["criticality"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def test_criticality_invalid_location(self, echo_engine):
        """Test error on invalid location."""
        with pytest.raises(ValueError):
            echo_engine.get_location_criticality("invalid_id")


class TestSystemHealth:
    """Tests for system health check."""

    def test_get_system_health(self, echo_engine):
        """Test system health check."""
        health = echo_engine.get_system_health()

        assert isinstance(health, dict)
        assert "n_locations" in health
        assert "n_chains" in health
        assert "chaos_index" in health
        assert "overall_status" in health

    def test_system_health_status_valid(self, echo_engine):
        """Test health status is valid."""
        health = echo_engine.get_system_health()

        assert health["overall_status"] in ["HEALTHY", "CAUTION", "AT_RISK"]


# ═══════════════════════════════════════════════════════════════════
# ENUM TESTS
# ═══════════════════════════════════════════════════════════════════

class TestEnums:
    """Tests for enum values."""

    def test_system_stability_values(self):
        """Test SystemStability enum values."""
        assert SystemStability.STABLE.value == "stable"
        assert SystemStability.UNSTABLE.value == "unstable"
        assert SystemStability.CHAOTIC.value == "chaotic"

    def test_signal_type_values(self):
        """Test SignalType enum values."""
        assert SignalType.BUY.value == "buy"
        assert SignalType.HOLD.value == "hold"
        assert SignalType.SELL.value == "sell"

    def test_propagation_type_values(self):
        """Test PropagationType enum values."""
        assert PropagationType.GEOGRAPHIC.value == "geographic"
        assert PropagationType.BRAND.value == "brand"
        assert PropagationType.CITY.value == "city"
        assert PropagationType.CATEGORY.value == "category"


# ═══════════════════════════════════════════════════════════════════
# CONFIG TESTS
# ═══════════════════════════════════════════════════════════════════

class TestEchoEngineConfig:
    """Tests for EchoEngineConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = EchoEngineConfig()

        assert config.self_influence == 0.7
        assert config.brand_weight == 0.20
        assert config.default_time_steps == 10

    def test_custom_config(self, custom_config):
        """Test custom configuration."""
        assert custom_config.self_influence == 0.6
        assert custom_config.default_time_steps == 5

    def test_config_to_dict(self):
        """Test config serialization."""
        config = EchoEngineConfig()
        data = config.to_dict()

        assert isinstance(data, dict)
        assert "self_influence" in data


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Tests for edge cases."""

    def test_single_location(self):
        """Test with single location."""
        state = LocationState(
            location_id="single",
            name="Single Location",
            latitude=40.7128,
            longitude=-74.0060,
            chain_id="test",
            city="Test City",
            category="test",
            current_sentiment=0.5,
            current_rating=4.0,
            review_count=100
        )

        engine = EchoEngine([state])
        result = engine.compute_echo(0)

        assert result.echo_value >= 0

    def test_no_chain_id(self):
        """Test locations without chain_id."""
        locations = [
            LocationState(
                location_id=f"loc_{i}",
                name=f"Location {i}",
                latitude=40.7128 + i * 0.01,
                longitude=-74.0060,
                chain_id=None,  # No chain
                city="Test City",
                category=None,
                current_sentiment=0.5,
                current_rating=4.0,
                review_count=100
            )
            for i in range(5)
        ]

        engine = EchoEngine(locations)
        result = engine.compute_echo(0)

        assert result.echo_value >= 0

    def test_zero_time_steps(self, echo_engine):
        """Test with zero time steps returns unchanged state."""
        x = echo_engine.get_state_vector()
        x_evolved = echo_engine.evolve_forward(x, T=0)

        np.testing.assert_array_equal(x, x_evolved)


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
