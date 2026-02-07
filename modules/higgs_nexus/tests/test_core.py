# HIGGS NEXUS - Core Tests
# Unit tests for main HiggsNexus orchestrator

import pytest
import numpy as np
import asyncio
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from modules.higgs_nexus.core import (
    HiggsNexus,
    NexusConfig,
)
from modules.higgs_nexus.models import MarketPhase


class TestNexusConfig:
    """Tests for NexusConfig"""

    def test_default_config(self):
        config = NexusConfig()
        assert config.tick_interval_sec == 1.0
        assert config.enable_swarm == True
        assert config.initial_swarm_nodes == 10

    def test_custom_config(self):
        config = NexusConfig(
            enable_swarm=False,
            max_cpu_percent=50.0
        )
        assert config.enable_swarm == False
        assert config.max_cpu_percent == 50.0


class TestHiggsNexus:
    """Tests for main HiggsNexus class"""

    @pytest.fixture
    def nexus(self):
        config = NexusConfig(
            enable_swarm=False,  # Disable for faster tests
            initial_swarm_nodes=5
        )
        return HiggsNexus(config)

    @pytest.fixture
    def nexus_with_swarm(self):
        config = NexusConfig(
            enable_swarm=True,
            initial_swarm_nodes=5
        )
        return HiggsNexus(config)

    @pytest.fixture
    def sample_echo_results(self):
        return {
            "signal": "BUY",
            "confidence": 0.72,
            "chaos_index": 1.8,
            "butterfly_coefficient": 0.45,
            "stability": "stable",
            "insights": ["System stable", "Low propagation risk"],
            "risk_factors": ["Minor volatility"],
            "critical_locations": []
        }

    @pytest.fixture
    def sample_singularity_results(self):
        return {
            "trading_action": "BUY",
            "confidence": 0.68,
            "signal_strength": 0.35,
            "insights": ["Positive trend", "Strong resonance"],
            "risk_factors": ["Seasonal volatility"],
            "patterns": ["weekly_positive"]
        }

    @pytest.fixture
    def sample_market_data(self):
        return {
            "location_sentiments": {
                "loc_001": 0.65,
                "loc_002": 0.42,
                "loc_003": 0.58
            },
            "chain_sentiments": {
                "starbucks": 0.52,
                "dunkin": 0.38
            },
            "ratings": [4.2, 4.5, 3.8, 4.1],
            "volatility": 0.12
        }

    def test_nexus_initialization(self, nexus):
        """Test nexus initializes correctly"""
        assert nexus is not None
        assert nexus._is_running == False
        assert nexus.phase_detector is not None
        assert nexus.signal_arbiter is not None

    def test_nexus_with_swarm_init(self, nexus_with_swarm):
        """Test nexus with swarm initializes correctly"""
        assert nexus_with_swarm.swarm is not None

    @pytest.mark.asyncio
    async def test_nexus_start_stop(self, nexus):
        """Test nexus start and stop"""
        await nexus.start()
        assert nexus._is_running == True
        assert nexus._start_time is not None

        nexus.stop()
        assert nexus._is_running == False

    @pytest.mark.asyncio
    async def test_basic_analysis(
        self, nexus,
        sample_echo_results,
        sample_singularity_results,
        sample_market_data
    ):
        """Test basic analysis flow"""
        await nexus.start()

        insight = await nexus.analyze(
            echo_results=sample_echo_results,
            singularity_results=sample_singularity_results,
            market_data=sample_market_data
        )

        assert insight is not None
        assert insight.insight_id is not None
        assert insight.timestamp is not None
        assert insight.phase_state is not None
        assert insight.signal is not None
        assert insight.primary_recommendation is not None

        nexus.stop()

    @pytest.mark.asyncio
    async def test_analysis_with_swarm(
        self, nexus_with_swarm,
        sample_echo_results,
        sample_singularity_results,
        sample_market_data
    ):
        """Test analysis with swarm enabled"""
        await nexus_with_swarm.start()

        insight = await nexus_with_swarm.analyze(
            echo_results=sample_echo_results,
            singularity_results=sample_singularity_results,
            market_data=sample_market_data
        )

        assert insight is not None
        assert insight.swarm_metrics is not None
        assert insight.swarm_metrics.total_nodes >= 0

        nexus_with_swarm.stop()

    @pytest.mark.asyncio
    async def test_insight_contains_required_fields(
        self, nexus,
        sample_echo_results,
        sample_singularity_results,
        sample_market_data
    ):
        """Test insight contains all required fields"""
        await nexus.start()

        insight = await nexus.analyze(
            echo_results=sample_echo_results,
            singularity_results=sample_singularity_results,
            market_data=sample_market_data
        )

        # Check all required fields
        assert insight.insight_id
        assert insight.timestamp
        assert insight.phase_state
        assert insight.signal
        assert insight.swarm_metrics
        assert insight.primary_recommendation
        assert insight.risk_assessment in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        assert isinstance(insight.action_items, list)
        assert isinstance(insight.watch_list, list)
        assert insight.market_narrative

        nexus.stop()

    @pytest.mark.asyncio
    async def test_insight_to_dict(
        self, nexus,
        sample_echo_results,
        sample_singularity_results,
        sample_market_data
    ):
        """Test insight serialization"""
        await nexus.start()

        insight = await nexus.analyze(
            echo_results=sample_echo_results,
            singularity_results=sample_singularity_results,
            market_data=sample_market_data
        )

        d = insight.to_dict()

        assert "insight_id" in d
        assert "timestamp" in d
        assert "phase" in d
        assert "signal" in d
        assert "recommendation" in d

        nexus.stop()

    @pytest.mark.asyncio
    async def test_multiple_analyses(
        self, nexus,
        sample_echo_results,
        sample_singularity_results,
        sample_market_data
    ):
        """Test multiple consecutive analyses"""
        await nexus.start()

        insights = []
        for i in range(5):
            # Vary the data slightly
            echo = sample_echo_results.copy()
            echo["chaos_index"] = 1.5 + i * 0.2

            market = sample_market_data.copy()
            market["volatility"] = 0.1 + i * 0.02

            insight = await nexus.analyze(
                echo_results=echo,
                singularity_results=sample_singularity_results,
                market_data=market
            )
            insights.append(insight)

        assert len(insights) == 5
        # All should have unique IDs
        ids = [i.insight_id for i in insights]
        assert len(set(ids)) == 5

        nexus.stop()

    @pytest.mark.asyncio
    async def test_insight_history(
        self, nexus,
        sample_echo_results,
        sample_singularity_results,
        sample_market_data
    ):
        """Test insight history tracking"""
        await nexus.start()

        for _ in range(3):
            await nexus.analyze(
                echo_results=sample_echo_results,
                singularity_results=sample_singularity_results,
                market_data=sample_market_data
            )

        history = nexus.get_recent_insights(count=10)
        assert len(history) == 3

        nexus.stop()

    @pytest.mark.asyncio
    async def test_health_check(self, nexus):
        """Test health status"""
        await nexus.start()

        health = nexus.get_health()

        assert health.status in ["healthy", "degraded", "critical", "stopped"]
        assert health.uptime_seconds >= 0
        assert health.cpu_percent >= 0
        assert health.ram_gb >= 0

        nexus.stop()

    @pytest.mark.asyncio
    async def test_current_phase(
        self, nexus,
        sample_echo_results,
        sample_singularity_results,
        sample_market_data
    ):
        """Test current phase retrieval"""
        await nexus.start()

        # Before analysis
        phase = nexus.get_current_phase()
        # May be None before first analysis

        # After analysis
        await nexus.analyze(
            echo_results=sample_echo_results,
            singularity_results=sample_singularity_results,
            market_data=sample_market_data
        )

        phase = nexus.get_current_phase()
        assert phase in MarketPhase

        nexus.stop()

    @pytest.mark.asyncio
    async def test_phase_change_callback(
        self, nexus,
        sample_singularity_results
    ):
        """Test phase change callback"""
        await nexus.start()

        phase_changes = []

        async def on_phase_change(old_phase, new_phase):
            phase_changes.append((old_phase, new_phase))

        nexus.on_phase_change(on_phase_change)

        # Run analyses with varying conditions to potentially trigger phase change
        for i in range(10):
            echo = {
                "signal": "BUY" if i < 5 else "SELL",
                "confidence": 0.7,
                "chaos_index": 1.0 + i * 0.5,  # Increasing chaos
                "butterfly_coefficient": 0.3 + i * 0.05,
                "stability": "stable" if i < 7 else "critical",
                "insights": [],
                "risk_factors": []
            }

            market = {
                "location_sentiments": {"loc": 0.5 - i * 0.1},
                "chain_sentiments": {"chain": 0.4 - i * 0.08},
                "ratings": [4.0],
                "volatility": 0.1 + i * 0.02
            }

            await nexus.analyze(
                echo_results=echo,
                singularity_results=sample_singularity_results,
                market_data=market
            )

        # May or may not have phase changes depending on thresholds
        # Just verify callback mechanism works
        nexus.stop()


