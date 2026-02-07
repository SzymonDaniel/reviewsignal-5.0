# ═══════════════════════════════════════════════════════════════════════════════
# SINGULARITY ENGINE - Signal Synthesizer
# Combine all module outputs into actionable trading signals
# ═══════════════════════════════════════════════════════════════════════════════

from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
import numpy as np
import structlog

from .models import (
    SingularityConfig,
    ReviewData,
    SingularityInsight,
    ModuleContribution,
    InsightConfidence,
    TradingAction,
    TemporalPattern,
    SemanticResonance,
    TopologicalInsight,
)
from .utils import (
    generate_id,
    normalize_sentiment,
    safe_mean,
    combine_confidences,
    calculate_confidence_level,
)

logger = structlog.get_logger(__name__)


class SignalSynthesizer:
    """
    Signal Synthesizer - Convergence of Multiple Analytical Perspectives

    Takes outputs from all Singularity modules:
    - Temporal Manifold: Time-based patterns
    - Semantic Resonance: Text-based correlations
    - Causal Archaeology: Root cause chains
    - Topological Analysis: Structural patterns
    - Echo Engine: System dynamics

    And synthesizes them into:
    - Unified confidence scores
    - Trading recommendations
    - Action items
    - Risk assessments
    """

    def __init__(self, config: Optional[SingularityConfig] = None):
        self.config = config or SingularityConfig()

        logger.info("signal_synthesizer_initialized")

    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN SYNTHESIS
    # ═══════════════════════════════════════════════════════════════════════════

    def synthesize(
        self,
        temporal_results: Dict[str, Any],
        semantic_results: Dict[str, Any],
        causal_results: Dict[str, Any],
        topology_results: Dict[str, Any],
        echo_results: Dict[str, Any],
        reviews: List[ReviewData]
    ) -> List[SingularityInsight]:
        """
        Synthesize results from all modules into insights

        Args:
            temporal_results: Results from TemporalManifold
            semantic_results: Results from SemanticResonanceField
            causal_results: Results from CausalArchaeologist
            topology_results: Results from TopologicalAnalyzer
            echo_results: Results from EchoSingularityIntegration
            reviews: Original reviews for context

        Returns:
            List of synthesized SingularityInsight objects
        """
        insights = []

        # 1. Extract signals from each module
        temporal_signal = self._extract_temporal_signal(temporal_results)
        semantic_signal = self._extract_semantic_signal(semantic_results)
        causal_signal = self._extract_causal_signal(causal_results)
        topology_signal = self._extract_topology_signal(topology_results)
        echo_signal = self._extract_echo_signal(echo_results)

        # 2. Combine signals
        all_signals = [
            s for s in [temporal_signal, semantic_signal, causal_signal, topology_signal, echo_signal]
            if s is not None
        ]

        if not all_signals:
            return [self._create_no_signal_insight()]

        # 3. Create primary insight (convergent signal)
        primary_insight = self._create_convergent_insight(
            all_signals, reviews, temporal_results, semantic_results, topology_results, echo_results
        )
        insights.append(primary_insight)

        # 4. Create secondary insights for notable findings
        secondary = self._create_secondary_insights(
            temporal_results, semantic_results, causal_results, topology_results
        )
        insights.extend(secondary)

        logger.info(
            "synthesis_complete",
            insight_count=len(insights),
            primary_confidence=primary_insight.confidence_score
        )

        return insights

    # ═══════════════════════════════════════════════════════════════════════════
    # SIGNAL EXTRACTION
    # ═══════════════════════════════════════════════════════════════════════════

    def _extract_temporal_signal(
        self,
        results: Dict[str, Any]
    ) -> Optional[ModuleContribution]:
        """Extract trading signal from temporal analysis"""
        if not results or 'error' in results:
            return None

        fold_results = results.get('fold_results', [])
        strongest_patterns = results.get('strongest_patterns', [])
        anomaly_count = results.get('anomaly_count', 0)

        if not fold_results:
            return None

        # Analyze patterns for signal
        bullish_signals = 0
        bearish_signals = 0
        evidence = []

        for pattern in strongest_patterns:
            if pattern:
                if pattern.trend_direction == 'up':
                    bullish_signals += 1
                    evidence.append(f"Upward trend in {pattern.fold_key}")
                elif pattern.trend_direction == 'down':
                    bearish_signals += 1
                    evidence.append(f"Downward trend in {pattern.fold_key}")

                if pattern.is_anomaly:
                    if pattern.deviation_from_baseline > 0:
                        bullish_signals += 0.5
                        evidence.append(f"Positive anomaly: {pattern.fold_key}")
                    else:
                        bearish_signals += 0.5
                        evidence.append(f"Negative anomaly: {pattern.fold_key}")

        # Calculate signal strength
        total_signals = bullish_signals + bearish_signals
        if total_signals > 0:
            signal_strength = (bullish_signals - bearish_signals) / total_signals
        else:
            signal_strength = 0

        # Confidence based on consistency
        confidence = min(1.0, len(strongest_patterns) / 5) * 0.8

        # Key finding
        if bullish_signals > bearish_signals:
            key_finding = f"Temporal analysis suggests improving sentiment ({bullish_signals:.0f} bullish signals)"
        elif bearish_signals > bullish_signals:
            key_finding = f"Temporal analysis suggests declining sentiment ({bearish_signals:.0f} bearish signals)"
        else:
            key_finding = "Temporal patterns show mixed signals"

        return ModuleContribution(
            module_name="temporal",
            signal_strength=signal_strength,
            confidence=confidence,
            key_finding=key_finding,
            supporting_evidence=evidence[:5]
        )

    def _extract_semantic_signal(
        self,
        results: Dict[str, Any]
    ) -> Optional[ModuleContribution]:
        """Extract trading signal from semantic analysis"""
        if not results or 'error' in results:
            return None

        resonances = results.get('resonances', [])
        prophetic = results.get('prophetic_reviews', [])
        themes = results.get('emergent_themes', [])

        evidence = []

        # Analyze resonances
        cross_brand_similar = len([r for r in resonances if r.resonance_type.value == 'cross_brand'])

        # Analyze prophetic reviews
        negative_prophetic = len([p for p in prophetic if 'negative' in p.predicted_event.lower() or 'decline' in p.predicted_event.lower()])
        positive_prophetic = len([p for p in prophetic if 'positive' in p.predicted_event.lower() or 'improve' in p.predicted_event.lower()])

        # Analyze emergent themes
        negative_themes = len([t for t in themes if t.avg_sentiment < -0.2])
        positive_themes = len([t for t in themes if t.avg_sentiment > 0.2])

        # Calculate signal
        bullish = positive_prophetic + positive_themes
        bearish = negative_prophetic + negative_themes

        if bullish + bearish > 0:
            signal_strength = (bullish - bearish) / (bullish + bearish)
        else:
            signal_strength = 0

        # Build evidence
        if cross_brand_similar > 0:
            evidence.append(f"{cross_brand_similar} cross-brand sentiment correlations")

        for theme in themes[:2]:
            if theme.growth_rate > 0.5:
                direction = "positive" if theme.avg_sentiment > 0 else "negative"
                evidence.append(f"Emergent {direction} theme: {', '.join(theme.keywords[:3])}")

        for p in prophetic[:2]:
            evidence.append(f"Prophetic signal: {p.predicted_event[:50]}")

        # Confidence
        confidence = min(1.0, (len(resonances) + len(themes) + len(prophetic)) / 20) * 0.7

        # Key finding
        if signal_strength > 0.2:
            key_finding = "Semantic analysis detects positive sentiment emergence"
        elif signal_strength < -0.2:
            key_finding = "Semantic analysis detects negative sentiment patterns"
        else:
            key_finding = f"Semantic analysis found {len(resonances)} resonances, {len(themes)} themes"

        return ModuleContribution(
            module_name="semantic",
            signal_strength=signal_strength,
            confidence=confidence,
            key_finding=key_finding,
            supporting_evidence=evidence[:5]
        )

    def _extract_causal_signal(
        self,
        results: Dict[str, Any]
    ) -> Optional[ModuleContribution]:
        """Extract trading signal from causal analysis"""
        if not results or 'error' in results:
            return None

        graphs = results.get('causal_graphs', [])
        if not graphs:
            return None

        evidence = []

        # Analyze causal graphs
        total_evidence = 0
        structural_issues = 0
        systemic_issues = 0

        for graph in graphs:
            total_evidence += graph.total_evidence_count

            for node in graph.nodes.values():
                if node.level.value >= 3:  # Structural or deeper
                    structural_issues += 1
                if node.level.value >= 4:  # Systemic
                    systemic_issues += 1

            # Add root causes as evidence
            for root_id in graph.root_causes[:2]:
                if root_id in graph.nodes:
                    node = graph.nodes[root_id]
                    evidence.append(f"Root cause: {node.description}")

        # Signal strength: deeper issues = more bearish
        if structural_issues + systemic_issues > 0:
            # More deep issues = bearish
            depth_ratio = systemic_issues / (structural_issues + systemic_issues + 1)
            signal_strength = -0.3 - (depth_ratio * 0.4)  # -0.3 to -0.7
        else:
            signal_strength = 0

        # Confidence based on evidence
        confidence = min(1.0, total_evidence / 50) * 0.6

        # Key finding
        if systemic_issues > 0:
            key_finding = f"Causal analysis reveals {systemic_issues} systemic issues"
        elif structural_issues > 0:
            key_finding = f"Causal analysis found {structural_issues} structural problems"
        else:
            key_finding = "Causal chains analyzed, no deep issues found"

        return ModuleContribution(
            module_name="causal",
            signal_strength=signal_strength,
            confidence=confidence,
            key_finding=key_finding,
            supporting_evidence=evidence[:5]
        )

    def _extract_topology_signal(
        self,
        results: Dict[str, Any]
    ) -> Optional[ModuleContribution]:
        """Extract trading signal from topological analysis"""
        if not results or 'error' in results:
            return None

        insights = results.get('insights', [])
        if not insights:
            return None

        evidence = []

        # Analyze topological features
        holes = [i for i in insights if i.feature_type.value == 'hole']
        voids = [i for i in insights if i.feature_type.value == 'void']
        clusters = [i for i in insights if i.feature_type.value == 'cluster']

        # Holes often represent opportunities (bullish) or gaps (neutral to bullish)
        opportunity_score = sum(h.opportunity_score for h in holes)
        risk_score = sum(h.risk_score for h in holes)

        # Signal based on opportunity vs risk
        if opportunity_score + risk_score > 0:
            signal_strength = (opportunity_score - risk_score) / (opportunity_score + risk_score)
        else:
            signal_strength = 0

        # Build evidence
        for hole in holes[:2]:
            evidence.append(f"Gap: {hole.interpretation[:50]}")

        for cluster in clusters[:2]:
            evidence.append(f"Cluster: {cluster.interpretation[:50]}")

        # Confidence
        avg_significance = safe_mean([i.significance for i in insights])
        confidence = avg_significance * 0.7

        # Key finding
        if holes:
            key_finding = f"Topological analysis found {len(holes)} market gaps"
        elif clusters:
            key_finding = f"Topological analysis identified {len(clusters)} distinct segments"
        else:
            key_finding = "Topological structure appears uniform"

        return ModuleContribution(
            module_name="topology",
            signal_strength=signal_strength,
            confidence=confidence,
            key_finding=key_finding,
            supporting_evidence=evidence[:5]
        )

    def _extract_echo_signal(
        self,
        results: Dict[str, Any]
    ) -> Optional[ModuleContribution]:
        """Extract trading signal from Echo Engine"""
        if not results or 'error' in results:
            return None

        butterfly = results.get('butterfly_coefficient', 0.5)
        stability = results.get('system_stability', 'unknown')
        propagation = results.get('propagation_prediction', {})
        echo_insights = results.get('echo_insights', [])

        evidence = []

        # Signal from propagation prediction
        direction = propagation.get('overall_direction', 'neutral')
        if direction == 'bullish':
            signal_strength = 0.5
        elif direction == 'bearish':
            signal_strength = -0.5
        else:
            signal_strength = 0

        # Adjust by stability
        if stability == 'critical':
            signal_strength -= 0.2
        elif stability == 'stable':
            signal_strength += 0.1

        # Build evidence
        evidence.append(f"Butterfly coefficient: {butterfly:.2f}")
        evidence.append(f"System stability: {stability}")

        for insight in echo_insights[:2]:
            evidence.append(insight.get('message', '')[:50])

        # Confidence
        confidence = 0.5 if stability == 'unknown' else 0.7

        # Key finding
        key_finding = f"Echo Engine: {stability} system, {direction} outlook (β={butterfly:.2f})"

        return ModuleContribution(
            module_name="echo",
            signal_strength=signal_strength,
            confidence=confidence,
            key_finding=key_finding,
            supporting_evidence=evidence[:5]
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # INSIGHT CREATION
    # ═══════════════════════════════════════════════════════════════════════════

    def _create_convergent_insight(
        self,
        signals: List[ModuleContribution],
        reviews: List[ReviewData],
        temporal_results: Dict,
        semantic_results: Dict,
        topology_results: Dict,
        echo_results: Dict
    ) -> SingularityInsight:
        """Create primary insight from converging signals"""
        # Calculate overall signal strength (weighted average)
        total_weight = sum(s.confidence for s in signals)
        if total_weight > 0:
            weighted_signal = sum(s.signal_strength * s.confidence for s in signals) / total_weight
        else:
            weighted_signal = 0

        # Calculate overall confidence
        confidences = [s.confidence for s in signals]
        overall_confidence = combine_confidences(confidences, method="harmonic")

        # Determine confidence level
        agreeing_modules = sum(1 for s in signals if (s.signal_strength > 0) == (weighted_signal > 0))
        if agreeing_modules >= 4:
            confidence_level = InsightConfidence.VERY_HIGH
        elif agreeing_modules >= 3:
            confidence_level = InsightConfidence.HIGH
        elif agreeing_modules >= 2:
            confidence_level = InsightConfidence.MEDIUM
        else:
            confidence_level = InsightConfidence.LOW

        # Determine trading action
        trading_action, trading_confidence = self._determine_trading_action(
            weighted_signal, overall_confidence, echo_results
        )

        # Generate synthesis narrative
        synthesis = self._generate_synthesis_narrative(signals, weighted_signal, confidence_level)

        # Collect key drivers and warnings
        key_drivers = [s.key_finding for s in signals if s.signal_strength > 0]
        warning_signals = [s.key_finding for s in signals if s.signal_strength < 0]

        # Generate action items
        action_items = self._generate_action_items(signals, trading_action)

        # Risk factors
        risk_factors = self._identify_risk_factors(signals, echo_results)

        # Get component data
        temporal_patterns = temporal_results.get('strongest_patterns', []) if temporal_results else []
        semantic_resonances = semantic_results.get('resonances', [])[:5] if semantic_results else []
        topological_insights = topology_results.get('insights', [])[:5] if topology_results else []

        return SingularityInsight(
            insight_id=generate_id("insight"),
            confidence=confidence_level,
            confidence_score=overall_confidence,
            contributing_modules=signals,
            temporal_patterns=[p for p in temporal_patterns if p],
            semantic_resonances=semantic_resonances,
            causal_summary=self._get_causal_summary(signals),
            topological_insights=topological_insights,
            echo_butterfly_coefficient=echo_results.get('butterfly_coefficient') if echo_results else None,
            echo_system_stability=echo_results.get('system_stability') if echo_results else None,
            synthesis=synthesis,
            key_drivers=key_drivers[:5],
            warning_signals=warning_signals[:5],
            trading_action=trading_action,
            trading_confidence=trading_confidence,
            action_items=action_items[:5],
            risk_factors=risk_factors[:5]
        )

    def _determine_trading_action(
        self,
        signal_strength: float,
        confidence: float,
        echo_results: Dict
    ) -> Tuple[TradingAction, float]:
        """Determine trading action from signal strength"""
        # Get stability from Echo if available
        stability = echo_results.get('system_stability', 'unknown') if echo_results else 'unknown'

        # Base action on signal strength
        if signal_strength > 0.4 and confidence > 0.6:
            action = TradingAction.STRONG_BUY
            action_confidence = confidence * 0.9
        elif signal_strength > 0.2:
            action = TradingAction.BUY
            action_confidence = confidence * 0.8
        elif signal_strength < -0.4 and confidence > 0.6:
            action = TradingAction.STRONG_SELL
            action_confidence = confidence * 0.9
        elif signal_strength < -0.2:
            action = TradingAction.SELL
            action_confidence = confidence * 0.8
        else:
            action = TradingAction.HOLD
            action_confidence = confidence * 0.7

        # Adjust for stability
        if stability == 'critical':
            # In critical state, be more defensive
            if action in [TradingAction.BUY, TradingAction.STRONG_BUY]:
                action = TradingAction.HOLD
                action_confidence *= 0.8
            elif action == TradingAction.SELL:
                action = TradingAction.STRONG_SELL
        elif stability == 'stable':
            action_confidence *= 1.1

        return action, min(1.0, action_confidence)

    def _generate_synthesis_narrative(
        self,
        signals: List[ModuleContribution],
        overall_signal: float,
        confidence: InsightConfidence
    ) -> str:
        """Generate human-readable synthesis"""
        parts = []

        # Overall direction
        if overall_signal > 0.3:
            parts.append("Multiple analytical perspectives converge on a bullish outlook.")
        elif overall_signal < -0.3:
            parts.append("Multiple analytical perspectives converge on a bearish outlook.")
        else:
            parts.append("Analytical perspectives show mixed signals with no clear directional bias.")

        # Module agreement
        agreeing = [s.module_name for s in signals if (s.signal_strength > 0) == (overall_signal > 0)]
        if len(agreeing) >= 3:
            parts.append(f"Strong agreement across {', '.join(agreeing)} modules.")

        # Key findings
        top_findings = sorted(signals, key=lambda s: abs(s.signal_strength), reverse=True)[:2]
        for finding in top_findings:
            parts.append(finding.key_finding)

        # Confidence note
        if confidence == InsightConfidence.VERY_HIGH:
            parts.append("Confidence is very high due to multi-module convergence.")
        elif confidence == InsightConfidence.LOW:
            parts.append("Confidence is low due to conflicting signals.")

        return " ".join(parts)

    def _generate_action_items(
        self,
        signals: List[ModuleContribution],
        action: TradingAction
    ) -> List[str]:
        """Generate actionable items based on analysis"""
        items = []

        # Trading action
        if action == TradingAction.STRONG_BUY:
            items.append("Consider increasing position size")
        elif action == TradingAction.BUY:
            items.append("Consider initiating or adding to position")
        elif action == TradingAction.STRONG_SELL:
            items.append("Consider reducing exposure significantly")
        elif action == TradingAction.SELL:
            items.append("Consider reducing position")
        else:
            items.append("Maintain current position, monitor for changes")

        # Module-specific actions
        for signal in signals:
            if signal.module_name == "temporal" and signal.signal_strength < 0:
                items.append("Monitor for trend reversal signals")
            elif signal.module_name == "causal" and signal.signal_strength < -0.3:
                items.append("Investigate identified root causes")
            elif signal.module_name == "topology" and signal.signal_strength > 0.3:
                items.append("Evaluate expansion into identified gaps")
            elif signal.module_name == "echo" and signal.confidence < 0.5:
                items.append("Increase monitoring frequency due to system instability")

        return items

    def _identify_risk_factors(
        self,
        signals: List[ModuleContribution],
        echo_results: Dict
    ) -> List[str]:
        """Identify risk factors from analysis"""
        risks = []

        # Module disagreement
        positive = [s for s in signals if s.signal_strength > 0.2]
        negative = [s for s in signals if s.signal_strength < -0.2]
        if positive and negative:
            risks.append(f"Conflicting signals: {len(positive)} bullish vs {len(negative)} bearish modules")

        # Low confidence
        low_confidence = [s for s in signals if s.confidence < 0.4]
        if low_confidence:
            risks.append(f"Low confidence in {', '.join(s.module_name for s in low_confidence)} analysis")

        # Echo warnings
        if echo_results:
            if echo_results.get('butterfly_coefficient', 0) > 0.7:
                risks.append("High sensitivity coefficient - small changes may cascade")
            if echo_results.get('system_stability') == 'critical':
                risks.append("System in critical state - expect volatility")

        # Causal risks
        causal_signal = next((s for s in signals if s.module_name == "causal"), None)
        if causal_signal and causal_signal.signal_strength < -0.4:
            risks.append("Deep structural issues identified in causal analysis")

        return risks

    def _get_causal_summary(self, signals: List[ModuleContribution]) -> Optional[str]:
        """Get causal analysis summary from signals"""
        causal = next((s for s in signals if s.module_name == "causal"), None)
        if causal:
            return causal.key_finding
        return None

    def _create_secondary_insights(
        self,
        temporal_results: Dict,
        semantic_results: Dict,
        causal_results: Dict,
        topology_results: Dict
    ) -> List[SingularityInsight]:
        """Create secondary insights for notable individual findings"""
        insights = []

        # Notable temporal anomalies
        if temporal_results and 'fold_results' in temporal_results:
            for fold_result in temporal_results['fold_results']:
                if fold_result.anomaly_count > 2:
                    insights.append(self._create_anomaly_insight(fold_result))
                    break  # Just one

        # Notable prophetic reviews
        if semantic_results and semantic_results.get('prophetic_reviews'):
            prophetic = semantic_results['prophetic_reviews'][0]
            insights.append(self._create_prophetic_insight(prophetic))

        return insights[:3]  # Limit secondary insights

    def _create_anomaly_insight(self, fold_result) -> SingularityInsight:
        """Create insight for temporal anomalies"""
        return SingularityInsight(
            insight_id=generate_id("insight"),
            confidence=InsightConfidence.MEDIUM,
            confidence_score=0.6,
            contributing_modules=[
                ModuleContribution(
                    module_name="temporal",
                    signal_strength=0.0,
                    confidence=0.6,
                    key_finding=f"Detected {fold_result.anomaly_count} temporal anomalies in {fold_result.fold_type.value}",
                    supporting_evidence=[]
                )
            ],
            synthesis=fold_result.insight_summary,
            key_drivers=[fold_result.insight_summary],
            trading_action=TradingAction.HOLD,
            trading_confidence=0.5
        )

    def _create_prophetic_insight(self, prophetic) -> SingularityInsight:
        """Create insight for prophetic review"""
        return SingularityInsight(
            insight_id=generate_id("insight"),
            confidence=InsightConfidence.MEDIUM,
            confidence_score=0.55,
            contributing_modules=[
                ModuleContribution(
                    module_name="semantic",
                    signal_strength=-0.3,
                    confidence=0.55,
                    key_finding=f"Prophetic review detected: {prophetic.predicted_event[:50]}",
                    supporting_evidence=[prophetic.review_text[:100]]
                )
            ],
            synthesis=f"Review from {prophetic.review_date.strftime('%Y-%m-%d')} predicted {prophetic.predicted_event} ({prophetic.lead_time_days} days early)",
            warning_signals=[f"Prophetic pattern: {prophetic.predicted_event}"],
            trading_action=TradingAction.HOLD,
            trading_confidence=0.5
        )

    def _create_no_signal_insight(self) -> SingularityInsight:
        """Create insight when no signals available"""
        return SingularityInsight(
            insight_id=generate_id("insight"),
            confidence=InsightConfidence.LOW,
            confidence_score=0.3,
            contributing_modules=[],
            synthesis="Insufficient data or module errors prevented signal generation.",
            warning_signals=["Unable to generate reliable signals"],
            trading_action=TradingAction.HOLD,
            trading_confidence=0.3
        )
