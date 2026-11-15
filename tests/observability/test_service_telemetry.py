"""Phase 14: services export real request, voice and loop telemetry."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from core.latency.collector import LatencyCollector
from core.latency.waterfall import LatencyWaterfall
from core.observability import context as obs_context
from core.observability.http import EventLoopLagMonitor
from core.observability.logging import StructuredJSONFormatter
from core.observability.metrics import (
    get_metrics_registry,
    ucve_provider_failover_total,
    ucve_turn_latency_ms,
    ucve_turn_stage_ms,
)
from core.providers.failover import FailoverRouter

BEARER = "test-metrics-bearer"


@pytest.fixture
def metrics_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_METRICS_BEARER", BEARER)
    # Offline: the telephony gateway only opens a database when one is configured.
    monkeypatch.delenv("DATABASE_URL", raising=False)


def _scrape(client: TestClient) -> str:
    response = client.get("/metrics", headers={"Authorization": f"Bearer {BEARER}"})
    assert response.status_code == 200
    return response.text


@pytest.mark.parametrize(
    ("module", "service"),
    [
        ("control_plane.app", "control-plane"),
        ("worker_raw.main", "worker-raw"),
        ("worker_managed.main", "worker-managed"),
        ("telephony_gateway.main", "telephony-gateway"),
    ],
)
def test_every_service_exposes_bearer_protected_metrics(
    module: str, service: str, metrics_env: None
) -> None:
    app = __import__(module, fromlist=["app"]).app
    with TestClient(app) as client:
        assert client.get("/metrics").status_code == 401
        client.get("/health")
        text = _scrape(client)
    assert (
        f'ucve_http_requests_total{{service="{service}",method="GET",route="/health",status_class="2xx"}}'
        in text
    )


def test_metrics_fail_closed_without_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UCVE_METRICS_BEARER", raising=False)
    from worker_raw.main import app

    with TestClient(app) as client:
        assert client.get("/metrics").status_code == 503


def test_request_metrics_use_route_templates_not_raw_ids(metrics_env: None) -> None:
    from control_plane.app import app

    raw_id = str(uuid.uuid4())
    with TestClient(app) as client:
        client.get(f"/v1/agents/{raw_id}")
        client.get(f"/no-such-path/{raw_id}")
        text = _scrape(client)
    assert raw_id not in text
    assert 'route="/v1/agents/{agent_id}"' in text
    assert 'route="unmatched"' in text


def test_server_span_continues_incoming_traceparent(metrics_env: None) -> None:
    from control_plane.app import app

    incoming = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    with TestClient(app) as client:
        response = client.get("/health", headers={"traceparent": incoming})
    assert response.headers["traceparent"].startswith(
        "00-4bf92f3577b34da6a3ce929d0e0e4736-"
    )


def test_completed_turn_records_latency_and_stage_histograms() -> None:
    before_e2e = ucve_turn_latency_ms.labels(
        measurement_quality="server_ack_upper_bound"
    ).count
    before_stage = ucve_turn_stage_ms.labels(stage="stt_after_vad").count
    waterfall = LatencyWaterfall(
        session_id=uuid.uuid4(), acoustic_end_ms=1000.0, vad_end_of_speech_ms=1200.0
    )
    waterfall.stt_final_ms = 1350.0
    waterfall.playback_ack_received_ms = 1800.0
    waterfall.measurement_quality = "server_ack_upper_bound"
    collector = LatencyCollector()
    collector.record_turn(waterfall)
    collector.record_turn(waterfall)  # idempotent per turn
    assert (
        ucve_turn_latency_ms.labels(measurement_quality="server_ack_upper_bound").count
        == before_e2e + 1
    )
    assert ucve_turn_stage_ms.labels(stage="stt_after_vad").count == before_stage + 1


@pytest.mark.asyncio
async def test_provider_failover_is_counted_by_category() -> None:
    router = FailoverRouter(priority=["primary", "secondary"])
    before = ucve_provider_failover_total.labels(category="llm").value

    async def invoke(route: str) -> str:
        if route == "primary":
            raise RuntimeError("down")
        return "ok"

    assert await router.call_with_failover("llm", "en", invoke) == "ok"
    assert ucve_provider_failover_total.labels(category="llm").value == before + 1


@pytest.mark.asyncio
async def test_event_loop_lag_monitor_samples_blocking() -> None:
    monitor = EventLoopLagMonitor("test-service", interval_s=0.01)
    monitor.start()
    await asyncio.sleep(0.03)
    import time

    time.sleep(0.08)  # deliberately block the loop
    await asyncio.sleep(0.03)
    await monitor.stop()
    assert monitor.samples >= 2
    assert monitor.max_lag_ms >= 40.0
    assert 'ucve_event_loop_lag_ms_bucket{service="test-service"' in (
        get_metrics_registry().export_prometheus_text()
    )


def test_logs_carry_session_turn_and_trace_correlation_without_content() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredJSONFormatter())
    logger = logging.getLogger("wavia.test.correlation")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    obs_context.clear()
    try:
        obs_context.bind(
            session_id="s-1", turn_id="t-1", trace_id="a" * 32, request_id="r-1"
        )
        logger.info("turn finished for caller +44 7700 900123")
    finally:
        obs_context.clear()
        logger.removeHandler(handler)
    record = json.loads(stream.getvalue().strip())
    assert record["session_id"] == "s-1"
    assert record["turn_id"] == "t-1"
    assert record["trace_id"] == "a" * 32
    assert record["request_id"] == "r-1"
    assert "7700 900123" not in record["event"]