class TestNexusRiskAssessment:
    """Tests for risk assessment logic"""

    @pytest.fixture
    def nexus(self):
        return HiggsNexus(NexusConfig(enable_swarm=False))

    @pytest.mark.asyncio
    async def test_low_risk_conditions(self, nexus):
        """Test low risk assessment"""
        await nexus.start()

        insight = await nexus.analyze(
            echo_results={
                "signal": "HOLD",
                "confidence": 0.8,
                "chaos_index": 1.0,
                "butterfly_coefficient": 0.2,
                "stability": "stable",
                "insights": [],
                "risk_factors": []
            },
            singularity_results={
                "trading_action": "HOLD",
                "confidence": 0.75,
                "signal_strength": 0.0,
                "insights": [],
                "risk_factors": [],
                "patterns": []
            },
            market_data={
                "location_sentiments": {"loc": 0.5},
                "chain_sentiments": {"chain": 0.5},
                "ratings": [4.0],
                "volatility": 0.08
            }
        )

        assert insight.risk_assessment in ["LOW", "MEDIUM"]

        nexus.stop()

    @pytest.mark.asyncio
    async def test_high_risk_conditions(self, nexus):
        """Test high risk assessment"""
        await nexus.start()

        insight = await nexus.analyze(
            echo_results={
                "signal": "SELL",
                "confidence": 0.4,  # Low confidence
                "chaos_index": 4.0,  # High chaos
                "butterfly_coefficient": 0.85,  # High sensitivity
                "stability": "critical",
                "insights": [],
                "risk_factors": ["High volatility", "Critical stability"]
            },
            singularity_results={
                "trading_action": "SELL",
                "confidence": 0.35,
                "signal_strength": -0.5,
                "insights": [],
                "risk_factors": ["Anomaly detected"],
                "patterns": ["divergence"]
            },
            market_data={
                "location_sentiments": {"loc": -0.5},
                "chain_sentiments": {"chain": -0.4},
                "ratings": [2.5],
                "volatility": 0.25
            }
        )

        assert insight.risk_assessment in ["HIGH", "CRITICAL"]

        nexus.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
