#!/usr/bin/env python3
"""
HIGGS NEXUS - Example Usage
===========================

This file demonstrates how to use the Higgs Nexus system
for market phase detection and signal arbitration.

Run with: python -m modules.higgs_nexus.example_usage
"""

import asyncio
import numpy as np
from datetime import datetime

from .core import HiggsNexus, NexusConfig
from .phase_detector import PhaseDetectorConfig
from .field_dynamics import HiggsFieldConfig
from .swarm_coordinator import SwarmConfig
from .signal_arbiter import ArbiterConfig
from .models import MarketPhase


async def basic_example():
    """Basic usage example"""
    print("\n" + "="*60)
    print("HIGGS NEXUS - Basic Example")
    print("="*60 + "\n")

    # Create Nexus with default config
    nexus = HiggsNexus()
    await nexus.start()

    # Simulate Echo Engine results
    echo_results = {
        "signal": "BUY",
        "confidence": 0.72,
        "chaos_index": 1.8,
        "butterfly_coefficient": 0.45,
        "stability": "stable",
        "insights": [
            "System shows low propagation risk",
            "Brand sentiment improving"
        ],
        "risk_factors": ["Minor volatility in NYC locations"],
        "critical_locations": [
            {"name": "Starbucks Times Square", "echo": 2.1}
        ]
    }

    # Simulate Singularity Engine results
    singularity_results = {
        "trading_action": "BUY",
        "confidence": 0.68,
        "signal_strength": 0.35,
        "insights": [
            "Positive weekly temporal pattern detected",
            "Strong semantic resonance with competitor weakness"
        ],
        "risk_factors": ["Seasonal volatility approaching"],
        "patterns": ["weekly_positive", "cross_brand_correlation"]
    }

    # Market data
    market_data = {
        "location_sentiments": {
            "loc_001": 0.65,
            "loc_002": 0.42,
            "loc_003": 0.58,
            "loc_004": 0.71,
            "loc_005": 0.33
        },
        "chain_sentiments": {
            "starbucks": 0.52,
            "dunkin": 0.38,
            "peets": 0.45
        },
        "ratings": [4.2, 4.5, 3.8, 4.1, 4.6, 3.9, 4.3],
        "volatility": 0.12
    }

    # Run analysis
    insight = await nexus.analyze(
        echo_results=echo_results,
        singularity_results=singularity_results,
        market_data=market_data
    )

    # Print results
    print(f"Insight ID: {insight.insight_id}")
    print(f"Timestamp: {insight.timestamp}")
    print(f"\n--- PHASE STATE ---")
    print(f"Current Phase: {insight.phase_state.current_phase.value}")
    print(f"Stability Score: {insight.phase_state.stability_score:.2f}")
    if insight.phase_state.pending_transition:
        pt = insight.phase_state.pending_transition
        print(f"Pending Transition: {pt.to_phase.value} (prob: {pt.probability:.0%})")

    print(f"\n--- ARBITRATED SIGNAL ---")
    print(f"Action: {insight.signal.action}")
    print(f"Confidence: {insight.signal.confidence:.0%}")
    print(f"Signal Strength: {insight.signal.signal_strength:.2f}")
    print(f"Authority: {insight.signal.authority.value}")
    print(f"Echo Weight: {insight.signal.echo_contribution.weight:.2f}")
    print(f"Singularity Weight: {insight.signal.singularity_contribution.weight:.2f}")

    print(f"\n--- RECOMMENDATION ---")
    print(f"Risk Level: {insight.risk_assessment}")
    print(f"Recommendation: {insight.primary_recommendation}")

    print(f"\n--- ACTION ITEMS ---")
    for item in insight.action_items:
        print(f"  • {item}")

    print(f"\n--- NARRATIVE ---")
    print(insight.market_narrative)

    # Get health status
    health = nexus.get_health()
    print(f"\n--- SYSTEM HEALTH ---")
    print(f"Status: {health.status}")
    print(f"CPU: {health.cpu_percent:.1f}%")
    print(f"RAM: {health.ram_gb:.2f} GB")

    nexus.stop()
    print("\n✓ Basic example complete")


