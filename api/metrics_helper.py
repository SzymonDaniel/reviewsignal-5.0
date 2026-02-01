#!/usr/bin/env python3
"""
Prometheus Metrics Helper for FastAPI apps
Simple wrapper to add /metrics endpoint
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
from fastapi.responses import PlainTextResponse
import time

# Define metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

ACTIVE_REQUESTS = Gauge(
    'http_requests_active',
    'Active HTTP requests'
)

# App-specific metrics - Lead Receiver
LEADS_COLLECTED = Counter('leads_collected_total', 'Total leads collected', ['source'])
LEADS_PROCESSED = Counter('leads_processed_total', 'Total leads processed successfully')
LEADS_FAILED = Counter('leads_failed_total', 'Total leads failed')
INSTANTLY_SYNCS = Counter('instantly_syncs_total', 'Total Instantly syncs', ['status'])

DB_CONNECTIONS = Gauge('database_connections_active', 'Active database connections')
DATABASE_QUERY_DURATION = Histogram(
    'database_query_duration_seconds',
    'Database query execution time',
    ['operation']
)


def metrics_endpoint():
    """Generate Prometheus metrics endpoint"""
    return PlainTextResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


def track_request(method: str, endpoint: str, status: int, duration: float):
    """Track HTTP request metrics"""
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
    REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)


def track_lead_collected(source: str = 'apollo'):
    """Track lead collection"""
    LEADS_COLLECTED.labels(source=source).inc()


def track_lead_processed():
    """Track successful lead processing"""
    LEADS_PROCESSED.inc()


def track_lead_failed():
    """Track failed lead processing"""
    LEADS_FAILED.inc()


def track_instantly_sync(success: bool):
    """Track Instantly sync"""
    status = 'success' if success else 'failed'
    INSTANTLY_SYNCS.labels(status=status).inc()


def set_database_connections(count: int):
    """Set active database connection count"""
    DB_CONNECTIONS.set(count)


def track_database_query(operation: str, duration: float):
    """Track database query duration"""
    DATABASE_QUERY_DURATION.labels(operation=operation).observe(duration)
