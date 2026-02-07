# ═══════════════════════════════════════════════════════════════════════════════
# SINGULARITY ENGINE - Causal Archaeology
# Dig deep into root causes - 7+ levels of "why"
# ═══════════════════════════════════════════════════════════════════════════════

import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
import numpy as np
import structlog

from .models import (
    SingularityConfig,
    ReviewData,
    CausalNode,
    CausalEdge,
    CausalGraph,
    CausalLevel,
)
from .utils import (
    generate_id,
    normalize_sentiment,
    safe_mean,
    truncate_text,
    extract_keywords,
    combine_confidences,
)

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CAUSAL PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

# Patterns that indicate causality in reviews
CAUSAL_INDICATORS = [
    r'because\s+of',
    r'due\s+to',
    r'caused\s+by',
    r'result\s+of',
    r'thanks\s+to',
    r'since\s+they',
    r'after\s+they',
    r'when\s+they',
    r'ever\s+since',
    r'led\s+to',
    r'resulting\s+in',
]

# Known causal chains in hospitality/retail
CAUSAL_KNOWLEDGE_BASE = {
    # Level 0 -> Level 1 (Symptom -> Proximate Cause)
    'low_rating': ['bad_service', 'long_wait', 'dirty', 'rude_staff', 'wrong_order'],
    'bad_service': ['understaffed', 'untrained', 'overwhelmed', 'no_manager'],
    'long_wait': ['understaffed', 'kitchen_slow', 'short_staffed', 'too_busy'],
    'dirty': ['no_cleaning', 'overwhelmed_staff', 'budget_cuts', 'no_standards'],
    'rude_staff': ['overworked', 'underpaid', 'bad_management', 'burnout'],
    'wrong_order': ['rushed', 'understaffed', 'poor_training', 'new_staff'],

    # Level 1 -> Level 2 (Proximate -> Intermediate)
    'understaffed': ['high_turnover', 'budget_cuts', 'hiring_freeze', 'location_issues'],
    'untrained': ['high_turnover', 'budget_cuts', 'rapid_expansion', 'poor_management'],
    'overwhelmed': ['understaffed', 'bad_scheduling', 'unexpected_rush', 'promotion'],
    'overworked': ['understaffed', 'bad_scheduling', 'cost_cutting', 'high_turnover'],
    'underpaid': ['cost_cutting', 'corporate_policy', 'market_wages', 'franchise_issues'],

    # Level 2 -> Level 3 (Intermediate -> Structural)
    'high_turnover': ['low_wages', 'bad_culture', 'better_opportunities', 'burnout'],
    'budget_cuts': ['corporate_pressure', 'declining_sales', 'margin_squeeze', 'debt'],
    'poor_management': ['bad_hiring', 'no_training', 'corporate_culture', 'turnover'],
    'rapid_expansion': ['investor_pressure', 'market_opportunity', 'competition'],

    # Level 3 -> Level 4 (Structural -> Systemic)
    'low_wages': ['industry_standard', 'corporate_greed', 'inflation', 'labor_surplus'],
    'corporate_pressure': ['investor_demands', 'quarterly_targets', 'competition'],
    'declining_sales': ['market_shift', 'competition', 'quality_decline', 'economic'],
    'margin_squeeze': ['cost_inflation', 'price_competition', 'supply_chain'],

    # Level 4 -> Level 5 (Systemic -> Macro)
    'investor_demands': ['market_expectations', 'short_termism', 'activist_investors'],
    'market_shift': ['consumer_trends', 'demographic_change', 'tech_disruption'],
    'competition': ['market_saturation', 'new_entrants', 'price_war'],
    'economic': ['recession', 'inflation', 'unemployment', 'consumer_confidence'],

    # Level 5 -> Level 6+ (Macro -> Global)
    'inflation': ['monetary_policy', 'supply_chain', 'energy_costs', 'global_events'],
    'recession': ['economic_cycle', 'policy_failure', 'external_shock'],
    'supply_chain': ['global_logistics', 'pandemic', 'geopolitical', 'climate'],
}