async def phase_transition_example():
    """Example showing phase transition detection"""
    print("\n" + "="*60)
    print("HIGGS NEXUS - Phase Transition Example")
    print("="*60 + "\n")

    # Configure for more sensitive phase detection
    field_config = HiggsFieldConfig(
        critical_volatility=0.15,
        symmetric_threshold=0.25
    )
    phase_config = PhaseDetectorConfig(
        transition_threshold=0.25,
        min_stability_window=3
    )

    nexus = HiggsNexus(config=NexusConfig(
        field_config=field_config,
        phase_config=phase_config,
        enable_swarm=False  # Disable swarm for this example
    ))
    await nexus.start()

    # Register phase change callback
    phase_changes = []
    async def on_phase_change(old_phase, new_phase):
        phase_changes.append((old_phase, new_phase, datetime.now()))
        print(f"  📊 Phase changed: {old_phase.value} → {new_phase.value}")

    nexus.on_phase_change(on_phase_change)

    # Simulate market evolution over time
    print("Simulating market evolution...")

    # Start stable
    volatilities = [0.08, 0.09, 0.10, 0.12, 0.15, 0.18, 0.22, 0.20, 0.16, 0.12]
    sentiments = [0.3, 0.32, 0.35, 0.28, 0.15, -0.05, -0.15, -0.10, 0.05, 0.15]

    for i, (vol, sent) in enumerate(zip(volatilities, sentiments)):
        echo_results = {
            "signal": "BUY" if sent > 0.1 else ("SELL" if sent < -0.1 else "HOLD"),
            "confidence": 0.6,
            "chaos_index": 1.0 + vol * 10,
            "butterfly_coefficient": min(0.9, vol * 3),
            "stability": "critical" if vol > 0.18 else ("unstable" if vol > 0.14 else "stable"),
            "insights": [],
            "risk_factors": []
        }

        singularity_results = {
            "trading_action": "BUY" if sent > 0.1 else ("SELL" if sent < -0.1 else "HOLD"),
            "confidence": 0.55,
            "signal_strength": sent,
            "insights": [],
            "risk_factors": [],
            "patterns": []
        }

        market_data = {
            "location_sentiments": {f"loc_{j}": sent + np.random.normal(0, 0.1) for j in range(10)},
            "chain_sentiments": {"chain_a": sent, "chain_b": sent * 0.8},
            "ratings": [3.5 + sent + np.random.normal(0, 0.3) for _ in range(5)],
            "volatility": vol
        }

        insight = await nexus.analyze(echo_results, singularity_results, market_data)
        print(f"  Tick {i+1}: vol={vol:.2f}, sent={sent:+.2f} → Phase: {insight.phase_state.current_phase.value}")

        await asyncio.sleep(0.1)  # Small delay

    print(f"\nPhase changes detected: {len(phase_changes)}")
    for old, new, ts in phase_changes:
        print(f"  {ts.strftime('%H:%M:%S')}: {old.value} → {new.value}")

    nexus.stop()
    print("\n✓ Phase transition example complete")


