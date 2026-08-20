"""UCVE Control Plane Prometheus /metrics Route Endpoint Handler."""

from __future__ import annotations

from typing import Any

from core.observability.metrics import get_metrics_registry


def handle_metrics_request() -> tuple[int, dict[str, str], str]:
    """HTTP endpoint handler for control-plane /metrics route."""
    registry = get_metrics_registry()
    body = registry.export_prometheus_text()
    headers = {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"}
    return 200, headers, body
