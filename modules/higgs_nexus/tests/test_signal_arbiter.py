# HIGGS NEXUS - Signal Arbiter Tests
# Unit tests for signal arbitration between Echo and Singularity

import pytest
import numpy as np
from datetime import datetime

import sys
sys.path.insert(0, '/home/info_betsim/reviewsignal-5.0')

from modules.higgs_nexus.signal_arbiter import (
    SignalArbiter,
    ArbiterConfig,
)
from modules.higgs_nexus.models import (
    MarketPhase,
    EngineAuthority,
    PhaseState,
    FieldState,
    FieldPotential,
)


class TestArbiterConfig:
    """Tests for ArbiterConfig"""

    def test_default_config(self):
        config = ArbiterConfig()
        assert config.base_echo_weight == 0.5
        assert config.base_singularity_weight == 0.5
        assert config.swarm_weight == 0.2

    def test_phase_weights_initialized(self):
        config = ArbiterConfig()
        assert MarketPhase.SYMMETRIC.value in config.phase_weights
        assert MarketPhase.CRITICAL.value in config.phase_weights


class TestSignalArbiter:
    """Tests for SignalArbiter"""

    @pytest.fixture
    def arbiter(self):
        return SignalArbiter()

    @pytest.fixture
    def sample_phase_state(self):
        """Create sample phase state for testing"""
        potential = FieldPotential(
            position=np.zeros(8),
            potential_value=0.0,
            gradient=np.zeros(8),
            curvature=-2.0,
            distance_from_minimum=2.0,
            vacuum_expectation_value=2.0
        )
        field_state = FieldState(
            potential=potential,
            phase=MarketPhase.SYMMETRIC,
            temperature=1.0,
            critical_temperature=1.5,
            order_parameter=0.3,
            susceptibility=0.5,
            correlation_length=1.0
        )
        return PhaseState(
            current_phase=MarketPhase.SYMMETRIC,
            field_state=field_state,
            pending_transition=None,
            stability_score=0.7
        )

    def test_arbiter_initialization(self, arbiter):
        """Test arbiter initializes correctly"""
        assert arbiter is not None
        assert arbiter.config is not None

    def test_basic_arbitration(self, arbiter, sample_phase_state):
        """Test basic signal arbitration"""
        signal = arbiter.arbitrate(
            # Echo
            echo_signal="BUY",
            echo_confidence=0.7,
            echo_chaos_index=1.5,
            echo_butterfly=0.4,
            echo_stability="stable",
            echo_insights=["System stable"],
            echo_risk_factors=[],
            echo_raw={},
            # Singularity
            singularity_action="BUY",
            singularity_confidence=0.65,
            singularity_signal_strength=0.3,
            singularity_insights=["Positive trend"],
            singularity_risk_factors=[],
            singularity_raw={},
            # Phase
            phase_state=sample_phase_state,
            # Swarm
            swarm_opinion=0.2,
            swarm_confidence=0.5,
            swarm_consensus=True,
            swarm_dissent=[]
        )

        assert signal is not None
        assert signal.action in ["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]
        assert 0 <= signal.confidence <= 1
        assert -1 <= signal.signal_strength <= 1

    def test_conflicting_signals(self, arbiter, sample_phase_state):
        """Test arbitration with conflicting engine signals"""
        signal = arbiter.arbitrate(
            # Echo says BUY
            echo_signal="BUY",
            echo_confidence=0.8,
            echo_chaos_index=1.5,
            echo_butterfly=0.3,
            echo_stability="stable",
            echo_insights=[],
            echo_risk_factors=[],
            echo_raw={},
            # Singularity says SELL
            singularity_action="SELL",
            singularity_confidence=0.75,
            singularity_signal_strength=-0.4,
            singularity_insights=[],
            singularity_risk_factors=[],
            singularity_raw={},
            # Phase
            phase_state=sample_phase_state,
            # Swarm
            swarm_opinion=0.0,
            swarm_confidence=0.3,
            swarm_consensus=False,
            swarm_dissent=["Split signals"]
        )

        # Should produce some result (likely HOLD given conflict)
        assert signal is not None
        assert signal.action in ["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]

    def test_echo_dominant_in_critical_phase(self, arbiter):
        """Test Echo gets more weight in critical phase"""
        # Create critical phase state
        potential = FieldPotential(
            position=np.zeros(8),
            potential_value=0.0,
            gradient=np.zeros(8),
            curvature=-2.0,
            distance_from_minimum=2.0,
            vacuum_expectation_value=2.0
        )
        field_state = FieldState(
            potential=potential,
            phase=MarketPhase.CRITICAL,
            temperature=1.5,
            critical_temperature=1.5,
            order_parameter=0.5,
            susceptibility=0.9,
            correlation_length=5.0
        )
        critical_phase = PhaseState(
            current_phase=MarketPhase.CRITICAL,
            field_state=field_state,
            pending_transition=None,
            stability_score=0.3
        )

        signal = arbiter.arbitrate(
            echo_signal="SELL",
            echo_confidence=0.8,
            echo_chaos_index=3.5,
            echo_butterfly=0.7,
            echo_stability="unstable",
            echo_insights=[],
            echo_risk_factors=[],
            echo_raw={},
            singularity_action="BUY",
            singularity_confidence=0.6,
            singularity_signal_strength=0.3,
            singularity_insights=[],
            singularity_risk_factors=[],
            singularity_raw={},
            phase_state=critical_phase,
            swarm_opinion=0.0,
            swarm_confidence=0.3,
            swarm_consensus=False,
            swarm_dissent=[]
        )

        # Echo should have more weight in critical phase
        assert signal.echo_contribution.weight > signal.singularity_contribution.weight

    def test_authority_determination(self, arbiter, sample_phase_state):
        """Test authority is correctly determined"""
        signal = arbiter.arbitrate(
            echo_signal="HOLD",
            echo_confidence=0.5,
            echo_chaos_index=1.0,
            echo_butterfly=0.3,
            echo_stability="stable",
            echo_insights=[],
            echo_risk_factors=[],
            echo_raw={},
            singularity_action="HOLD",
            singularity_confidence=0.5,
            singularity_signal_strength=0.0,
            singularity_insights=[],
            singularity_risk_factors=[],
            singularity_raw={},
            phase_state=sample_phase_state,
            swarm_opinion=0.0,
            swarm_confidence=0.5,
            swarm_consensus=True,
            swarm_dissent=[]
        )

        assert signal.authority in EngineAuthority

    def test_phase_adjustment_in_chaotic(self, arbiter):
        """Test signal is adjusted in chaotic phase"""
        potential = FieldPotential(
            position=np.zeros(8),
            potential_value=0.0,
            gradient=np.zeros(8),
            curvature=-2.0,
            distance_from_minimum=2.0,
            vacuum_expectation_value=2.0
        )
        field_state = FieldState(
            potential=potential,
            phase=MarketPhase.CHAOTIC,
            temperature=2.0,
            critical_temperature=1.5,
            order_parameter=0.8,
            susceptibility=0.95,
            correlation_length=8.0
        )
        chaotic_phase = PhaseState(
            current_phase=MarketPhase.CHAOTIC,
            field_state=field_state,
            pending_transition=None,
            stability_score=0.1
        )

        signal = arbiter.arbitrate(
            echo_signal="STRONG_BUY",
            echo_confidence=0.5,  # Low confidence
            echo_chaos_index=4.0,
            echo_butterfly=0.85,  # High butterfly
            echo_stability="critical",
            echo_insights=[],
            echo_risk_factors=[],
            echo_raw={},
            singularity_action="STRONG_BUY",
            singularity_confidence=0.5,
            singularity_signal_strength=0.6,
            singularity_insights=[],
            singularity_risk_factors=[],
            singularity_raw={},
            phase_state=chaotic_phase,
            swarm_opinion=0.5,
            swarm_confidence=0.4,
            swarm_consensus=False,
            swarm_dissent=[]
        )

        # Should be moderated due to chaotic phase
        # STRONG_BUY might become HOLD or BUY
        assert signal.action in ["HOLD", "BUY", "STRONG_BUY"]

    def test_swarm_veto(self, arbiter, sample_phase_state):
        """Test swarm can veto with high consensus"""
        arbiter.config.swarm_veto_threshold = 0.7

        signal = arbiter.arbitrate(
            echo_signal="BUY",
            echo_confidence=0.6,
            echo_chaos_index=1.5,
            echo_butterfly=0.4,
            echo_stability="stable",
            echo_insights=[],
            echo_risk_factors=[],
            echo_raw={},
            singularity_action="BUY",
            singularity_confidence=0.55,
            singularity_signal_strength=0.3,
            singularity_insights=[],
            singularity_risk_factors=[],
            singularity_raw={},
            phase_state=sample_phase_state,
            # Swarm strongly disagrees
            swarm_opinion=-0.5,
            swarm_confidence=0.9,  # High confidence
            swarm_consensus=True,
            swarm_dissent=[]
        )

        # Swarm veto should moderate the signal
        assert signal.phase_adjusted  # Should be marked as adjusted

    def test_arbitration_stats(self, arbiter, sample_phase_state):
        """Test arbitration stats tracking"""
        # Run multiple arbitrations
        for _ in range(5):
            arbiter.arbitrate(
                echo_signal="BUY",
                echo_confidence=0.7,
                echo_chaos_index=1.5,
                echo_butterfly=0.4,
                echo_stability="stable",
                echo_insights=[],
                echo_risk_factors=[],
                echo_raw={},
                singularity_action="BUY",
                singularity_confidence=0.65,
                singularity_signal_strength=0.3,
                singularity_insights=[],
                singularity_risk_factors=[],
                singularity_raw={},
                phase_state=sample_phase_state,
                swarm_opinion=0.2,
                swarm_confidence=0.5,
                swarm_consensus=True,
                swarm_dissent=[]
            )

        stats = arbiter.get_arbitration_stats()

        assert stats["count"] == 5
        assert "action_distribution" in stats
        assert "avg_confidence" in stats

    def test_signal_to_dict(self, arbiter, sample_phase_state):
        """Test signal can be serialized to dict"""
        signal = arbiter.arbitrate(
            echo_signal="HOLD",
            echo_confidence=0.5,
            echo_chaos_index=1.0,
            echo_butterfly=0.3,
            echo_stability="stable",
            echo_insights=[],
            echo_risk_factors=[],
            echo_raw={},
            singularity_action="HOLD",
            singularity_confidence=0.5,
            singularity_signal_strength=0.0,
            singularity_insights=[],
            singularity_risk_factors=[],
            singularity_raw={},
            phase_state=sample_phase_state,
            swarm_opinion=0.0,
            swarm_confidence=0.5,
            swarm_consensus=True,
            swarm_dissent=[]
        )

        d = signal.to_dict()

        assert "action" in d
        assert "confidence" in d
        assert "market_phase" in d
        assert "timestamp" in d


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
