#!/usr/bin/env python3
"""
ECHO ENGINE - Quantum-Inspired Sentiment Propagation
System 5.0.7 - Neural Hub for ReviewSignal

Inspired by Google Willow Quantum Echo Algorithm (OTOC)
Acts as the central "neural connection" between all ReviewSignal modules.

Author: ReviewSignal Team
Version: 5.0.7
Date: January 2026

Business Applications:
- Early Warning System: Predict cascading sentiment drops before earnings
- Contagion Detection: Identify which locations are most "infectious"
- What-If Scenarios: Strategic simulations for CMO/CEO
- Chaos Indicators: Risk assessment for investors
"""

import os
import numpy as np
from scipy.sparse import csr_matrix, lil_matrix
from scipy.sparse.linalg import spsolve
from typing import List, Dict, Optional, Tuple, Any, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import structlog

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════

class SystemStability(Enum):
    """System stability classification based on echo values"""
    STABLE = "stable"           # Echo < 1.0 - System absorbs perturbations
    UNSTABLE = "unstable"       # Echo 1.0-3.0 - Moderate sensitivity
    CHAOTIC = "chaotic"         # Echo > 3.0 - High sensitivity, cascades likely


class SignalType(Enum):
    """Trading signal types"""
    BUY = "buy"                 # System stable, resilient to shocks
    HOLD = "hold"               # Neutral state
    SELL = "sell"               # System unstable, cascade risk high


class PropagationType(Enum):
    """Types of sentiment propagation"""
    GEOGRAPHIC = "geographic"   # Based on physical distance
    BRAND = "brand"             # Same chain/brand connection
    CATEGORY = "category"       # Same business category
    CITY = "city"               # Same city cluster


# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class LocationState:
    """Represents a location's state in the propagation network"""
    location_id: str
    name: str
    latitude: float
    longitude: float
    chain_id: Optional[str]
    city: str
    category: Optional[str]
    current_sentiment: float  # -1 to 1
    current_rating: float     # 0 to 5
    review_count: int

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class EchoResult:
    """Result of echo calculation for a single perturbation"""
    echo_value: float
    source_location: str
    source_location_id: str
    perturbation_delta: float
    time_steps: int
    butterfly_coefficient: float
    system_stability: SystemStability
    top_affected_locations: List[Dict]
    propagation_path: List[str]
    computed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['system_stability'] = self.system_stability.value
        return data


@dataclass
class MonteCarloResult:
    """Result of Monte Carlo simulation"""
    n_trials: int
    mean_echo: float
    std_echo: float
    max_echo: float
    min_echo: float
    system_chaos_index: float
    percentile_95: float
    percentile_99: float
    critical_locations: List[Dict]
    stability_distribution: Dict[str, float]
    computed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TradingSignal:
    """Trading signal generated from Echo Engine analysis"""
    brand: str
    signal: SignalType
    confidence: float           # 0 to 1
    chaos_index: float
    echo_mean: float
    echo_std: float
    critical_locations: List[Dict]
    recommendation: str
    risk_level: str
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['signal'] = self.signal.value
        return data


@dataclass
class PropagationEdge:
    """Edge in the propagation network"""
    source_idx: int
    target_idx: int
    weight: float
    propagation_type: PropagationType
    distance_km: Optional[float] = None