async def swarm_example():
    """Example showing swarm collective intelligence"""
    print("\n" + "="*60)
    print("HIGGS NEXUS - Swarm Intelligence Example")
    print("="*60 + "\n")

    # Configure swarm
    swarm_config = SwarmConfig(
        min_active_nodes=5,
        max_active_nodes=50
    )

    nexus = HiggsNexus(config=NexusConfig(
        swarm_config=swarm_config,
        enable_swarm=True,
        initial_swarm_nodes=20
    ))
    await nexus.start()

    # Show initial swarm state
    if nexus.swarm:
        metrics = nexus.swarm.get_metrics()
        print(f"Initial Swarm State:")
        print(f"  Active Nodes: {metrics.active_nodes}")
        print(f"  Total Nodes: {metrics.total_nodes}")

    # Run analysis with swarm
    echo_results = {
        "signal": "BUY",
        "confidence": 0.65,
        "chaos_index": 2.0,
        "butterfly_coefficient": 0.5,
        "stability": "stable",
        "insights": [],
        "risk_factors": []
    }

    singularity_results = {
        "trading_action": "HOLD",  # Disagreement with Echo
        "confidence": 0.60,
        "signal_strength": 0.1,
        "insights": [],
        "risk_factors": [],
        "patterns": []
    }

    # Large market data for swarm processing
    market_data = {
        "location_sentiments": {f"loc_{i}": np.random.uniform(-0.5, 0.8) for i in range(50)},
        "chain_sentiments": {f"chain_{i}": np.random.uniform(0, 0.6) for i in range(5)},
        "ratings": [np.random.uniform(3.0, 5.0) for _ in range(100)],
        "volatility": 0.15
    }

    insight = await nexus.analyze(echo_results, singularity_results, market_data)

    print(f"\nAnalysis with Swarm:")
    print(f"  Signal: {insight.signal.action}")
    print(f"  Swarm Consensus: {insight.signal.swarm_consensus:.0%}")
    if insight.signal.swarm_dissent_reasons:
        print(f"  Dissent: {', '.join(insight.signal.swarm_dissent_reasons)}")

    # Show final swarm state
    if nexus.swarm:
        metrics = nexus.swarm.get_metrics()
        print(f"\nFinal Swarm State:")
        print(f"  Active Nodes: {metrics.active_nodes}")
        print(f"  Collective Intelligence: {metrics.collective_intelligence_score:.2f}")
        print(f"  Diversity Index: {metrics.diversity_index:.2f}")
        print(f"  Health Score: {metrics.health_score:.2f}")

    nexus.stop()
    print("\n✓ Swarm example complete")


async def custom_config_example():
    """Example with custom configuration"""
    print("\n" + "="*60)
    print("HIGGS NEXUS - Custom Configuration Example")
    print("="*60 + "\n")

    # Custom field dynamics
    field_config = HiggsFieldConfig(
        mu_squared=1.5,              # Stronger symmetry breaking
        lambda_coupling=0.3,         # Adjust potential shape
        critical_volatility=0.12,    # Lower critical point
        field_dimensions=16          # Higher dimensional order parameter
    )

    # Custom arbiter weights
    arbiter_config = ArbiterConfig(
        base_echo_weight=0.6,        # Favor Echo
        base_singularity_weight=0.4,
        swarm_weight=0.15,           # Less swarm influence
        strong_signal_threshold=0.5  # Require stronger signals
    )

    # Custom swarm
    swarm_config = SwarmConfig(
        max_active_nodes=30,
        max_cpu_percent=50.0,
        consensus_threshold=0.8      # Require more agreement
    )

    config = NexusConfig(
        field_config=field_config,
        arbiter_config=arbiter_config,
        swarm_config=swarm_config,
        enable_swarm=True,
        initial_swarm_nodes=15,
        max_cpu_percent=50.0,
        max_ram_gb=2.0
    )

    nexus = HiggsNexus(config=config)
    await nexus.start()

    print("Custom configuration applied:")
    print(f"  Field VEV: {nexus.phase_detector.field.vev:.3f}")
    print(f"  Echo base weight: {arbiter_config.base_echo_weight}")
    print(f"  Max active nodes: {swarm_config.max_active_nodes}")

    # Quick analysis
    insight = await nexus.analyze(
        echo_results={"signal": "BUY", "confidence": 0.7, "chaos_index": 1.5,
                      "butterfly_coefficient": 0.4, "stability": "stable",
                      "insights": [], "risk_factors": []},
        singularity_results={"trading_action": "BUY", "confidence": 0.65,
                            "signal_strength": 0.3, "insights": [],
                            "risk_factors": [], "patterns": []},
        market_data={"location_sentiments": {"a": 0.5}, "chain_sentiments": {"x": 0.4},
                    "ratings": [4.0], "volatility": 0.1}
    )

    print(f"\nResult: {insight.signal.action} ({insight.signal.confidence:.0%})")

    nexus.stop()
    print("\n✓ Custom config example complete")


async def main():
    """Run all examples"""
    print("\n" + "#"*60)
    print("#  HIGGS NEXUS - Example Suite")
    print("#"*60)

    await basic_example()
    await phase_transition_example()
    await swarm_example()
    await custom_config_example()

    print("\n" + "#"*60)
    print("#  All examples completed successfully!")
    print("#"*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
