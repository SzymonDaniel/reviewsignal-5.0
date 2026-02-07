# HIGGS NEXUS - Integration Layer
# Connects Nexus with Echo Engine and Singularity Engine

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime
import logging

from .core import HiggsNexus, NexusConfig
from .models import NexusInsight, MarketPhase

# Type hints for engines (avoid circular imports)
if TYPE_CHECKING:
    from ..echo_engine import EchoEngine, TradingSignal
    from ..singularity_engine import SingularityEngine, SingularityInsight

logger = logging.getLogger("HiggsNexus.Integration")


@dataclass
class IntegrationConfig:
    """Configuration for Nexus integration"""
    # Auto-analysis settings
    auto_analyze_interval_sec: float = 60.0
    min_reviews_for_analysis: int = 10

    # Data preparation
    max_locations_per_batch: int = 100
    sentiment_smoothing_window: int = 5

    # Callbacks
    notify_on_phase_change: bool = True
    notify_on_critical_signal: bool = True


class NexusIntegration:
    """
    Integration layer that orchestrates Nexus with Echo and Singularity engines.

    This class:
    - Prepares data from both engines for Nexus analysis
    - Handles the full pipeline: data → engines → nexus → insight
    - Manages callbacks and notifications
    - Provides unified API for the complete system
    """

    def __init__(
        self,
        echo_engine: "EchoEngine",
        singularity_engine: "SingularityEngine",
        nexus: Optional[HiggsNexus] = None,
        config: Optional[IntegrationConfig] = None
    ):
        self.echo = echo_engine
        self.singularity = singularity_engine
        self.nexus = nexus or HiggsNexus()
        self.config = config or IntegrationConfig()

        self._is_running = False
        self._last_analysis: Optional[datetime] = None
        self._analysis_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_insight_callbacks: List[callable] = []
        self._on_phase_change_callbacks: List[callable] = []
        self._on_critical_callbacks: List[callable] = []

        logger.info("NexusIntegration initialized")

    async def start(self):
        """Start the integration layer"""
        self._is_running = True

        # Start Nexus
        await self.nexus.start()

        # Register Nexus callbacks
        self.nexus.on_phase_change(self._handle_phase_change)
        self.nexus.on_symmetry_breaking(self._handle_symmetry_breaking)

        logger.info("NexusIntegration started")

    def stop(self):
        """Stop the integration layer"""
        self._is_running = False

        if self._analysis_task:
            self._analysis_task.cancel()

        self.nexus.stop()
        logger.info("NexusIntegration stopped")

    async def analyze_chain(
        self,
        chain_name: str,
        reviews: List[Dict[str, Any]],
        include_monte_carlo: bool = True
    ) -> NexusInsight:
        """
        Analyze a specific chain through the full pipeline.

        Args:
            chain_name: Name of the chain to analyze
            reviews: List of review data dicts
            include_monte_carlo: Whether to run Monte Carlo simulation

        Returns:
            Complete NexusInsight
        """
        # Prepare market data
        market_data = self._prepare_market_data(reviews)

        # Run Echo Engine analysis
        echo_results = await self._run_echo_analysis(
            chain_name,
            include_monte_carlo
        )

        # Run Singularity Engine analysis
        singularity_results = await self._run_singularity_analysis(
            reviews,
            chain_name
        )

        # Run through Nexus
        insight = await self.nexus.analyze(
            echo_results=echo_results,
            singularity_results=singularity_results,
            market_data=market_data
        )

        self._last_analysis = datetime.now()

        # Notify callbacks
        await self._notify_insight(insight)

        return insight

    async def analyze_market(
        self,
        reviews_by_chain: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, NexusInsight]:
        """
        Analyze entire market (multiple chains).

        Args:
            reviews_by_chain: Dict mapping chain names to review lists

        Returns:
            Dict mapping chain names to NexusInsights
        """
        insights = {}

        for chain_name, reviews in reviews_by_chain.items():
            if len(reviews) >= self.config.min_reviews_for_analysis:
                try:
                    insight = await self.analyze_chain(chain_name, reviews)
                    insights[chain_name] = insight
                except Exception as e:
                    logger.error(f"Error analyzing {chain_name}: {e}")

        return insights

    def _prepare_market_data(
        self,
        reviews: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Prepare market data from reviews"""
        location_sentiments = {}
        chain_sentiments = {}
        ratings = []

        for review in reviews:
            # Location sentiment
            loc_id = review.get("location_id", "unknown")
            sentiment = review.get("sentiment_score", 0.0)
            location_sentiments[loc_id] = sentiment

            # Chain sentiment
            chain = review.get("chain_name", "unknown")
            if chain not in chain_sentiments:
                chain_sentiments[chain] = []
            chain_sentiments[chain].append(sentiment)

            # Rating
            rating = review.get("rating")
            if rating is not None:
                ratings.append(rating)

        # Average chain sentiments
        chain_sentiments = {
            chain: sum(sents) / len(sents)
            for chain, sents in chain_sentiments.items()
            if sents
        }

        # Calculate volatility from rating variance
        volatility = 0.1
        if len(ratings) > 1:
            import numpy as np
            volatility = min(0.5, np.std(ratings) / 5.0)

        return {
            "location_sentiments": location_sentiments,
            "chain_sentiments": chain_sentiments,
            "ratings": ratings,
            "volatility": volatility
        }

    async def _run_echo_analysis(
        self,
        chain_name: str,
        include_monte_carlo: bool
    ) -> Dict[str, Any]:
        """Run Echo Engine analysis"""
        try:
            # Generate trading signal
            signal = self.echo.generate_trading_signal(
                brand=chain_name,
                n_trials=500 if include_monte_carlo else 100
            )

            # Get system health
            health = self.echo.get_system_health()

            return {
                "signal": signal.signal.value if hasattr(signal.signal, 'value') else str(signal.signal),
                "confidence": signal.confidence,
                "chaos_index": signal.chaos_index,
                "butterfly_coefficient": getattr(signal, 'butterfly_coefficient', 0.5),
                "stability": health.get("stability", "stable"),
                "insights": [signal.recommendation] if signal.recommendation else [],
                "risk_factors": [f"Risk level: {signal.risk_level}"] if signal.risk_level else [],
                "critical_locations": signal.critical_locations[:5] if signal.critical_locations else [],
                "echo_mean": signal.echo_mean,
                "echo_std": signal.echo_std
            }

        except Exception as e:
            logger.error(f"Echo analysis error: {e}")
            return {
                "signal": "HOLD",
                "confidence": 0.3,
                "chaos_index": 1.0,
                "butterfly_coefficient": 0.5,
                "stability": "unknown",
                "insights": [],
                "risk_factors": [f"Echo error: {str(e)}"]
            }

    async def _run_singularity_analysis(
        self,
        reviews: List[Dict[str, Any]],
        chain_name: str
    ) -> Dict[str, Any]:
        """Run Singularity Engine analysis"""
        try:
            # Convert to ReviewData format if needed
            review_data = self._convert_to_review_data(reviews)

            # Run analysis
            result = await self.singularity.analyze(review_data)

            # Extract primary insight
            if result.insights:
                primary = result.insights[0]
                return {
                    "trading_action": primary.trading_action.value if hasattr(primary.trading_action, 'value') else str(primary.trading_action),
                    "confidence": primary.confidence_score,
                    "signal_strength": getattr(primary, 'signal_strength', 0.0),
                    "insights": primary.key_drivers[:3] if primary.key_drivers else [],
                    "risk_factors": primary.risk_factors[:3] if primary.risk_factors else [],
                    "patterns": [m.module_name for m in primary.contributing_modules] if primary.contributing_modules else [],
                    "warning_signals": primary.warning_signals[:3] if primary.warning_signals else [],
                    "synthesis": primary.synthesis
                }
            else:
                return self._default_singularity_result()

        except Exception as e:
            logger.error(f"Singularity analysis error: {e}")
            return self._default_singularity_result(error=str(e))

    def _convert_to_review_data(self, reviews: List[Dict[str, Any]]) -> List[Any]:
        """Convert review dicts to ReviewData format expected by Singularity"""
        # This would use the actual ReviewData class from singularity_engine
        # For now, return as-is if the engine can handle dicts
        return reviews

    def _default_singularity_result(self, error: Optional[str] = None) -> Dict[str, Any]:
        """Return default Singularity result"""
        result = {
            "trading_action": "HOLD",
            "confidence": 0.3,
            "signal_strength": 0.0,
            "insights": [],
            "risk_factors": [],
            "patterns": [],
            "warning_signals": []
        }
        if error:
            result["risk_factors"].append(f"Singularity error: {error}")
        return result

    async def _handle_phase_change(
        self,
        old_phase: MarketPhase,
        new_phase: MarketPhase
    ):
        """Handle phase change event"""
        logger.info(f"Phase change: {old_phase.value} → {new_phase.value}")

        if self.config.notify_on_phase_change:
            for callback in self._on_phase_change_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(old_phase, new_phase)
                    else:
                        callback(old_phase, new_phase)
                except Exception as e:
                    logger.error(f"Phase change callback error: {e}")

    async def _handle_symmetry_breaking(self, breaking):
        """Handle symmetry breaking event"""
        logger.warning(
            f"Symmetry breaking: {breaking.direction}, "
            f"cascade risk: {breaking.cascade_risk:.0%}"
        )

        if self.config.notify_on_critical_signal:
            for callback in self._on_critical_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback("symmetry_breaking", breaking)
                    else:
                        callback("symmetry_breaking", breaking)
                except Exception as e:
                    logger.error(f"Critical callback error: {e}")

    async def _notify_insight(self, insight: NexusInsight):
        """Notify insight callbacks"""
        for callback in self._on_insight_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(insight)
                else:
                    callback(insight)
            except Exception as e:
                logger.error(f"Insight callback error: {e}")

        # Check for critical signals
        if self.config.notify_on_critical_signal:
            if insight.risk_assessment in ["HIGH", "CRITICAL"]:
                for callback in self._on_critical_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback("high_risk", insight)
                        else:
                            callback("high_risk", insight)
                    except Exception as e:
                        logger.error(f"Critical callback error: {e}")

    def on_insight(self, callback: callable):
        """Register callback for new insights"""
        self._on_insight_callbacks.append(callback)

    def on_phase_change(self, callback: callable):
        """Register callback for phase changes"""
        self._on_phase_change_callbacks.append(callback)

    def on_critical(self, callback: callable):
        """Register callback for critical events"""
        self._on_critical_callbacks.append(callback)

    def get_status(self) -> Dict[str, Any]:
        """Get integration status"""
        return {
            "is_running": self._is_running,
            "last_analysis": self._last_analysis.isoformat() if self._last_analysis else None,
            "nexus_health": self.nexus.get_health().__dict__,
            "current_phase": self.nexus.get_current_phase().value if self.nexus.get_current_phase() else None
        }


# Factory function for creating complete integrated system
async def create_integrated_system(
    db_connection,
    nexus_config: Optional[NexusConfig] = None,
    integration_config: Optional[IntegrationConfig] = None
) -> NexusIntegration:
    """
    Create fully integrated system with database connection.

    Args:
        db_connection: Database connection for loading data
        nexus_config: Optional Nexus configuration
        integration_config: Optional integration configuration

    Returns:
        Initialized and started NexusIntegration
    """
    # Import engines here to avoid circular imports
    from ..echo_engine import create_echo_engine_from_db
    from ..singularity_engine import create_singularity_engine_from_db

    # Create engines
    echo_engine = await create_echo_engine_from_db(db_connection)
    singularity_engine = await create_singularity_engine_from_db(db_connection)

    # Create Nexus
    nexus = HiggsNexus(config=nexus_config)

    # Create integration
    integration = NexusIntegration(
        echo_engine=echo_engine,
        singularity_engine=singularity_engine,
        nexus=nexus,
        config=integration_config
    )

    # Start
    await integration.start()

    return integration
