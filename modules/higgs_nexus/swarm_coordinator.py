# HIGGS NEXUS - Swarm Coordinator
# Manages adaptive node swarm for distributed processing

import asyncio
import numpy as np
import psutil
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime
import uuid
import logging

from .models import (
    NodeState,
    SwarmMetrics,
    MarketPhase,
)

logger = logging.getLogger("HiggsNexus.SwarmCoordinator")


@dataclass
class SwarmConfig:
    """Configuration for swarm coordinator"""
    # Node limits
    min_active_nodes: int = 5
    max_active_nodes: int = 100
    max_total_nodes: int = 500
    node_memory_mb: int = 5

    # Resource limits
    max_ram_usage_gb: float = 4.0
    max_cpu_percent: float = 60.0
    cpu_check_interval: float = 0.5

    # Lifecycle
    hibernation_threshold: float = 0.8     # Resource usage to trigger hibernation
    wake_threshold: float = 0.5            # Resource usage to wake nodes
    node_ttl_minutes: int = 30             # Time before idle node hibernates

    # Collective intelligence
    consensus_threshold: float = 0.7       # Agreement needed for consensus
    min_votes_for_decision: int = 3        # Min nodes for valid vote


@dataclass
class NexusNode:
    """A single processing node in the swarm"""
    node_id: str
    state: NodeState
    created_at: datetime
    last_active: datetime

    # Processing state
    energy: float = 1.0                    # 0-1, processing capacity
    opinion: float = 0.0                   # -1 to 1, current signal opinion
    confidence: float = 0.5                # 0-1, confidence in opinion
    specialization: str = "general"        # What this node focuses on

    # Memory
    knowledge: Dict[str, Any] = field(default_factory=dict)
    recent_inputs: List[np.ndarray] = field(default_factory=list)
    max_memory: int = 10

    def process(self, data: np.ndarray, context: Dict[str, Any]) -> Dict[str, float]:
        """
        Process input data and update opinion.

        Args:
            data: Input feature vector
            context: Market context (phase, volatility, etc.)

        Returns:
            Dict with opinion and confidence
        """
        self.last_active = datetime.now()

        # Store input (bounded memory)
        self.recent_inputs.append(data)
        if len(self.recent_inputs) > self.max_memory:
            self.recent_inputs.pop(0)

        # Simple processing: weighted average of recent inputs
        if len(self.recent_inputs) >= 2:
            # Trend detection
            recent = np.mean(self.recent_inputs[-3:], axis=0) if len(self.recent_inputs) >= 3 else self.recent_inputs[-1]
            older = np.mean(self.recent_inputs[:-3], axis=0) if len(self.recent_inputs) > 3 else self.recent_inputs[0]
            trend = np.mean(recent - older)

            # Opinion based on trend
            self.opinion = np.tanh(trend * 2)  # Bounded -1 to 1

            # Confidence based on consistency
            variance = np.var([np.mean(x) for x in self.recent_inputs])
            self.confidence = max(0.1, 1.0 - variance)
        else:
            self.opinion = np.tanh(np.mean(data))
            self.confidence = 0.3

        # Adjust for phase context
        phase = context.get("phase", MarketPhase.SYMMETRIC)
        if phase == MarketPhase.CHAOTIC:
            self.confidence *= 0.5
        elif phase == MarketPhase.CRITICAL:
            self.confidence *= 0.7

        # Energy decay
        self.energy = max(0.1, self.energy - 0.01)

        return {
            "opinion": self.opinion,
            "confidence": self.confidence,
            "energy": self.energy
        }

    def hibernate(self):
        """Put node in hibernation state"""
        self.state = NodeState.HIBERNATING
        self.recent_inputs = self.recent_inputs[-2:]  # Keep minimal memory
        self.energy = 0.5
        logger.debug(f"Node {self.node_id} hibernated")

    def wake(self):
        """Wake node from hibernation"""
        self.state = NodeState.ACTIVE
        self.last_active = datetime.now()
        self.energy = min(1.0, self.energy + 0.3)
        logger.debug(f"Node {self.node_id} woken")


class NodePool:
    """Manages pool of nodes with lifecycle control"""

    def __init__(self, config: SwarmConfig):
        self.config = config
        self.active: Dict[str, NexusNode] = {}
        self.hibernating: Dict[str, NexusNode] = {}

    @property
    def total_count(self) -> int:
        return len(self.active) + len(self.hibernating)

    def spawn(self, specialization: str = "general") -> Optional[NexusNode]:
        """Spawn a new node if within limits"""
        if self.total_count >= self.config.max_total_nodes:
            return None
        if len(self.active) >= self.config.max_active_nodes:
            return None

        node = NexusNode(
            node_id=str(uuid.uuid4())[:8],
            state=NodeState.ACTIVE,
            created_at=datetime.now(),
            last_active=datetime.now(),
            specialization=specialization
        )
        self.active[node.node_id] = node
        logger.debug(f"Spawned node {node.node_id} ({specialization})")
        return node

    def hibernate_node(self, node_id: str):
        """Move node to hibernation"""
        if node_id in self.active:
            node = self.active.pop(node_id)
            node.hibernate()
            self.hibernating[node_id] = node

    def wake_node(self, node_id: str) -> Optional[NexusNode]:
        """Wake a hibernating node"""
        if node_id in self.hibernating:
            if len(self.active) >= self.config.max_active_nodes:
                return None
            node = self.hibernating.pop(node_id)
            node.wake()
            self.active[node_id] = node
            return node
        return None

    def terminate_node(self, node_id: str):
        """Permanently remove a node"""
        self.active.pop(node_id, None)
        self.hibernating.pop(node_id, None)

    def get_nodes_by_specialization(self, spec: str) -> List[NexusNode]:
        """Get all active nodes with given specialization"""
        return [n for n in self.active.values() if n.specialization == spec]


