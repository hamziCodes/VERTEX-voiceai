"""Wavia tracing: W3C-correlated spans, bounded buffering and OTLP/HTTP export.

Spans are always recorded in a bounded in-process buffer (useful for tests and
for the latency tooling). Export is opt-in: set ``OTEL_EXPORTER_ENABLED=true`` and
``OTEL_EXPORTER_OTLP_ENDPOINT`` (OTLP/HTTP, e.g. ``http://otel-collector:4318``); then
the service calls :func:`configure_tracing` at startup. Export uses the OTLP
JSON encoding over HTTP so no extra dependency is needed.

Privacy rules: attribute keys that carry conversation content, credentials or
personal identifiers are dropped; remaining string values pass through the
shared redactor and are truncated. Exceptions record only their type.
"""

from __future__ import annotations

import os
import queue
import re
import secrets
import threading
import time
from collections import deque
from collections.abc import Generator, Iterable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

import httpx

from core.compliance.redaction import redact_text
from core.observability.context import ObservabilityContext

MAX_ATTRIBUTE_LENGTH = 256
DEFAULT_MAX_FINISHED_SPANS = 2048
DEFAULT_EXPORT_QUEUE = 4096
DEFAULT_BATCH_SIZE = 256

DROPPED_ATTRIBUTE_KEYS = frozenset(
    {
        "transcript",
        "text",
        "utterance",
        "prompt",
        "system_prompt",
        "greeting",
        "content",
        "message",
        "messages",
        "body",
        "payload",
        "response_body",
        "request_body",
        "caller",
        "callee",
        "from",
        "to",
        "phone",
        "phone_number",
        "email",
        "name",
        "address",
        "authorization",
        "token",
        "api_key",
        "secret",
        "password",
        "cookie",
    }
)

_TRACEPARENT = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")


@dataclass(frozen=True)
class SpanContext:
    trace_id: str
    span_id: str
    sampled: bool = True


def parse_traceparent(header: str | None) -> SpanContext | None:
    """Parse a W3C ``traceparent`` header; invalid or all-zero IDs return None."""
    if not header:
        return None
    match = _TRACEPARENT.match(header.strip().lower())
    if match is None:
        return None
    trace_id, span_id, flags = match.groups()
    if trace_id == "0" * 32 or span_id == "0" * 16:
        return None
    return SpanContext(
        trace_id=trace_id, span_id=span_id, sampled=bool(int(flags, 16) & 1)
    )


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, bool | int | float):
        return value
    text = redact_text(str(value))
    if len(text) > MAX_ATTRIBUTE_LENGTH:
        text = text[: MAX_ATTRIBUTE_LENGTH - 1] + "~"
    return text


def sanitize_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in (attributes or {}).items():
        leaf = str(key).rsplit(".", 1)[-1].lower()
        if leaf in DROPPED_ATTRIBUTE_KEYS or str(key).lower() in DROPPED_ATTRIBUTE_KEYS:
            continue
        if value is None:
            continue
        clean[str(key)] = _sanitize_value(value)
    return clean


class Span:
    """A recorded unit of work."""

    def __init__(
        self,
        name: str,
        *,
        trace_id: str,
        parent_span_id: str | None,
        attributes: Mapping[str, Any] | None = None,
        kind: str = "internal",
    ) -> None:
        self.name = name
        self.trace_id = trace_id
        self.span_id = secrets.token_hex(8)
        self.parent_span_id = parent_span_id
        self.kind = kind
        self.attributes: dict[str, Any] = sanitize_attributes(attributes)
        self.start_time: float = time.time()
        self.start_unix_nano = time.time_ns()
        self.end_time: float | None = None
        self.end_unix_nano: int | None = None
        self.status: str = "OK"

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes.update(sanitize_attributes({key: value}))

    def record_exception(self, exc: BaseException) -> None:
        self.status = "ERROR"
        self.attributes["error.type"] = type(exc).__name__

    def finish(self) -> None:
        if self.end_unix_nano is None:
            self.end_time = time.time()
            self.end_unix_nano = time.time_ns()

    def traceparent(self) -> str:
        return f"00-{self.trace_id}-{self.span_id}-01"

    @property
    def context(self) -> SpanContext:
        return SpanContext(self.trace_id, self.span_id)


