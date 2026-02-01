#!/usr/bin/env python3
"""
Echo Engine Prometheus Metrics
Custom business metrics for Echo Engine API
"""

from prometheus_client import Counter, Histogram, Gauge

# Echo Engine Business Metrics
ECHO_COMPUTATIONS = Counter(
    'echo_computations_total',
    'Total echo computations performed',
    ['location_type']  # chain, city, individual
)

MONTE_CARLO_SIMULATIONS = Counter(
    'monte_carlo_simulations_total',
    'Total Monte Carlo simulations run',
    ['chain_filter']  # specific chain or 'all'
)

TRADING_SIGNALS = Counter(
    'trading_signals_generated_total',
    'Total trading signals generated',
    ['signal_type', 'confidence_level']  # BUY/HOLD/SELL, HIGH/MEDIUM/LOW
)

ENGINE_REBUILD_DURATION = Histogram(
    'engine_rebuild_duration_seconds',
    'Time taken to rebuild Echo Engine from database'
)

ENGINE_CACHE_HITS = Counter(
    'engine_cache_hits_total',
    'Total cache hits for Echo Engine'
)

ENGINE_CACHE_MISSES = Counter(
    'engine_cache_misses_total',
    'Total cache misses for Echo Engine'
)

LOCATION_CRITICALITY_CHECKS = Counter(
    'location_criticality_checks_total',
    'Total location criticality analyses performed'
)

ENGINE_LOCATIONS_GAUGE = Gauge(
    'echo_engine_locations_loaded',
    'Number of locations currently loaded in Echo Engine'
)

ENGINE_CHAINS_GAUGE = Gauge(
    'echo_engine_chains_loaded',
    'Number of chains currently loaded in Echo Engine'
)

COMPUTATION_DURATION = Histogram(
    'echo_computation_duration_seconds',
    'Time taken for echo computations',
    ['operation']  # compute_echo, monte_carlo, trading_signal, criticality
)


# Helper functions
def track_echo_computation(location_type: str = 'individual'):
    """Track echo computation"""
    ECHO_COMPUTATIONS.labels(location_type=location_type).inc()


def track_monte_carlo(chain_filter: str = 'all'):
    """Track Monte Carlo simulation"""
    MONTE_CARLO_SIMULATIONS.labels(chain_filter=chain_filter or 'all').inc()


def track_trading_signal(signal_type: str, confidence: str):
    """Track trading signal generation"""
    TRADING_SIGNALS.labels(signal_type=signal_type, confidence_level=confidence).inc()


def track_engine_rebuild(duration: float):
    """Track engine rebuild duration"""
    ENGINE_REBUILD_DURATION.observe(duration)


def track_cache_hit():
    """Track cache hit"""
    ENGINE_CACHE_HITS.inc()


def track_cache_miss():
    """Track cache miss"""
    ENGINE_CACHE_MISSES.inc()


def track_criticality_check():
    """Track location criticality check"""
    LOCATION_CRITICALITY_CHECKS.inc()


def update_engine_gauges(n_locations: int, n_chains: int):
    """Update engine size gauges"""
    ENGINE_LOCATIONS_GAUGE.set(n_locations)
    ENGINE_CHAINS_GAUGE.set(n_chains)


def track_computation_duration(operation: str, duration: float):
    """Track computation duration"""
    COMPUTATION_DURATION.labels(operation=operation).observe(duration)
