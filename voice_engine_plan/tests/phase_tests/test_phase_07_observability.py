"""Phase 07: Observability Foundations."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def observability_module():
    try:
        from core import observability  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 07 implementation pending: {exc}")
    return observability


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_07_observability_foundations.md"
    )
    assert plan.is_file()


def test_context_binds_call_id(observability_module) -> None:
    ctx = observability_module.context
    ctx.bind(call_id="call-123", tenant_id="tenant-456")
    bound = ctx.get()
    assert bound["call_id"] == "call-123"
    assert bound["tenant_id"] == "tenant-456"
    ctx.clear()


def test_phi_redaction_strips_phone(observability_module) -> None:
    redact = observability_module.logging.redact_phi
    text = "Call me at 555-123-4567 please"
    cleaned = redact(text)
    assert "555-123-4567" not in cleaned


def test_auth_query_params_redacted(observability_module) -> None:
    redact_url = observability_module.logging.redact_url_params
    url = "wss://voice.example.com/ws?token=secret-jwt&session_id=abc"
    cleaned = redact_url(url)
    assert "secret-jwt" not in cleaned
    assert "token=" in cleaned or "[REDACTED]" in cleaned


@pytest.mark.asyncio
async def test_async_context_propagation(observability_module) -> None:
    import asyncio
    ctx = observability_module.context

    async def worker(call_id: str):
        ctx.bind(call_id=call_id)
        await asyncio.sleep(0.01)
        return ctx.get()["call_id"]

    results = await asyncio.gather(
        worker("call-A"),
        worker("call-B"),
    )
    assert results == ["call-A", "call-B"]


def test_metrics_prometheus_export(observability_module) -> None:
    metrics = observability_module.metrics
    reg = metrics.get_metrics_registry()
    counter = reg.counter("test_counter", "Test counter metric")
    counter.inc(5.0)

    output = reg.export_prometheus_text()
    assert "test_counter 5.0" in output


def test_tracing_span_lifecycle(observability_module) -> None:
    tracing = observability_module.tracing
    with tracing.start_span("test_span", {"key": "val"}) as span:
        assert span.name == "test_span"
        assert span.attributes["key"] == "val"
        assert span.end_time is None
    assert span.end_time is not None


def test_metric_event_to_dict(observability_module) -> None:
    MetricEvent = observability_module.events.MetricEvent
    event = MetricEvent(name="ucve_latency", value=123.4, labels={"tier": "prod"})
    payload = event.to_dict()
    assert payload["type"] == "metric"
    assert payload["name"] == "ucve_latency"
    assert payload["value"] == 123.4
    assert payload["labels"] == {"tier": "prod"}