_current_span: ContextVar[Span | None] = ContextVar("wavia_current_span", default=None)


def current_span() -> Span | None:
    return _current_span.get()


def _attr_value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    return {"stringValue": str(value)}


_KIND = {"internal": 1, "server": 2, "client": 3, "producer": 4, "consumer": 5}


class OtlpHttpSpanExporter:
    """Send spans to an OTLP/HTTP collector using the JSON encoding."""

    def __init__(
        self,
        *,
        endpoint: str,
        service_name: str,
        headers: Mapping[str, str] | None = None,
        timeout_s: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        base = endpoint.rstrip("/")
        self.url = base if base.endswith("/v1/traces") else f"{base}/v1/traces"
        self.service_name = service_name
        self._headers = {"Content-Type": "application/json", **(headers or {})}
        self._client = httpx.Client(timeout=timeout_s, transport=transport)
        self.exported_spans = 0
        self.failed_batches = 0

    def _encode(self, spans: Iterable[Span]) -> dict[str, Any]:
        encoded = []
        for span in spans:
            item: dict[str, Any] = {
                "traceId": span.trace_id,
                "spanId": span.span_id,
                "name": span.name,
                "kind": _KIND.get(span.kind, 1),
                "startTimeUnixNano": str(span.start_unix_nano),
                "endTimeUnixNano": str(span.end_unix_nano or span.start_unix_nano),
                "attributes": [
                    {"key": k, "value": _attr_value(v)}
                    for k, v in span.attributes.items()
                ],
                "status": {"code": 2 if span.status == "ERROR" else 1},
            }
            if span.parent_span_id:
                item["parentSpanId"] = span.parent_span_id
            encoded.append(item)
        return {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {
                                "key": "service.name",
                                "value": {"stringValue": self.service_name},
                            },
                            {
                                "key": "service.namespace",
                                "value": {"stringValue": "wavia"},
                            },
                        ]
                    },
                    "scopeSpans": [{"scope": {"name": "wavia"}, "spans": encoded}],
                }
            ]
        }

    def export(self, spans: list[Span]) -> bool:
        if not spans:
            return True
        try:
            response = self._client.post(
                self.url, json=self._encode(spans), headers=self._headers
            )
        except httpx.HTTPError:
            self.failed_batches += 1
            return False
        if response.status_code >= 300:
            self.failed_batches += 1
            return False
        self.exported_spans += len(spans)
        return True

    def close(self) -> None:
        self._client.close()


class _BatchProcessor:
    """Background thread that batches finished spans to an exporter."""

    def __init__(
        self,
        exporter: OtlpHttpSpanExporter,
        *,
        flush_interval_s: float,
        max_queue: int = DEFAULT_EXPORT_QUEUE,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self.exporter = exporter
        self.flush_interval_s = flush_interval_s
        self.batch_size = batch_size
        self.dropped_spans = 0
        self._queue: queue.Queue[Span] = queue.Queue(maxsize=max_queue)
        self._flush_requested = threading.Event()
        self._flushed = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="wavia-span-export", daemon=True
        )
        self._thread.start()

    def on_end(self, span: Span) -> None:
        try:
            self._queue.put_nowait(span)
        except queue.Full:
            self.dropped_spans += 1

    def _drain(self) -> None:
        while True:
            batch: list[Span] = []
            while len(batch) < self.batch_size:
                try:
                    batch.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            if not batch:
                return
            self.exporter.export(batch)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._flush_requested.wait(self.flush_interval_s)
            self._flush_requested.clear()
            self._drain()
            self._flushed.set()
        self._drain()
        self._flushed.set()

    def force_flush(self, timeout_s: float = 5.0) -> None:
        self._flushed.clear()
        self._flush_requested.set()
        self._flushed.wait(timeout_s)

    def shutdown(self, timeout_s: float = 5.0) -> None:
        self._stop.set()
        self._flush_requested.set()
        self._thread.join(timeout_s)
        self.exporter.close()


