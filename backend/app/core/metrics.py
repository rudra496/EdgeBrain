"""Prometheus metrics for EdgeBrain.

Exposes system metrics in Prometheus format for monitoring and alerting.
"""
import logging
import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── Counters ─────────────────────────────────────────────

REQUESTS_TOTAL = Counter(
    "edgebrain_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"]
)

MQTT_MESSAGES_TOTAL = Counter(
    "edgebrain_mqtt_messages_total",
    "Total number of MQTT messages processed",
    ["topic"]
)

SENSOR_READINGS_TOTAL = Counter(
    "edgebrain_sensor_readings_total",
    "Total number of sensor readings ingested",
    ["device_type"]
)

ALERTS_TOTAL = Counter(
    "edgebrain_alerts_total",
    "Total number of alerts generated",
    ["severity", "device_type"]
)

# ─── Gauges ───────────────────────────────────────────────

DEVICES_ONLINE = Gauge(
    "edgebrain_devices_online",
    "Number of devices currently online"
)

DEVICES_OFFLINE = Gauge(
    "edgebrain_devices_offline",
    "Number of devices currently offline"
)

ACTIVE_CONNECTIONS = Gauge(
    "edgebrain_active_connections",
    "Number of active connections",
    ["type"]  # websocket, mqtt, etc
)

# ─── Histograms ───────────────────────────────────────────

REQUEST_DURATION = Histogram(
    "edgebrain_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

MQTT_PROCESSING_TIME = Histogram(
    "edgebrain_mqtt_processing_seconds",
    "MQTT message processing time in seconds",
    ["topic"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5]
)


class MetricsMiddleware:
    """FastAPI middleware to collect HTTP metrics."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        start_time = time.time()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Record metrics when response starts
                duration = time.time() - start_time
                endpoint = request.url.path
                method = request.method
                status_code = message["status"]

                REQUESTS_TOTAL.labels(
                    method=method,
                    endpoint=endpoint,
                    status_code=status_code
                ).inc()

                REQUEST_DURATION.labels(
                    method=method,
                    endpoint=endpoint
                ).observe(duration)

            await send(message)

        await self.app(scope, receive, send_wrapper)


def get_metrics() -> bytes:
    """Generate Prometheus metrics output."""
    return generate_latest()


def get_metrics_content_type() -> str:
    """Get Prometheus metrics content type."""
    return CONTENT_TYPE_LATEST
