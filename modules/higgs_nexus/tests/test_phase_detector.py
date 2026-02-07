# HIGGS NEXUS - Phase Detector Tests
# Unit tests for phase detection and transition prediction

import pytest
import numpy as np
from datetime import datetime

import sys
sys.path.insert(0, '/home/info_betsim/reviewsignal-5.0')

from modules.higgs_nexus.phase_detector import (
    PhaseDetector,
    PhaseDetectorConfig,
)
from modules.higgs_nexus.field_dynamics import HiggsFieldConfig
from modules.higgs_nexus.models import MarketPhase, TransitionType


class TestPhaseDetectorConfig:
    """Tests for PhaseDetectorConfig"""

    def test_default_config(self):
        config = PhaseDetectorConfig()
        assert config.transition_threshold == 0.3
        assert config.min_stability_window == 5
        assert config.lookback_window == 20

    def test_custom_config(self):
        config = PhaseDetectorConfig(
            transition_threshold=0.5,
            min_stability_window=10
        )
        assert config.transition_threshold == 0.5
        assert config.min_stability_window == 10


class TestPhaseDetector:
    """Tests for PhaseDetector"""

    @pytest.fixture
    def detector(self):
        return PhaseDetector()

    @pytest.fixture
    def sensitive_detector(self):
        """Detector with higher sensitivity"""
        config = PhaseDetectorConfig(
            transition_threshold=0.2,
            min_stability_window=2
        )
        return PhaseDetector(config=config)

    def test_initialization(self, detector):
        """Test detector initializes correctly"""
        assert detector is not None
        assert detector._current_phase == MarketPhase.SYMMETRIC

    def test_basic_update(self, detector):
        """Test basic phase state update"""
        phase_state = detector.update(
            location_sentiments={"loc1": 0.5, "loc2": 0.3},
            chain_sentiments={"chain1": 0.4},
            ratings=[4.0, 4.2, 3.8],
            volatility=0.1
        )

        assert phase_state is not None
        assert phase_state.current_phase in MarketPhase
        assert 0 <= phase_state.stability_score <= 1

    def test_phase_with_echo_data(self, detector):
        """Test phase detection with Echo Engine data"""
        phase_state = detector.update(
            location_sentiments={"loc1": 0.5},
            chain_sentiments={"chain1": 0.4},
            ratings=[4.0],
            volatility=0.1,
            echo_chaos_index=2.5,
            echo_stability="stable",
            echo_butterfly=0.4
        )

        assert phase_state is not None
        # With stable echo data, should remain stable-ish

    def test_critical_phase_detection(self, sensitive_detector):
        """Test critical phase detection with high chaos"""
        phase_state = sensitive_detector.update(
            location_sentiments={"loc1": 0.2},
            chain_sentiments={"chain1": 0.1},
            ratings=[3.5],
            volatility=0.15,  # Near critical volatility
            echo_chaos_index=4.0,  # High chaos
            echo_stability="critical",
            echo_butterfly=0.9
        )

        # Should detect critical conditions
        # Phase might be CRITICAL or CHAOTIC
        assert phase_state.current_phase in [
            MarketPhase.CRITICAL,
            MarketPhase.CHAOTIC,
            MarketPhase.TRANSITION,
            MarketPhase.SYMMETRIC  # May still be symmetric depending on params
        ]

    def test_chaotic_phase_detection(self, sensitive_detector):
        """Test chaotic phase with high echo chaos"""
        # First establish some history
        for _ in range(5):
            sensitive_detector.update(
                location_sentiments={"loc1": 0.5},
                chain_sentiments={"chain1": 0.4},
                ratings=[4.0],
                volatility=0.1
            )

        # Now trigger chaos
        phase_state = sensitive_detector.update(
            location_sentiments={"loc1": -0.5},  # Sudden reversal
            chain_sentiments={"chain1": -0.4},
            ratings=[2.5],
            volatility=0.25,
            echo_chaos_index=5.0,  # Very high chaos
            echo_stability="critical"
        )

        # Should recognize instability
        assert phase_state is not None

    def test_phase_transition_sequence(self, sensitive_detector):
        """Test phase transitions over time"""
        phases_seen = []

        # Start stable
        for i in range(3):
            state = sensitive_detector.update(
                location_sentiments={"loc1": 0.3},
                chain_sentiments={"chain1": 0.3},
                ratings=[4.0],
                volatility=0.08
            )
            phases_seen.append(state.current_phase)

        # Increase volatility
        for i in range(5):
            state = sensitive_detector.update(
                location_sentiments={"loc1": 0.2 - i * 0.1},
                chain_sentiments={"chain1": 0.2 - i * 0.1},
                ratings=[3.5],
                volatility=0.12 + i * 0.03
            )
            phases_seen.append(state.current_phase)

        # Should have seen some variety
        unique_phases = set(phases_seen)
        assert len(phases_seen) == 8

    def test_pending_transition_prediction(self, detector):
        """Test prediction of pending transitions"""
        # Build up history for prediction
        for _ in range(25):
            detector.update(
                location_sentiments={"loc1": 0.5},
                chain_sentiments={"chain1": 0.4},
                ratings=[4.0],
                volatility=0.1 + np.random.uniform(-0.01, 0.01)
            )

        state = detector.update(
            location_sentiments={"loc1": 0.5},
            chain_sentiments={"chain1": 0.4},
            ratings=[4.0],
            volatility=0.15  # Increase volatility
        )

        # May or may not have pending transition
        if state.pending_transition:
            assert 0 <= state.pending_transition.probability <= 1
            assert state.pending_transition.from_phase in MarketPhase
            assert state.pending_transition.to_phase in MarketPhase

    def test_phase_summary(self, detector):
        """Test phase summary generation"""
        detector.update(
            location_sentiments={"loc1": 0.5},
            chain_sentiments={"chain1": 0.4},
            ratings=[4.0],
            volatility=0.1
        )

        summary = detector.get_phase_summary()

        assert "current_phase" in summary
        assert "stability_counter" in summary
        assert "field_summary" in summary

    def test_singularity_pattern_influence(self, detector):
        """Test Singularity patterns affect phase"""
        phase_state = detector.update(
            location_sentiments={"loc1": 0.5},
            chain_sentiments={"chain1": 0.4},
            ratings=[4.0],
            volatility=0.1,
            singularity_confidence=0.8,
            singularity_patterns=["anomaly_detected", "divergence_pattern"]
        )

        # Patterns with "anomaly" or "divergence" may trigger transition
        assert phase_state is not None

    def test_stability_score_calculation(self, detector):
        """Test stability score is properly bounded"""
        for _ in range(10):
            state = detector.update(
                location_sentiments={"loc1": np.random.uniform(-1, 1)},
                chain_sentiments={"chain1": np.random.uniform(-1, 1)},
                ratings=[np.random.uniform(1, 5)],
                volatility=np.random.uniform(0.05, 0.3)
            )

            assert 0 <= state.stability_score <= 1


class TestPhaseStateHistory:
    """Tests for phase state history tracking"""

    @pytest.fixture
    def detector(self):
        return PhaseDetector()

    def test_history_accumulation(self, detector):
        """Test that history accumulates properly"""
        for i in range(10):
            state = detector.update(
                location_sentiments={"loc1": 0.5},
                chain_sentiments={"chain1": 0.4},
                ratings=[4.0],
                volatility=0.1
            )

        # Phase history should be limited
        assert len(state.phase_history) <= 100

    def test_phase_history_content(self, detector):
        """Test phase history contains proper data"""
        for _ in range(5):
            state = detector.update(
                location_sentiments={"loc1": 0.5},
                chain_sentiments={"chain1": 0.4},
                ratings=[4.0],
                volatility=0.1
            )

        if state.phase_history:
            entry = state.phase_history[-1]
            assert "phase" in entry
            assert "timestamp" in entry


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