class SwarmCoordinator:
    """
    Coordinates the node swarm for collective intelligence.

    Responsibilities:
    - Resource monitoring and adaptive scaling
    - Node lifecycle management
    - Collective opinion aggregation
    - Consensus building
    """

    def __init__(self, config: Optional[SwarmConfig] = None):
        self.config = config or SwarmConfig()
        self.pool = NodePool(self.config)
        self._is_running = False
        self._last_resource_check = datetime.now()

        # Collective state
        self._collective_opinion: float = 0.0
        self._collective_confidence: float = 0.0
        self._consensus_reached: bool = False
        self._dissent_reasons: List[str] = []

        logger.info(f"SwarmCoordinator initialized (max {self.config.max_active_nodes} active nodes)")

    async def start(self, initial_nodes: int = 10):
        """Start the swarm with initial nodes"""
        self._is_running = True

        # Spawn initial nodes with varied specializations
        specializations = ["trend", "volatility", "sentiment", "general"]
        for i in range(min(initial_nodes, self.config.max_active_nodes)):
            spec = specializations[i % len(specializations)]
            self.pool.spawn(specialization=spec)

        logger.info(f"Swarm started with {len(self.pool.active)} nodes")

    def stop(self):
        """Stop the swarm"""
        self._is_running = False
        logger.info("Swarm stopped")

    def process_batch(
        self,
        data_batch: List[np.ndarray],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a batch of data through the swarm.

        Args:
            data_batch: List of feature vectors
            context: Market context including phase

        Returns:
            Collective processing results
        """
        if not self.pool.active:
            return {"opinion": 0, "confidence": 0, "consensus": False}

        # Check resources
        self._check_resources()

        # Distribute data to nodes
        opinions = []
        confidences = []
        nodes = list(self.pool.active.values())

        for i, data in enumerate(data_batch):
            node = nodes[i % len(nodes)]
            result = node.process(data, context)
            opinions.append(result["opinion"] * result["confidence"])
            confidences.append(result["confidence"])

        # Aggregate collective opinion
        if confidences:
            total_confidence = sum(confidences)
            if total_confidence > 0:
                self._collective_opinion = sum(opinions) / total_confidence
                self._collective_confidence = np.mean(confidences)
            else:
                self._collective_opinion = 0
                self._collective_confidence = 0

        # Check consensus
        self._check_consensus(nodes)

        return {
            "opinion": self._collective_opinion,
            "confidence": self._collective_confidence,
            "consensus": self._consensus_reached,
            "dissent_reasons": self._dissent_reasons,
            "active_nodes": len(self.pool.active)
        }

    def _check_consensus(self, nodes: List[NexusNode]):
        """Check if swarm has reached consensus"""
        if len(nodes) < self.config.min_votes_for_decision:
            self._consensus_reached = False
            self._dissent_reasons = ["Insufficient nodes for consensus"]
            return

        opinions = [n.opinion for n in nodes if n.confidence > 0.3]
        if not opinions:
            self._consensus_reached = False
            self._dissent_reasons = ["No confident opinions"]
            return

        # Check agreement
        mean_opinion = np.mean(opinions)
        agreeing = sum(1 for o in opinions if np.sign(o) == np.sign(mean_opinion))
        agreement_ratio = agreeing / len(opinions)

        self._consensus_reached = agreement_ratio >= self.config.consensus_threshold
        self._dissent_reasons = []

        if not self._consensus_reached:
            # Identify dissent
            bullish = sum(1 for o in opinions if o > 0.1)
            bearish = sum(1 for o in opinions if o < -0.1)
            neutral = len(opinions) - bullish - bearish

            if bullish > 0 and bearish > 0:
                self._dissent_reasons.append(f"Split: {bullish} bullish, {bearish} bearish, {neutral} neutral")

    def _check_resources(self):
        """Check system resources and adjust swarm size"""
        now = datetime.now()
        if (now - self._last_resource_check).total_seconds() < 5:
            return

        self._last_resource_check = now

        # Get resource usage
        cpu = psutil.cpu_percent(interval=self.config.cpu_check_interval)
        ram = psutil.Process().memory_info().rss / (1024 ** 3)

        # Hibernate if over threshold
        if cpu > self.config.max_cpu_percent * self.config.hibernation_threshold or \
           ram > self.config.max_ram_usage_gb * self.config.hibernation_threshold:
            self._hibernate_excess()

        # Wake if under threshold and hibernating nodes exist
        elif cpu < self.config.max_cpu_percent * self.config.wake_threshold and \
             ram < self.config.max_ram_usage_gb * self.config.wake_threshold:
            self._wake_nodes(5)

        # Also hibernate idle nodes
        self._hibernate_idle()

    def _hibernate_excess(self):
        """Hibernate excess nodes to free resources"""
        if len(self.pool.active) <= self.config.min_active_nodes:
            return

        # Sort by energy (hibernate lowest energy first)
        sorted_nodes = sorted(
            self.pool.active.values(),
            key=lambda n: n.energy
        )

        to_hibernate = max(1, len(sorted_nodes) // 4)  # Hibernate 25%
        for node in sorted_nodes[:to_hibernate]:
            if len(self.pool.active) > self.config.min_active_nodes:
                self.pool.hibernate_node(node.node_id)

        logger.info(f"Hibernated {to_hibernate} nodes, {len(self.pool.active)} active")

    def _hibernate_idle(self):
        """Hibernate nodes that have been idle too long"""
        now = datetime.now()
        ttl = self.config.node_ttl_minutes * 60

        for node in list(self.pool.active.values()):
            if len(self.pool.active) <= self.config.min_active_nodes:
                break
            idle_seconds = (now - node.last_active).total_seconds()
            if idle_seconds > ttl:
                self.pool.hibernate_node(node.node_id)

    def _wake_nodes(self, count: int):
        """Wake hibernating nodes"""
        if not self.pool.hibernating:
            return

        # Sort by energy (wake highest energy first)
        sorted_nodes = sorted(
            self.pool.hibernating.values(),
            key=lambda n: n.energy,
            reverse=True
        )

        woken = 0
        for node in sorted_nodes[:count]:
            if self.pool.wake_node(node.node_id):
                woken += 1

        if woken > 0:
            logger.debug(f"Woke {woken} nodes, {len(self.pool.active)} active")

    def scale_for_phase(self, phase: MarketPhase):
        """
        Adjust swarm size based on market phase.

        Critical/Chaotic phases need more processing power.
        Stable phases can use fewer nodes.
        """
        if phase in [MarketPhase.CRITICAL, MarketPhase.CHAOTIC, MarketPhase.TRANSITION]:
            # Scale up
            target = min(self.config.max_active_nodes, len(self.pool.active) + 20)
            while len(self.pool.active) < target:
                if self.pool.hibernating:
                    node_id = next(iter(self.pool.hibernating.keys()))
                    if not self.pool.wake_node(node_id):
                        break
                else:
                    if not self.pool.spawn():
                        break

        elif phase == MarketPhase.SYMMETRIC:
            # Scale down to save resources
            target = max(self.config.min_active_nodes, len(self.pool.active) - 10)
            while len(self.pool.active) > target:
                # Hibernate lowest energy node
                lowest = min(self.pool.active.values(), key=lambda n: n.energy)
                self.pool.hibernate_node(lowest.node_id)

    def get_metrics(self) -> SwarmMetrics:
        """Get current swarm metrics"""
        cpu = psutil.cpu_percent()
        ram = psutil.Process().memory_info().rss / (1024 ** 3)

        # Calculate collective intelligence score
        if self.pool.active:
            avg_confidence = np.mean([n.confidence for n in self.pool.active.values()])
            consensus_factor = 1.0 if self._consensus_reached else 0.5
            intelligence_score = avg_confidence * consensus_factor
        else:
            intelligence_score = 0

        # Diversity index
        if len(self.pool.active) >= 2:
            opinions = [n.opinion for n in self.pool.active.values()]
            diversity = np.std(opinions) / 2  # Normalize to ~0-1
        else:
            diversity = 0

        # Convergence rate (how quickly opinions align)
        convergence = 1.0 - diversity if self._consensus_reached else diversity

        return SwarmMetrics(
            active_nodes=len(self.pool.active),
            hibernating_nodes=len(self.pool.hibernating),
            total_nodes=self.pool.total_count,
            cpu_usage_percent=cpu,
            ram_usage_gb=ram,
            average_node_energy=np.mean([n.energy for n in self.pool.active.values()]) if self.pool.active else 0,
            collective_intelligence_score=intelligence_score,
            convergence_rate=convergence,
            diversity_index=diversity
        )

    def get_collective_state(self) -> Dict[str, Any]:
        """Get current collective state"""
        return {
            "opinion": self._collective_opinion,
            "confidence": self._collective_confidence,
            "consensus": self._consensus_reached,
            "dissent_reasons": self._dissent_reasons,
            "active_nodes": len(self.pool.active),
            "hibernating_nodes": len(self.pool.hibernating)
        }
