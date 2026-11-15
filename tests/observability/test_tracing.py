"""Phase 14: real spans with W3C correlation and OTLP/HTTP export."""

from __future__ import annotations

import json

import httpx
import pytest

from core.observability import context as obs_context
from core.observability.tracing import (
    OtlpHttpSpanExporter,
    Tracer,
    parse_traceparent,
)


def test_child_span_shares_trace_and_points_at_parent() -> None:
    tracer = Tracer(max_finished_spans=10)
    with tracer.start_span("turn") as parent:
        with tracer.start_span("llm") as child:
            assert child.trace_id == parent.trace_id
            assert child.parent_span_id == parent.span_id
    assert len(parent.trace_id) == 32 and len(parent.span_id) == 16
    assert [s.name for s in tracer.finished_spans()] == ["llm", "turn"]


def test_finished_span_buffer_is_bounded() -> None:
    tracer = Tracer(max_finished_spans=5)
    for i in range(50):
        with tracer.start_span(f"s{i}"):
            pass
    names = [s.name for s in tracer.finished_spans()]
    assert names == ["s45", "s46", "s47", "s48", "s49"]


def test_identifying_and_content_attributes_are_dropped_or_redacted() -> None:
    tracer = Tracer(max_finished_spans=10)
    with tracer.start_span(
        "stt",
        {
            "transcript": "my card is 4111 1111 1111 1111",
            "caller": "+44 7700 900123",
            "authorization": "Bearer abc",
            "provider": "deepgram",
            "note": "reach me at someone@example.com",
            "session.id": "5f8a0c8e-0000-4000-8000-000000000001",
        },
    ) as span:
        span.set_attribute("prompt", "secret system prompt")
    attrs = tracer.finished_spans()[-1].attributes
    assert "transcript" not in attrs
    assert "caller" not in attrs
    assert "authorization" not in attrs
    assert "prompt" not in attrs
    assert attrs["provider"] == "deepgram"
    assert "someone@example.com" not in attrs["note"]
    assert attrs["session.id"].startswith("5f8a0c8e")


def test_exception_marks_span_error_without_message_text() -> None:
    tracer = Tracer(max_finished_spans=10)
    with pytest.raises(RuntimeError):
        with tracer.start_span("tts"):
            raise RuntimeError("provider said: caller +1 415 555 0100 hung up")
    span = tracer.finished_spans()[-1]
    assert span.status == "ERROR"
    assert span.attributes["error.type"] == "RuntimeError"
    assert "415" not in json.dumps(span.attributes)


def test_span_binds_trace_ids_into_log_context() -> None:
    tracer = Tracer(max_finished_spans=10)
    obs_context.clear()
    with tracer.start_span("turn") as span:
        bound = obs_context.get()
        assert bound["trace_id"] == span.trace_id
        assert bound["span_id"] == span.span_id
    assert "span_id" not in obs_context.get()


def test_traceparent_round_trip_continues_remote_trace() -> None:
    tracer = Tracer(max_finished_spans=10)
    header = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    remote = parse_traceparent(header)
    assert remote is not None
    with tracer.start_span("http", parent=remote) as span:
        assert span.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
        assert span.parent_span_id == "00f067aa0ba902b7"
        assert span.traceparent().startswith("00-4bf92f3577b34da6a3ce929d0e0e4736-")
    assert parse_traceparent("garbage") is None
    assert parse_traceparent("00-" + "0" * 32 + "-" + "1" * 16 + "-01") is None


def test_otlp_exporter_posts_resource_spans_json() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={})

    tracer = Tracer(max_finished_spans=10)
    with tracer.start_span("turn", {"stage": "llm"}):
        pass
    exporter = OtlpHttpSpanExporter(
        endpoint="http://collector:4318",
        service_name="worker-raw",
        transport=httpx.MockTransport(handler),
    )
    assert exporter.export(tracer.finished_spans()) is True
    request = captured[0]
    assert str(request.url) == "http://collector:4318/v1/traces"
    body = json.loads(request.content)
    resource = body["resourceSpans"][0]["resource"]["attributes"]
    assert {"key": "service.name", "value": {"stringValue": "worker-raw"}} in resource
    span = body["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span["name"] == "turn"
    assert len(span["traceId"]) == 32
    assert int(span["endTimeUnixNano"]) >= int(span["startTimeUnixNano"])


def test_otlp_exporter_reports_failure_honestly() -> None:
    exporter = OtlpHttpSpanExporter(
        endpoint="http://collector:4318",
        service_name="x",
        transport=httpx.MockTransport(lambda r: httpx.Response(503)),
    )
    tracer = Tracer(max_finished_spans=10)
    with tracer.start_span("a"):
        pass
    assert exporter.export(tracer.finished_spans()) is False
    assert exporter.failed_batches == 1


def test_tracer_exports_through_processor_when_configured() -> None:
    posted: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        posted.append(json.loads(request.content))
        return httpx.Response(200)

    tracer = Tracer(max_finished_spans=10)
    tracer.configure_export(
        OtlpHttpSpanExporter(
            endpoint="http://collector:4318",
            service_name="control-plane",
            transport=httpx.MockTransport(handler),
        ),
        flush_interval_s=60.0,
    )
    try:
        with tracer.start_span("one"):
            pass
        tracer.force_flush()
    finally:
        tracer.shutdown()
    names = [
        s["name"]
        for batch in posted
        for rs in batch["resourceSpans"]
        for ss in rs["scopeSpans"]
        for s in ss["spans"]
    ]
    assert names == ["one"]


def test_export_requires_explicit_enable_and_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.observability.tracing import configure_tracing

    tracer = Tracer(max_finished_spans=10)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    monkeypatch.setenv("OTEL_EXPORTER_ENABLED", "false")
    assert configure_tracing("svc", tracer=tracer) is False
    monkeypatch.setenv("OTEL_EXPORTER_ENABLED", "true")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    assert configure_tracing("svc", tracer=tracer) is False
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    try:
        assert configure_tracing("svc", tracer=tracer) is True
        assert tracer.export_enabled is True
    finally:
        tracer.shutdown()
    assert tracer.export_enabled is False