# Keywords that indicate specific causes
CAUSE_KEYWORDS = {
    'bad_service': ['service', 'terrible service', 'awful service', 'poor service'],
    'long_wait': ['wait', 'waiting', 'took forever', 'slow', 'hour for', 'minutes for'],
    'dirty': ['dirty', 'filthy', 'gross', 'unclean', 'disgusting', 'mess'],
    'rude_staff': ['rude', 'attitude', 'disrespectful', 'mean', 'unfriendly'],
    'wrong_order': ['wrong order', 'messed up', 'incorrect', 'not what I ordered'],
    'understaffed': ['understaffed', 'short staffed', 'not enough', 'one person'],
    'overworked': ['overwhelmed', 'stressed', 'rushed', 'running around'],
    'management': ['manager', 'management', 'corporate', 'owner'],
    'training': ['training', 'trained', 'dont know', "don't know", 'no idea'],
    'quality': ['quality', 'used to be', 'not like before', 'worse'],
    'price': ['expensive', 'overpriced', 'price', 'cost', 'money'],
}


class CausalArchaeologist:
    """
    Causal Archaeology - Dig Deep into Root Causes

    Implements the "7 Whys" methodology to trace symptoms back to
    their root causes, using a combination of:
    1. Pattern matching in review text
    2. Statistical correlation between issues
    3. Domain knowledge base
    4. Optional LLM-based inference

    Example:
        Symptom: "Rating dropped 20%"
        Level 1: "Bad service mentioned in reviews"
        Level 2: "Staff seems overwhelmed/understaffed"
        Level 3: "High turnover indicated by reviews"
        Level 4: "Low wages compared to market"
        Level 5: "Corporate cost-cutting pressure"
        Level 6: "Investor demands for margins"
        Level 7: "Market-wide labor shortage + inflation"
    """

    def __init__(
        self,
        reviews: List[ReviewData],
        config: Optional[SingularityConfig] = None
    ):
        self.reviews = reviews
        self.config = config or SingularityConfig()

        # Index reviews by chain and city for filtering
        self._reviews_by_chain = self._index_by_chain()

        # Compile regex patterns
        self._causal_patterns = [re.compile(p, re.IGNORECASE) for p in CAUSAL_INDICATORS]

        logger.info(
            "causal_archaeologist_initialized",
            review_count=len(reviews),
            knowledge_base_size=len(CAUSAL_KNOWLEDGE_BASE)
        )

    def _index_by_chain(self) -> Dict[str, List[ReviewData]]:
        """Index reviews by chain"""
        index = defaultdict(list)
        for r in self.reviews:
            if r.chain_id:
                index[r.chain_id.lower()].append(r)
        return dict(index)

    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN ANALYSIS METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def identify_symptoms(
        self,
        reviews: Optional[List[ReviewData]] = None
    ) -> List[str]:
        """
        Identify main symptoms to investigate from reviews

        Args:
            reviews: Reviews to analyze

        Returns:
            List of symptom descriptions
        """
        reviews = reviews or self.reviews
        symptoms = []

        # Analyze overall sentiment
        sentiments = [
            r.sentiment_score if r.sentiment_score is not None
            else normalize_sentiment(r.rating) if r.rating else 0
            for r in reviews
        ]

        avg_sentiment = safe_mean(sentiments)
        negative_reviews = [r for r in reviews if self._is_negative(r)]
        negative_ratio = len(negative_reviews) / len(reviews) if reviews else 0

        # Symptom 1: Overall negative sentiment
        if avg_sentiment < -0.2:
            symptoms.append(f"Overall sentiment negative ({avg_sentiment:.2f})")

        # Symptom 2: High proportion of negative reviews
        if negative_ratio > 0.3:
            symptoms.append(f"High negative review ratio ({negative_ratio:.1%})")

        # Symptom 3: Specific issues mentioned frequently
        issue_counts = self._count_issues(negative_reviews)
        for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
            if count >= self.config.causal_min_evidence:
                symptoms.append(f"{issue.replace('_', ' ').title()} mentioned in {count} reviews")

        return symptoms

    def investigate(
        self,
        symptom: str,
        max_depth: int = 7,
        chain_filter: Optional[str] = None
    ) -> CausalGraph:
        """
        Investigate a symptom to find root causes

        Args:
            symptom: The symptom to investigate
            max_depth: Maximum depth to dig (up to 7+ levels)
            chain_filter: Optional filter by chain

        Returns:
            CausalGraph with full causal chain
        """
        logger.info(
            "investigating_symptom",
            symptom=symptom,
            max_depth=max_depth,
            chain_filter=chain_filter
        )

        # Filter reviews if needed
        if chain_filter:
            reviews = self._reviews_by_chain.get(chain_filter.lower(), [])
        else:
            reviews = self.reviews

        negative_reviews = [r for r in reviews if self._is_negative(r)]

        if len(negative_reviews) < self.config.causal_min_evidence:
            return self._create_empty_graph(symptom, "Insufficient negative reviews")

        # Initialize graph
        nodes = {}
        edges = []
        current_depth = 0

        # Create root node (symptom)
        root_node = CausalNode(
            node_id=generate_id("node"),
            level=CausalLevel.SYMPTOM,
            description=symptom,
            evidence_count=len(negative_reviews),
            confidence=1.0,
            source_reviews=[r.review_id for r in negative_reviews[:10]],
            extracted_quotes=self._extract_quotes(negative_reviews, 3)
        )
        nodes[root_node.node_id] = root_node

        # Build causal chain
        current_nodes = [root_node]
        all_explored = set()

        while current_depth < max_depth and current_nodes:
            next_nodes = []
            current_depth += 1
            level = self._depth_to_level(current_depth)

            for parent_node in current_nodes:
                # Find causes for this node
                causes = self._find_causes(
                    parent_node.description,
                    negative_reviews,
                    all_explored
                )

                for cause_desc, evidence_count, confidence, quotes, review_ids in causes:
                    all_explored.add(cause_desc)

                    # Create child node
                    child_node = CausalNode(
                        node_id=generate_id("node"),
                        level=level,
                        description=cause_desc,
                        evidence_count=evidence_count,
                        confidence=confidence,
                        source_reviews=review_ids[:10],
                        extracted_quotes=quotes,
                        inferred=evidence_count == 0
                    )
                    nodes[child_node.node_id] = child_node
                    next_nodes.append(child_node)

                    # Create edge
                    edge = CausalEdge(
                        source_id=parent_node.node_id,
                        target_id=child_node.node_id,
                        weight=confidence,
                        evidence=f"{evidence_count} reviews mention this"
                    )
                    edges.append(edge)

            current_nodes = next_nodes

        # Find critical path and root causes
        critical_path = self._find_critical_path(nodes, edges, root_node.node_id)
        root_causes = self._find_root_causes(nodes, edges)

        # Calculate overall confidence
        if nodes:
            overall_confidence = combine_confidences(
                [n.confidence for n in nodes.values()],
                method="harmonic"
            )
        else:
            overall_confidence = 0.0

        # Generate insight summary
        insight = self._generate_insight(nodes, critical_path, root_causes)

        return CausalGraph(
            graph_id=generate_id("graph"),
            root_symptom=symptom,
            max_depth_reached=current_depth,
            nodes=nodes,
            edges=edges,
            critical_path=critical_path,
            root_causes=root_causes,
            total_evidence_count=sum(n.evidence_count for n in nodes.values()),
            overall_confidence=overall_confidence,
            insight_summary=insight
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # CAUSE FINDING
    # ═══════════════════════════════════════════════════════════════════════════

    def _find_causes(
        self,
        symptom_desc: str,
        reviews: List[ReviewData],
        already_explored: Set[str]
    ) -> List[Tuple[str, int, float, List[str], List[str]]]:
        """
        Find potential causes for a symptom

        Returns:
            List of (description, evidence_count, confidence, quotes, review_ids)
        """
        causes = []

        # Method 1: Look in knowledge base
        symptom_key = self._normalize_to_key(symptom_desc)
        if symptom_key in CAUSAL_KNOWLEDGE_BASE:
            for cause_key in CAUSAL_KNOWLEDGE_BASE[symptom_key]:
                if cause_key in already_explored:
                    continue

                # Search reviews for evidence
                evidence_reviews = self._find_evidence_reviews(cause_key, reviews)
                evidence_count = len(evidence_reviews)
                confidence = min(1.0, evidence_count / 10) * 0.7  # Max 70% from evidence

                if evidence_count >= self.config.causal_min_evidence or confidence > 0:
                    cause_desc = cause_key.replace('_', ' ').title()
                    quotes = self._extract_quotes(evidence_reviews, 2)
                    review_ids = [r.review_id for r in evidence_reviews]
                    causes.append((cause_desc, evidence_count, confidence, quotes, review_ids))

        # Method 2: Extract causes directly from review text
        text_causes = self._extract_causes_from_text(reviews, already_explored)
        causes.extend(text_causes)

        # Method 3: Use knowledge base inference even without direct evidence
        if not causes and symptom_key in CAUSAL_KNOWLEDGE_BASE:
            for cause_key in CAUSAL_KNOWLEDGE_BASE[symptom_key][:2]:
                if cause_key not in already_explored:
                    cause_desc = cause_key.replace('_', ' ').title()
                    causes.append((cause_desc, 0, 0.3, [], []))  # Inferred

        # Sort by confidence and evidence
        causes.sort(key=lambda x: (x[2], x[1]), reverse=True)

        return causes[:5]  # Top 5 causes

    def _find_evidence_reviews(
        self,
        cause_key: str,
        reviews: List[ReviewData]
    ) -> List[ReviewData]:
        """Find reviews that mention a specific cause"""
        keywords = CAUSE_KEYWORDS.get(cause_key, [cause_key.replace('_', ' ')])
        evidence = []

        for review in reviews:
            text_lower = review.text.lower()
            if any(kw.lower() in text_lower for kw in keywords):
                evidence.append(review)

        return evidence

    def _extract_causes_from_text(
        self,
        reviews: List[ReviewData],
        already_explored: Set[str]
    ) -> List[Tuple[str, int, float, List[str], List[str]]]:
        """Extract causal statements directly from review text"""
        cause_mentions = defaultdict(list)

        for review in reviews:
            text = review.text

            # Look for causal phrases
            for pattern in self._causal_patterns:
                matches = pattern.finditer(text)
                for match in matches:
                    # Get the phrase after the causal indicator
                    start = match.end()
                    end = min(start + 100, len(text))
                    phrase = text[start:end].strip()

                    # Clean up
                    phrase = re.split(r'[.!?,]', phrase)[0].strip()
                    if len(phrase) > 10 and len(phrase) < 100:
                        cause_mentions[phrase.lower()].append(review)

        # Convert to causes
        causes = []
        for phrase, evidence_reviews in cause_mentions.items():
            if phrase in already_explored:
                continue
            if len(evidence_reviews) >= 2:
                confidence = min(1.0, len(evidence_reviews) / 5) * 0.6
                quotes = [truncate_text(r.text, 100) for r in evidence_reviews[:2]]
                review_ids = [r.review_id for r in evidence_reviews]
                causes.append((phrase.title(), len(evidence_reviews), confidence, quotes, review_ids))

        return causes[:3]

    # ═══════════════════════════════════════════════════════════════════════════
    # GRAPH ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════

    def _find_critical_path(
        self,
        nodes: Dict[str, CausalNode],
        edges: List[CausalEdge],
        root_id: str
    ) -> List[str]:
        """Find the most significant causal path"""
        if not nodes or not edges:
            return [root_id] if root_id in nodes else []

        # Build adjacency list
        adj = defaultdict(list)
        for edge in edges:
            adj[edge.source_id].append((edge.target_id, edge.weight))

        # Find path with highest cumulative weight
        best_path = [root_id]
        best_score = 0

        def dfs(node_id: str, path: List[str], score: float):
            nonlocal best_path, best_score

            if node_id not in adj or not adj[node_id]:
                # Leaf node
                if score > best_score:
                    best_score = score
                    best_path = path.copy()
                return

            for child_id, weight in adj[node_id]:
                if child_id not in path:  # Avoid cycles
                    path.append(child_id)
                    dfs(child_id, path, score + weight)
                    path.pop()

        dfs(root_id, [root_id], 0)
        return best_path

    def _find_root_causes(
        self,
        nodes: Dict[str, CausalNode],
        edges: List[CausalEdge]
    ) -> List[str]:
        """Find nodes that have no outgoing edges (root causes)"""
        sources = set(e.source_id for e in edges)
        targets = set(e.target_id for e in edges)

        # Nodes that are targets but not sources
        root_cause_ids = targets - sources

        # Sort by confidence
        root_causes = sorted(
            [nodes[nid] for nid in root_cause_ids if nid in nodes],
            key=lambda n: n.confidence,
            reverse=True
        )

        return [n.node_id for n in root_causes]

    def _depth_to_level(self, depth: int) -> CausalLevel:
        """Convert depth to causal level"""
        if depth <= 1:
            return CausalLevel.PROXIMATE
        elif depth <= 3:
            return CausalLevel.INTERMEDIATE
        elif depth <= 5:
            return CausalLevel.STRUCTURAL
        elif depth <= 6:
            return CausalLevel.SYSTEMIC
        else:
            return CausalLevel.MACRO

    # ═══════════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def _is_negative(self, review: ReviewData) -> bool:
        """Check if a review is negative"""
        if review.sentiment_score is not None:
            return review.sentiment_score < -0.2
        if review.rating:
            return review.rating <= 2.5
        return False

    def _count_issues(self, reviews: List[ReviewData]) -> Dict[str, int]:
        """Count occurrences of different issues in reviews"""
        counts = defaultdict(int)
        for review in reviews:
            text_lower = review.text.lower()
            for issue_key, keywords in CAUSE_KEYWORDS.items():
                if any(kw.lower() in text_lower for kw in keywords):
                    counts[issue_key] += 1
        return dict(counts)

    def _extract_quotes(
        self,
        reviews: List[ReviewData],
        max_quotes: int = 3
    ) -> List[str]:
        """Extract representative quotes from reviews"""
        quotes = []
        for review in reviews[:max_quotes * 2]:
            # Find a good excerpt
            text = review.text
            # Try to find a sentence with a causal indicator
            sentences = re.split(r'[.!?]', text)
            for sentence in sentences:
                if any(p.search(sentence) for p in self._causal_patterns):
                    quotes.append(truncate_text(sentence.strip(), 150))
                    break
            else:
                # Just take the first meaningful sentence
                for sentence in sentences:
                    if len(sentence.strip()) > 20:
                        quotes.append(truncate_text(sentence.strip(), 150))
                        break

            if len(quotes) >= max_quotes:
                break

        return quotes

    def _normalize_to_key(self, description: str) -> str:
        """Normalize description to knowledge base key"""
        # Remove common words and convert to key format
        desc_lower = description.lower()

        # Try to match to known keys
        for key in CAUSAL_KNOWLEDGE_BASE.keys():
            key_words = key.replace('_', ' ')
            if key_words in desc_lower or desc_lower in key_words:
                return key

        # Try keyword matching
        for key, keywords in CAUSE_KEYWORDS.items():
            if any(kw.lower() in desc_lower for kw in keywords):
                return key

        # Fallback: convert to key format
        return re.sub(r'\s+', '_', desc_lower.strip())[:30]

    def _generate_insight(
        self,
        nodes: Dict[str, CausalNode],
        critical_path: List[str],
        root_causes: List[str]
    ) -> str:
        """Generate human-readable insight summary"""
        if not nodes:
            return "Unable to determine causal chain."

        insights = []

        # Describe the critical path
        if len(critical_path) >= 2:
            path_descriptions = [nodes[nid].description for nid in critical_path if nid in nodes]
            chain = " -> ".join(path_descriptions[:5])
            insights.append(f"Primary causal chain: {chain}")

        # Describe root causes
        if root_causes:
            root_descriptions = [
                nodes[nid].description for nid in root_causes[:3]
                if nid in nodes
            ]
            if root_descriptions:
                insights.append(f"Root causes identified: {', '.join(root_descriptions)}")

        # Note confidence
        high_confidence = [n for n in nodes.values() if n.confidence > 0.7 and not n.inferred]
        if high_confidence:
            insights.append(
                f"{len(high_confidence)} causes supported by direct review evidence"
            )

        inferred = [n for n in nodes.values() if n.inferred]
        if inferred:
            insights.append(
                f"{len(inferred)} causes inferred from domain knowledge"
            )

        return "; ".join(insights) if insights else "Causal analysis complete."

    def _create_empty_graph(self, symptom: str, reason: str) -> CausalGraph:
        """Create empty graph when analysis cannot proceed"""
        return CausalGraph(
            graph_id=generate_id("graph"),
            root_symptom=symptom,
            max_depth_reached=0,
            nodes={},
            edges=[],
            critical_path=[],
            root_causes=[],
            total_evidence_count=0,
            overall_confidence=0.0,
            insight_summary=reason
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # COMPARISON METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def compare_chains_causal(
        self,
        chain_a: str,
        chain_b: str
    ) -> Dict[str, any]:
        """
        Compare causal patterns between two chains

        Args:
            chain_a: First chain name
            chain_b: Second chain name

        Returns:
            Comparison of causal patterns
        """
        reviews_a = self._reviews_by_chain.get(chain_a.lower(), [])
        reviews_b = self._reviews_by_chain.get(chain_b.lower(), [])

        if len(reviews_a) < 10 or len(reviews_b) < 10:
            return {'error': 'Insufficient reviews for comparison'}

        # Get issue counts for each
        neg_a = [r for r in reviews_a if self._is_negative(r)]
        neg_b = [r for r in reviews_b if self._is_negative(r)]

        issues_a = self._count_issues(neg_a)
        issues_b = self._count_issues(neg_b)

        # Normalize by count
        total_a = len(neg_a) or 1
        total_b = len(neg_b) or 1

        all_issues = set(issues_a.keys()) | set(issues_b.keys())

        comparison = []
        for issue in all_issues:
            rate_a = issues_a.get(issue, 0) / total_a
            rate_b = issues_b.get(issue, 0) / total_b
            comparison.append({
                'issue': issue.replace('_', ' ').title(),
                f'{chain_a}_rate': rate_a,
                f'{chain_b}_rate': rate_b,
                'difference': rate_a - rate_b,
                'more_common_in': chain_a if rate_a > rate_b else chain_b
            })

        comparison.sort(key=lambda x: abs(x['difference']), reverse=True)

        return {
            'chain_a': chain_a,
            'chain_b': chain_b,
            'negative_review_rate_a': len(neg_a) / len(reviews_a),
            'negative_review_rate_b': len(neg_b) / len(reviews_b),
            'issue_comparison': comparison
        }
