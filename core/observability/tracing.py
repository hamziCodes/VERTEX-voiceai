"""UCVE OpenTelemetry Trace Manager & In-Process Span Collector."""

from __future__ import annotations

from contextlib import contextmanager
import os
import time
from typing import Any, Generator


class Span:
    """In-process trace span representation."""

    def __init__(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.name = name
        self.attributes = attributes or {}
        self.start_time: float = time.time()
        self.end_time: float | None = None
        self.status: str = "OK"

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def finish(self) -> None:
        self.end_time = time.time()


class Tracer:
    """Tracer manager controlling span creation and in-process accumulation."""

    def __init__(self, name: str = "ucve") -> None:
        self.name = name
        self.exporter_enabled: bool = os.getenv("OTEL_EXPORTER_ENABLED", "false").lower() == "true"
        self.active_spans: list[Span] = []

    @contextmanager
    def start_span(
        self, name: str, attributes: dict[str, Any] | None = None
    ) -> Generator[Span, None, None]:
        span = Span(name, attributes)
        self.active_spans.append(span)
        try:
            yield span
        finally:
            span.finish()


_tracer = Tracer()


def get_tracer(name: str = "ucve") -> Tracer:
    return _tracer


start_span = _tracer.start_span