@dataclass
class EchoEngineConfig:
    """Configuration for Echo Engine"""
    # Propagation weights
    self_influence: float = 0.7        # Inertia (how much location keeps its own sentiment)
    geo_weight_max: float = 0.15       # Max weight for geographic proximity
    geo_radius_km: float = 50.0        # Radius for geographic influence
    brand_weight: float = 0.20         # Weight for same brand
    city_weight: float = 0.08          # Weight for same city
    category_weight: float = 0.05      # Weight for same category

    # Echo parameters
    default_time_steps: int = 10       # Default evolution steps
    default_perturbation: float = -0.5 # Default perturbation (rating drop)

    # Monte Carlo
    default_mc_trials: int = 500       # Default Monte Carlo trials

    # Thresholds (calibrated for typical sentiment networks)
    # Echo is normalized by sqrt(n), typical range 0.5-5.0
    chaos_threshold_low: float = 1.5   # Below this = stable
    chaos_threshold_high: float = 3.5  # Above this = chaotic

    def to_dict(self) -> Dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth.

    Args:
        lat1, lon1: Coordinates of first point (degrees)
        lat2, lon2: Coordinates of second point (degrees)

    Returns:
        Distance in kilometers
    """
    R = 6371.0  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def normalize_sentiment(rating: float, min_rating: float = 1.0, max_rating: float = 5.0) -> float:
    """
    Convert rating to sentiment score (-1 to 1).

    Args:
        rating: Rating value (typically 1-5)
        min_rating: Minimum possible rating
        max_rating: Maximum possible rating

    Returns:
        Sentiment score between -1 and 1
    """
    mid = (max_rating + min_rating) / 2
    return (rating - mid) / (max_rating - mid)


# ═══════════════════════════════════════════════════════════════════
# MAIN CLASS
# ═══════════════════════════════════════════════════════════════════

class EchoEngine:
    """
    Quantum-inspired sentiment propagation analyzer.
    Measures "butterfly effect" in review sentiment networks.

    Core Algorithm (inspired by OTOC - Out-of-Time-Order Correlator):
    1. Initial state x₀ = sentiment vector of all locations
    2. Forward evolution: x_T = F^T(x₀) where F is propagation matrix
    3. Perturbation: x'_T = x_T + δ·eᵢ (inject small change at location i)
    4. Backward evolution: x'₀ = F^(-T)(x'_T)
    5. Echo measurement: D = ||x'₀ - x₀|| (how much change propagated back)

    High echo = chaotic system, small changes cascade
    Low echo = stable system, absorbs perturbations
    """

    def __init__(
        self,
        locations: List[LocationState],
        config: Optional[EchoEngineConfig] = None
    ):
        """
        Initialize Echo Engine.

        Args:
            locations: List of LocationState objects
            config: EchoEngineConfig (uses defaults if not provided)
        """
        self.config = config or EchoEngineConfig()
        self.locations = locations
        self.n = len(locations)

        # Build lookup indices
        self._location_idx_map = {loc.location_id: i for i, loc in enumerate(locations)}
        self._chain_locations: Dict[str, List[int]] = {}
        self._city_locations: Dict[str, List[int]] = {}
        self._category_locations: Dict[str, List[int]] = {}

        self._build_location_indices()

        # Build propagation matrix (lazy - built on first use)
        self._propagation_matrix: Optional[csr_matrix] = None
        self._propagation_matrix_inverse: Optional[np.ndarray] = None

        logger.info(
            "echo_engine_initialized",
            n_locations=self.n,
            n_chains=len(self._chain_locations),
            n_cities=len(self._city_locations)
        )

    def _build_location_indices(self) -> None:
        """Build lookup indices for efficient propagation calculation."""
        for i, loc in enumerate(self.locations):
            # Chain index
            if loc.chain_id:
                if loc.chain_id not in self._chain_locations:
                    self._chain_locations[loc.chain_id] = []
                self._chain_locations[loc.chain_id].append(i)

            # City index
            if loc.city:
                if loc.city not in self._city_locations:
                    self._city_locations[loc.city] = []
                self._city_locations[loc.city].append(i)

            # Category index
            if loc.category:
                if loc.category not in self._category_locations:
                    self._category_locations[loc.category] = []
                self._category_locations[loc.category].append(i)

    def _build_propagation_matrix(self) -> csr_matrix:
        """
        Build the propagation matrix F.

        The matrix defines how sentiment "flows" between locations based on:
        - Geographic proximity (closer = stronger influence)
        - Same brand (strong influence)
        - Same city (moderate influence)
        - Same category (weak influence)

        Returns:
            Sparse CSR matrix of shape (n, n)
        """
        if self._propagation_matrix is not None:
            return self._propagation_matrix

        logger.info("building_propagation_matrix", n_locations=self.n)

        # Use LIL format for efficient construction, then convert to CSR
        F = lil_matrix((self.n, self.n), dtype=np.float64)

        # Set self-influence (diagonal)
        for i in range(self.n):
            F[i, i] = self.config.self_influence

        # Build edges efficiently using indices
        edges_added = 0

        # Brand connections (same chain)
        for chain_id, indices in self._chain_locations.items():
            for i in indices:
                for j in indices:
                    if i != j:
                        F[i, j] += self.config.brand_weight
                        edges_added += 1

        # City connections
        for city, indices in self._city_locations.items():
            for i in indices:
                for j in indices:
                    if i != j:
                        F[i, j] += self.config.city_weight
                        edges_added += 1

        # Category connections
        for category, indices in self._category_locations.items():
            for i in indices:
                for j in indices:
                    if i != j:
                        F[i, j] += self.config.category_weight
                        edges_added += 1

        # Geographic connections (for locations in same city, add distance-based weight)
        for city, indices in self._city_locations.items():
            for i in indices:
                loc_i = self.locations[i]
                for j in indices:
                    if i != j:
                        loc_j = self.locations[j]
                        if loc_i.latitude and loc_i.longitude and loc_j.latitude and loc_j.longitude:
                            dist = haversine_distance(
                                loc_i.latitude, loc_i.longitude,
                                loc_j.latitude, loc_j.longitude
                            )
                            if dist < self.config.geo_radius_km:
                                geo_weight = self.config.geo_weight_max * (1 - dist / self.config.geo_radius_km)
                                F[i, j] += geo_weight

        # Normalize rows (each row sums to 1 for proper Markov-like propagation)
        F_csr = F.tocsr()
        row_sums = np.array(F_csr.sum(axis=1)).flatten()
        row_sums[row_sums == 0] = 1  # Avoid division by zero

        # Create diagonal matrix with 1/row_sum
        D_inv = csr_matrix((1.0 / row_sums, (range(self.n), range(self.n))), shape=(self.n, self.n))
        self._propagation_matrix = D_inv @ F_csr

        logger.info(
            "propagation_matrix_built",
            edges=edges_added,
            density=self._propagation_matrix.nnz / (self.n * self.n)
        )

        return self._propagation_matrix

    def get_state_vector(self) -> np.ndarray:
        """
        Get current sentiment state as a normalized vector.

        Returns:
            Normalized sentiment vector (z-scored)
        """
        x = np.array([loc.current_sentiment for loc in self.locations], dtype=np.float64)

        mean = np.mean(x)
        std = np.std(x)

        if std == 0:
            return x - mean

        return (x - mean) / std

    def evolve_forward(self, x: np.ndarray, T: int) -> np.ndarray:
        """
        Evolve state FORWARD through T time steps.
        x_{t+1} = F @ x_t

        Args:
            x: State vector
            T: Number of time steps

        Returns:
            Evolved state vector
        """
        F = self._build_propagation_matrix()
        x_current = x.copy()

        for _ in range(T):
            x_current = F @ x_current

        return x_current

    def evolve_backward(self, x: np.ndarray, T: int) -> np.ndarray:
        """
        Evolve state BACKWARD through T time steps.
        Uses iterative solver for numerical stability and memory efficiency.

        In the quantum OTOC analogy, backward evolution represents
        "uncomputing" the forward dynamics. We use conjugate gradient
        with Tikhonov regularization for scalability to large networks.

        Args:
            x: State vector
            T: Number of time steps

        Returns:
            Backward-evolved state vector
        """
        from scipy.sparse.linalg import cg, LinearOperator

        F = self._build_propagation_matrix()

        # Use iterative solver for memory efficiency with large networks
        # This avoids dense matrix operations for 30k+ locations

        # Regularization parameter
        lambda_reg = 0.01

        def matvec(v):
            """Matrix-vector product for (F^T F + λI) v"""
            Fv = F @ v
            FtFv = F.T @ Fv
            return FtFv + lambda_reg * v

        # Create LinearOperator for iterative solver
        A_op = LinearOperator(
            shape=(self.n, self.n),
            matvec=matvec,
            dtype=np.float64
        )

        x_current = x.copy()

        for _ in range(T):
            # Solve (F^T F + λI) x' = F^T x using conjugate gradient
            Ft_x = F.T @ x_current
            x_current, info = cg(A_op, Ft_x, x0=x_current, maxiter=100, tol=1e-6)

            if info != 0:
                logger.warning("cg_solver_warning", info=info)

            # Re-normalize to prevent explosion
            norm = np.linalg.norm(x_current)
            if norm > 10:
                x_current = x_current / norm * 10

        return x_current

    def inject_perturbation(
        self,
        x: np.ndarray,
        location_idx: int,
        delta: float
    ) -> np.ndarray:
        """
        Inject a small perturbation at a single location.
        Simulates e.g., sudden rating drop of 0.5 stars.

        Args:
            x: State vector
            location_idx: Index of location to perturb
            delta: Perturbation magnitude

        Returns:
            Perturbed state vector
        """
        x_pert = x.copy()
        x_pert[location_idx] += delta
        return x_pert

    def measure_echo(self, x0: np.ndarray, x0_prime: np.ndarray) -> float:
        """
        Measure the "echo" - difference between original and perturbed states.

        The echo is normalized by the number of locations to give a
        per-location average effect, making it comparable across different
        system sizes.

        Args:
            x0: Original state
            x0_prime: State after perturbation and forward-backward evolution

        Returns:
            Echo value (normalized L2 norm of difference)
        """
        # Normalize by sqrt(n) to make echo scale-independent
        raw_echo = float(np.linalg.norm(x0_prime - x0))
        return raw_echo / np.sqrt(self.n)

    def compute_echo(
        self,
        location_idx: int,
        T: Optional[int] = None,
        delta: Optional[float] = None
    ) -> EchoResult:
        """
        MAIN ECHO COMPUTATION

        1. Get initial state x₀
        2. Forward evolution: x_T = F^T(x₀)
        3. Perturbation: x'_T = x_T + δ·e_i
        4. Backward evolution: x'₀ = F^(-T)(x'_T)
        5. Measure echo: D = ||x'₀ - x₀||

        Args:
            location_idx: Index of location to perturb
            T: Number of time steps (default from config)
            delta: Perturbation magnitude (default from config)

        Returns:
            EchoResult with analysis
        """
        T = T or self.config.default_time_steps
        delta = delta if delta is not None else self.config.default_perturbation

        # 1. Initial state
        x0 = self.get_state_vector()

        # 2. Forward evolution
        x_T = self.evolve_forward(x0.copy(), T)

        # 3. Perturbation
        x_T_pert = self.inject_perturbation(x_T, location_idx, delta)

        # 4. Backward evolution
        x0_prime = self.evolve_backward(x_T_pert, T)

        # 5. Measure echo
        echo_value = self.measure_echo(x0, x0_prime)

        # Analyze impact
        impact_vector = np.abs(x0_prime - x0)
        top_indices = np.argsort(impact_vector)[-10:][::-1]

        # Classify stability
        if echo_value > self.config.chaos_threshold_high:
            stability = SystemStability.CHAOTIC
        elif echo_value > self.config.chaos_threshold_low:
            stability = SystemStability.UNSTABLE
        else:
            stability = SystemStability.STABLE

        # Build result
        source_loc = self.locations[location_idx]

        top_affected = []
        for idx in top_indices:
            affected_loc = self.locations[idx]
            top_affected.append({
                "location_id": affected_loc.location_id,
                "name": affected_loc.name,
                "city": affected_loc.city,
                "chain_id": affected_loc.chain_id,
                "impact": float(impact_vector[idx])
            })

        # Build propagation path (simplified - top 5 by impact)
        propagation_path = [self.locations[idx].name for idx in top_indices[:5]]

        # Butterfly coefficient: echo per unit perturbation
        butterfly_coeff = echo_value / abs(delta) if delta != 0 else 0

        result = EchoResult(
            echo_value=round(echo_value, 4),
            source_location=source_loc.name,
            source_location_id=source_loc.location_id,
            perturbation_delta=delta,
            time_steps=T,
            butterfly_coefficient=round(butterfly_coeff, 4),
            system_stability=stability,
            top_affected_locations=top_affected,
            propagation_path=propagation_path
        )

        logger.info(
            "echo_computed",
            source=source_loc.name,
            echo=echo_value,
            stability=stability.value
        )

        return result

    def compute_echo_by_location_id(
        self,
        location_id: str,
        T: Optional[int] = None,
        delta: Optional[float] = None
    ) -> EchoResult:
        """
        Compute echo for a location specified by ID.

        Args:
            location_id: Location ID string
            T: Time steps
            delta: Perturbation

        Returns:
            EchoResult
        """
        if location_id not in self._location_idx_map:
            raise ValueError(f"Location ID not found: {location_id}")

        idx = self._location_idx_map[location_id]
        return self.compute_echo(idx, T, delta)

    def run_monte_carlo(
        self,
        n_trials: Optional[int] = None,
        T: Optional[int] = None,
        parallel: bool = True
    ) -> MonteCarloResult:
        """
        Monte Carlo simulation: random locations, random perturbations.
        Builds a "sensitivity map" of the entire system.

        Args:
            n_trials: Number of trials (default from config)
            T: Time steps per trial
            parallel: Use parallel execution

        Returns:
            MonteCarloResult with aggregated statistics
        """
        n_trials = n_trials or self.config.default_mc_trials
        T = T or self.config.default_time_steps

        logger.info("monte_carlo_starting", n_trials=n_trials, T=T)

        echo_values = []
        location_echoes: Dict[str, List[float]] = {}

        def run_single_trial(trial_idx: int) -> Tuple[float, str]:
            # Random location
            idx = np.random.randint(0, self.n)
            # Random perturbation (-1 to 1)
            delta = np.random.uniform(-1.0, 1.0)

            result = self.compute_echo(idx, T, delta)
            return result.echo_value, result.source_location_id

        if parallel and n_trials > 10:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(run_single_trial, i) for i in range(n_trials)]
                for future in as_completed(futures):
                    echo_val, loc_id = future.result()
                    echo_values.append(echo_val)
                    if loc_id not in location_echoes:
                        location_echoes[loc_id] = []
                    location_echoes[loc_id].append(echo_val)
        else:
            for i in range(n_trials):
                echo_val, loc_id = run_single_trial(i)
                echo_values.append(echo_val)
                if loc_id not in location_echoes:
                    location_echoes[loc_id] = []
                location_echoes[loc_id].append(echo_val)

        # Aggregate statistics
        echo_arr = np.array(echo_values)
        mean_echo = float(np.mean(echo_arr))
        std_echo = float(np.std(echo_arr))

        # Chaos index: mean / std (higher = more predictable chaos patterns)
        chaos_index = mean_echo / std_echo if std_echo > 0 else 0

        # Identify critical locations
        critical_locations = []
        for loc_id, echoes in location_echoes.items():
            loc_idx = self._location_idx_map[loc_id]
            loc = self.locations[loc_idx]
            mean_loc_echo = float(np.mean(echoes))
            critical_locations.append({
                "location_id": loc_id,
                "name": loc.name,
                "city": loc.city,
                "chain_id": loc.chain_id,
                "mean_echo": round(mean_loc_echo, 4),
                "n_samples": len(echoes),
                "criticality": "HIGH" if mean_loc_echo > 3.0 else "MEDIUM" if mean_loc_echo > 1.5 else "LOW"
            })

        critical_locations.sort(key=lambda x: x["mean_echo"], reverse=True)

        # Stability distribution
        n_stable = sum(1 for e in echo_values if e < self.config.chaos_threshold_low)
        n_unstable = sum(1 for e in echo_values if self.config.chaos_threshold_low <= e < self.config.chaos_threshold_high)
        n_chaotic = sum(1 for e in echo_values if e >= self.config.chaos_threshold_high)

        stability_dist = {
            "stable": round(n_stable / n_trials, 4),
            "unstable": round(n_unstable / n_trials, 4),
            "chaotic": round(n_chaotic / n_trials, 4)
        }

        result = MonteCarloResult(
            n_trials=n_trials,
            mean_echo=round(mean_echo, 4),
            std_echo=round(std_echo, 4),
            max_echo=round(float(np.max(echo_arr)), 4),
            min_echo=round(float(np.min(echo_arr)), 4),
            system_chaos_index=round(chaos_index, 4),
            percentile_95=round(float(np.percentile(echo_arr, 95)), 4),
            percentile_99=round(float(np.percentile(echo_arr, 99)), 4),
            critical_locations=critical_locations[:20],  # Top 20
            stability_distribution=stability_dist
        )

        logger.info(
            "monte_carlo_complete",
            n_trials=n_trials,
            mean_echo=mean_echo,
            chaos_index=chaos_index
        )

        return result

    def generate_trading_signal(
        self,
        brand: Optional[str] = None,
        n_trials: int = 300
    ) -> TradingSignal:
        """
        Generate a trading signal based on Echo Engine analysis.

        Args:
            brand: Brand/chain to analyze (if None, analyzes entire system)
            n_trials: Monte Carlo trials

        Returns:
            TradingSignal with recommendation
        """
        logger.info("generating_trading_signal", brand=brand or "ALL")

        # If brand specified, filter locations
        if brand:
            brand_indices = []
            for chain_id, indices in self._chain_locations.items():
                # Match by chain_id or approximate name match
                if brand.lower() in chain_id.lower():
                    brand_indices.extend(indices)

            if not brand_indices:
                logger.warning("brand_not_found", brand=brand)
                return TradingSignal(
                    brand=brand,
                    signal=SignalType.HOLD,
                    confidence=0.0,
                    chaos_index=0.0,
                    echo_mean=0.0,
                    echo_std=0.0,
                    critical_locations=[],
                    recommendation=f"Brand '{brand}' not found in dataset",
                    risk_level="UNKNOWN"
                )

        # Run Monte Carlo
        mc_result = self.run_monte_carlo(n_trials=n_trials)
        chaos_index = mc_result.system_chaos_index

        # Generate signal based on MEAN ECHO and STABILITY DISTRIBUTION
        # Mean echo determines propagation strength
        # Stability distribution shows how often system enters chaotic state
        mean_echo = mc_result.mean_echo
        chaotic_pct = mc_result.stability_distribution.get("chaotic", 0)
        unstable_pct = mc_result.stability_distribution.get("unstable", 0)

        # Risk score based on mean echo and chaotic percentage
        risk_score = mean_echo * (1 + chaotic_pct + 0.5 * unstable_pct)

        if risk_score > 4.0 or chaotic_pct > 0.3:
            signal = SignalType.SELL
            confidence = min(0.9, 0.5 + risk_score / 10.0)
            risk_level = "HIGH"
            recommendation = f"System {'for ' + brand if brand else ''} shows HIGH cascade risk - {chaotic_pct*100:.0f}% chaotic states!"
        elif risk_score < 2.0 and chaotic_pct < 0.1:
            signal = SignalType.BUY
            confidence = min(0.9, 0.7 + (2 - risk_score) * 0.1)
            risk_level = "LOW"
            recommendation = f"System {'for ' + brand if brand else ''} is STABLE - perturbations absorbed locally"
        else:
            signal = SignalType.HOLD
            confidence = 0.5 + min(0.2, (3 - abs(risk_score - 3)) * 0.1)
            risk_level = "MEDIUM"
            recommendation = f"System {'for ' + brand if brand else ''} shows moderate sensitivity - monitor key locations"

        return TradingSignal(
            brand=brand or "ALL_BRANDS",
            signal=signal,
            confidence=round(confidence, 2),
            chaos_index=mc_result.system_chaos_index,
            echo_mean=mc_result.mean_echo,
            echo_std=mc_result.std_echo,
            critical_locations=mc_result.critical_locations[:5],
            recommendation=recommendation,
            risk_level=risk_level
        )

    def get_location_criticality(self, location_id: str, n_samples: int = 50) -> Dict:
        """
        Analyze how critical a specific location is to system stability.

        Args:
            location_id: Location to analyze
            n_samples: Number of perturbation samples

        Returns:
            Criticality analysis dict
        """
        if location_id not in self._location_idx_map:
            raise ValueError(f"Location ID not found: {location_id}")

        idx = self._location_idx_map[location_id]
        loc = self.locations[idx]

        echoes = []
        for _ in range(n_samples):
            delta = np.random.uniform(-1.0, 1.0)
            result = self.compute_echo(idx, delta=delta)
            echoes.append(result.echo_value)

        mean_echo = float(np.mean(echoes))
        max_echo = float(np.max(echoes))

        # Determine criticality
        if mean_echo > 3.0:
            criticality = "CRITICAL"
        elif mean_echo > 2.0:
            criticality = "HIGH"
        elif mean_echo > 1.0:
            criticality = "MEDIUM"
        else:
            criticality = "LOW"

        return {
            "location_id": location_id,
            "name": loc.name,
            "city": loc.city,
            "chain_id": loc.chain_id,
            "mean_echo": round(mean_echo, 4),
            "max_echo": round(max_echo, 4),
            "std_echo": round(float(np.std(echoes)), 4),
            "criticality": criticality,
            "n_samples": n_samples,
            "recommendation": (
                "Monitor closely - changes here propagate widely" if criticality in ["CRITICAL", "HIGH"]
                else "Standard monitoring sufficient"
            )
        }

    def get_system_health(self) -> Dict:
        """
        Get overall system health metrics.

        Returns:
            Health metrics dict
        """
        # Quick Monte Carlo with fewer trials
        mc_result = self.run_monte_carlo(n_trials=100, parallel=False)

        # Health based on mean echo and stability distribution
        mean_echo = mc_result.mean_echo
        chaotic_pct = mc_result.stability_distribution.get("chaotic", 0)
        stable_pct = mc_result.stability_distribution.get("stable", 0)

        # Calculate risk score
        risk_score = mean_echo * (1 + chaotic_pct + 0.5 * (1 - stable_pct))

        return {
            "n_locations": self.n,
            "n_chains": len(self._chain_locations),
            "n_cities": len(self._city_locations),
            "chaos_index": mc_result.system_chaos_index,
            "risk_score": round(risk_score, 4),
            "stability_distribution": mc_result.stability_distribution,
            "mean_echo": mc_result.mean_echo,
            "top_critical_locations": mc_result.critical_locations[:3],
            "overall_status": (
                "HEALTHY" if risk_score < 2.0 and chaotic_pct < 0.1
                else "CAUTION" if risk_score < 3.5 and chaotic_pct < 0.3
                else "AT_RISK"
            ),
            "checked_at": datetime.utcnow().isoformat()
        }


# ═══════════════════════════════════════════════════════════════════
# FACTORY FUNCTION - Integration with Database
# ═══════════════════════════════════════════════════════════════════

def create_echo_engine_from_db(
    db_manager: Any = None,
    chain_filter: Optional[str] = None,
    city_filter: Optional[str] = None,
    config: Optional[EchoEngineConfig] = None,
    database_url: Optional[str] = None
) -> EchoEngine:
    """
    Factory function to create EchoEngine from database.
    Uses direct SQL to work with actual database schema.

    Args:
        db_manager: DatabaseManager instance (optional, can use database_url)
        chain_filter: Optional chain ID to filter locations
        city_filter: Optional city name to filter locations
        config: EchoEngineConfig
        database_url: Direct database URL (alternative to db_manager)

    Returns:
        Initialized EchoEngine
    """
    from sqlalchemy import create_engine, text

    # Get database connection
    if database_url:
        engine = create_engine(database_url)
    elif db_manager:
        engine = db_manager.engine
    else:
        # Default database URL
        db_pass = os.getenv('DB_PASS')
        engine = create_engine(f'postgresql://reviewsignal:{db_pass}@localhost:5432/reviewsignal')

    # Build SQL query for actual database schema
    sql = """
        SELECT
            id,
            name,
            COALESCE(latitude, 0) as latitude,
            COALESCE(longitude, 0) as longitude,
            chain_id,
            COALESCE(city, '') as city,
            chain_name as category,
            COALESCE(rating, 3.0) as rating,
            COALESCE(review_count, 0) as review_count
        FROM locations
        WHERE 1=1
    """

    params = {}

    if chain_filter:
        sql += " AND chain_id = :chain_filter"
        params['chain_filter'] = chain_filter

    if city_filter:
        sql += " AND city = :city_filter"
        params['city_filter'] = city_filter

    sql += " ORDER BY id"

    # Execute query
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        rows = result.fetchall()

    # Convert to LocationState (handle Decimal types from database)
    from decimal import Decimal

    location_states = []
    for row in rows:
        loc_id, name, lat, lon, chain_id, city, category, rating, review_count = row

        # Convert Decimal to float safely
        lat_float = float(lat) if lat is not None else 0.0
        lon_float = float(lon) if lon is not None else 0.0
        rating_float = float(rating) if rating is not None else 3.0

        # Calculate sentiment from rating (1-5 → -1 to 1)
        sentiment = normalize_sentiment(rating_float)

        state = LocationState(
            location_id=f"loc_{loc_id}",
            name=name or f"Location {loc_id}",
            latitude=lat_float,
            longitude=lon_float,
            chain_id=chain_id,
            city=city or "",
            category=category,
            current_sentiment=sentiment,
            current_rating=rating_float,
            review_count=int(review_count) if review_count else 0
        )
        location_states.append(state)

    logger.info(
        "echo_engine_created_from_db",
        n_locations=len(location_states),
        chain_filter=chain_filter,
        city_filter=city_filter
    )

    if not location_states:
        logger.warning("no_locations_found", chain_filter=chain_filter, city_filter=city_filter)
        # Return empty engine
        return EchoEngine([], config)

    return EchoEngine(location_states, config)


# ═══════════════════════════════════════════════════════════════════
# CLI / MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  ECHO ENGINE - Quantum-Inspired Sentiment Propagation")
    print("  ReviewSignal 5.0.7 - Neural Hub Module")
    print("="*70)

    # Create sample locations for testing
    np.random.seed(42)

    # Generate 100 sample locations (5 chains x 4 cities x 5 locations)
    chains = ["starbucks", "mcdonalds", "kfc", "subway", "chipotle"]
    cities = ["New York, NY, USA", "Los Angeles, CA, USA", "Chicago, IL, USA", "Houston, TX, USA"]
    categories = ["coffee", "fast_food", "fast_food", "sandwich", "mexican"]

    # NYC coordinates: 40.7128, -74.0060
    # LA coordinates: 34.0522, -118.2437
    # Chicago: 41.8781, -87.6298
    # Houston: 29.7604, -95.3698
    city_coords = {
        "New York, NY, USA": (40.7128, -74.0060),
        "Los Angeles, CA, USA": (34.0522, -118.2437),
        "Chicago, IL, USA": (41.8781, -87.6298),
        "Houston, TX, USA": (29.7604, -95.3698)
    }

    sample_locations = []
    loc_id = 0
    for chain_idx, chain in enumerate(chains):
        for city in cities:
            base_lat, base_lon = city_coords[city]
            for i in range(5):
                # Add small random offset for each location
                lat = base_lat + np.random.uniform(-0.1, 0.1)
                lon = base_lon + np.random.uniform(-0.1, 0.1)
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
                sample_locations.append(state)
                loc_id += 1

    print(f"\n  Created {len(sample_locations)} sample locations")
    print(f"  Chains: {len(chains)}")
    print(f"  Cities: {len(cities)}")

    # Initialize Echo Engine
    engine = EchoEngine(sample_locations)

    # Test 1: Single echo computation
    print("\n" + "-"*70)
    print("  TEST 1: Single Echo Computation")
    print("-"*70)

    echo_result = engine.compute_echo(location_idx=0)
    print(f"  Source: {echo_result.source_location}")
    print(f"  Echo Value: {echo_result.echo_value}")
    print(f"  Butterfly Coefficient: {echo_result.butterfly_coefficient}")
    print(f"  System Stability: {echo_result.system_stability.value}")
    print(f"  Top Affected:")
    for affected in echo_result.top_affected_locations[:3]:
        print(f"    - {affected['name']}: impact={affected['impact']:.4f}")

    # Test 2: Monte Carlo
    print("\n" + "-"*70)
    print("  TEST 2: Monte Carlo Simulation (100 trials)")
    print("-"*70)

    mc_result = engine.run_monte_carlo(n_trials=100, parallel=False)
    print(f"  Mean Echo: {mc_result.mean_echo}")
    print(f"  Std Echo: {mc_result.std_echo}")
    print(f"  Chaos Index: {mc_result.system_chaos_index}")
    print(f"  95th Percentile: {mc_result.percentile_95}")
    print(f"  Stability Distribution:")
    for status, pct in mc_result.stability_distribution.items():
        print(f"    - {status}: {pct*100:.1f}%")
    print(f"  Top Critical Locations:")
    for loc in mc_result.critical_locations[:3]:
        print(f"    - {loc['name']}: mean_echo={loc['mean_echo']}, criticality={loc['criticality']}")

    # Test 3: Trading Signal
    print("\n" + "-"*70)
    print("  TEST 3: Trading Signal Generation")
    print("-"*70)

    signal = engine.generate_trading_signal(brand="starbucks", n_trials=100)
    print(f"  Brand: {signal.brand}")
    print(f"  Signal: {signal.signal.value.upper()}")
    print(f"  Confidence: {signal.confidence}")
    print(f"  Risk Level: {signal.risk_level}")
    print(f"  Recommendation: {signal.recommendation}")

    # Test 4: System Health
    print("\n" + "-"*70)
    print("  TEST 4: System Health Check")
    print("-"*70)

    health = engine.get_system_health()
    print(f"  Overall Status: {health['overall_status']}")
    print(f"  Chaos Index: {health['chaos_index']}")
    print(f"  Locations: {health['n_locations']}")
    print(f"  Chains: {health['n_chains']}")
    print(f"  Cities: {health['n_cities']}")

    print("\n" + "="*70)
    print("  ECHO ENGINE TEST COMPLETE")
    print("="*70)