class Tracer:
    """Create spans, keep a bounded tail of finished spans, optionally export."""

    def __init__(
        self,
        name: str = "wavia",
        *,
        max_finished_spans: int = DEFAULT_MAX_FINISHED_SPANS,
    ) -> None:
        self.name = name
        self._finished: deque[Span] = deque(maxlen=max_finished_spans)
        self._lock = threading.Lock()
        self._processor: _BatchProcessor | None = None

    @property
    def export_enabled(self) -> bool:
        return self._processor is not None

    @property
    def active_spans(self) -> list[Span]:
        """Compatibility alias for the bounded finished-span buffer."""
        return self.finished_spans()

    def finished_spans(self) -> list[Span]:
        with self._lock:
            return list(self._finished)

    def configure_export(
        self, exporter: OtlpHttpSpanExporter, *, flush_interval_s: float = 2.0
    ) -> None:
        self.shutdown()
        self._processor = _BatchProcessor(exporter, flush_interval_s=flush_interval_s)

    def force_flush(self) -> None:
        if self._processor is not None:
            self._processor.force_flush()

    def shutdown(self) -> None:
        processor, self._processor = self._processor, None
        if processor is not None:
            processor.shutdown()

    @contextmanager
    def start_span(
        self,
        name: str,
        attributes: Mapping[str, Any] | None = None,
        *,
        parent: SpanContext | None = None,
        kind: str = "internal",
    ) -> Generator[Span, None, None]:
        active = _current_span.get()
        if parent is not None:
            trace_id, parent_id = parent.trace_id, parent.span_id
        elif active is not None:
            trace_id, parent_id = active.trace_id, active.span_id
        else:
            trace_id, parent_id = secrets.token_hex(16), None
        span = Span(
            name,
            trace_id=trace_id,
            parent_span_id=parent_id,
            attributes=attributes,
            kind=kind,
        )
        token = _current_span.set(span)
        previous_ctx = ObservabilityContext.get()
        ObservabilityContext.bind(trace_id=span.trace_id, span_id=span.span_id)
        try:
            yield span
        except BaseException as exc:
            span.record_exception(exc)
            raise
        finally:
            span.finish()
            _current_span.reset(token)
            ObservabilityContext.clear()
            if previous_ctx:
                ObservabilityContext.bind(**previous_ctx)
            with self._lock:
                self._finished.append(span)
            if self._processor is not None:
                self._processor.on_end(span)


_tracer = Tracer()


def get_tracer(name: str = "wavia") -> Tracer:
    return _tracer


def configure_tracing(service_name: str, *, tracer: Tracer | None = None) -> bool:
    """Enable OTLP/HTTP export when ``OTEL_EXPORTER_ENABLED=true`` and endpoint set."""
    target = tracer or _tracer
    enabled = os.getenv("OTEL_EXPORTER_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not enabled or not endpoint:
        return False
    target.configure_export(
        OtlpHttpSpanExporter(
            endpoint=endpoint,
            service_name=os.getenv("OTEL_SERVICE_NAME", service_name),
        ),
        flush_interval_s=float(os.getenv("OTEL_BSP_SCHEDULE_DELAY_S", "2.0")),
    )
    return True


def start_span(
    name: str,
    attributes: Mapping[str, Any] | None = None,
    *,
    parent: SpanContext | None = None,
    kind: str = "internal",
) -> Any:
    return _tracer.start_span(name, attributes, parent=parent, kind=kind)
