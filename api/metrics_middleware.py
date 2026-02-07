"""
Prometheus Metrics Middleware for FastAPI
Exposes /metrics endpoint for Prometheus scraping
"""

from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest,
    CollectorRegistry, CONTENT_TYPE_LATEST
)
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
import psutil
import os

# Create a custom registry
REGISTRY = CollectorRegistry()

# HTTP Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=REGISTRY
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    registry=REGISTRY
)

http_requests_in_progress = Gauge(
    'http_requests_in_progress',
    'HTTP requests currently in progress',
    ['method', 'endpoint'],
    registry=REGISTRY
)

# Lead Metrics
leads_collected_total = Counter(
    'leads_collected_total',
    'Total leads collected',
    ['source'],
    registry=REGISTRY
)

leads_processed_total = Counter(
    'leads_processed_total',
    'Total leads processed successfully',
    registry=REGISTRY
)

leads_failed_total = Counter(
    'leads_failed_total',
    'Total lead processing failures',
    registry=REGISTRY
)

instantly_sync_total = Counter(
    'instantly_sync_total',
    'Total Instantly sync operations',
    ['status'],
    registry=REGISTRY
)

# Database Metrics
database_connections_active = Gauge(
    'database_connections_active',
    'Active database connections',
    registry=REGISTRY
)

database_query_duration_seconds = Histogram(
    'database_query_duration_seconds',
    'Database query duration',
    ['query_type'],
    registry=REGISTRY
)

# System Metrics
system_cpu_usage_percent = Gauge(
    'system_cpu_usage_percent',
    'CPU usage percentage',
    registry=REGISTRY
)

system_memory_usage_percent = Gauge(
    'system_memory_usage_percent',
    'Memory usage percentage',
    registry=REGISTRY
)

system_disk_usage_percent = Gauge(
    'system_disk_usage_percent',
    'Disk usage percentage',
    ['mount'],
    registry=REGISTRY
)

# Application Metrics
app_uptime_seconds = Gauge(
    'app_uptime_seconds',
    'Application uptime in seconds',
    registry=REGISTRY
)

app_info = Gauge(
    'app_info',
    'Application information',
    ['version', 'environment'],
    registry=REGISTRY
)

# Set application info
app_info.labels(version='5.0', environment='production').set(1)

# Track application start time
APP_START_TIME = time.time()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to track HTTP request metrics"""

    async def dispatch(self, request: Request, call_next):
        # Skip metrics endpoint itself
        if request.url.path == '/metrics':
            return await call_next(request)

        # Track request start
        start_time = time.time()
        method = request.method
        endpoint = request.url.path

        # Increment in-progress gauge
        http_requests_in_progress.labels(
            method=method,
            endpoint=endpoint
        ).inc()

        try:
            # Process request
            response = await call_next(request)
            status = response.status_code

            # Record metrics
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=status
            ).inc()

            duration = time.time() - start_time
            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)

            return response

        except Exception as e:
            # Track errors
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=500
            ).inc()
            raise

        finally:
            # Decrement in-progress gauge
            http_requests_in_progress.labels(
                method=method,
                endpoint=endpoint
            ).dec()


def update_system_metrics():
    """Update system resource metrics"""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        system_cpu_usage_percent.set(cpu_percent)

        # Memory usage
        memory = psutil.virtual_memory()
        system_memory_usage_percent.set(memory.percent)

        # Disk usage
        disk = psutil.disk_usage('/')
        system_disk_usage_percent.labels(mount='/').set(disk.percent)

        # Application uptime
        uptime = time.time() - APP_START_TIME
        app_uptime_seconds.set(uptime)

    except Exception as e:
        print(f"Error updating system metrics: {e}")


def metrics_endpoint():
    """Generate Prometheus metrics"""
    # Update system metrics before generating output
    update_system_metrics()

    # Generate metrics in Prometheus format
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST
    )


# Helper functions to track specific events
def track_lead_collected(source: str = 'apollo'):
    """Track a lead collection event"""
    leads_collected_total.labels(source=source).inc()


def track_lead_processed():
    """Track a successful lead processing"""
    leads_processed_total.inc()


def track_lead_failed():
    """Track a failed lead processing"""
    leads_failed_total.inc()


def track_instantly_sync(status: str):
    """Track Instantly sync operation"""
    instantly_sync_total.labels(status=status).inc()


def track_database_query(query_type: str, duration: float):
    """Track database query duration"""
    database_query_duration_seconds.labels(query_type=query_type).observe(duration)


def set_database_connections(count: int):
    """Set the current number of active database connections"""
    database_connections_active.set(count)
