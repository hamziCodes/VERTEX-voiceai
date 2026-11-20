"""Shared HTTP observability for every Wavia FastAPI service.

``install_observability(app, service)`` adds:

- a request middleware that records ``ucve_http_requests_total`` and
  ``ucve_http_request_duration_ms`` keyed by the *route template* (never the
  raw path, so IDs cannot explode cardinality), opens a server span that
  continues an incoming W3C ``traceparent`` and binds ``request_id``/trace IDs
  into the log context;
- ``GET /metrics`` (Prometheus text) protected by ``UCVE_METRICS_BEARER``
  unless the app already defines one;
- an event-loop lag monitor started and stopped with :func:`observability_runtime`.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import os
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from starlette.responses import Response

from core.observability.context import ObservabilityContext
from core.observability.logging import install_log_redaction
from core.observability.metrics import (
    get_metrics_registry,
    ucve_event_loop_lag_ms,
    ucve_http_request_duration_ms,
    ucve_http_requests_total,
)
from core.observability.tracing import configure_tracing, get_tracer, parse_traceparent

UNMATCHED_ROUTE = "unmatched"


def metrics_bearer() -> str:
    return (os.environ.get("UCVE_METRICS_BEARER") or "").strip()


def render_metrics(authorization: str | None) -> PlainTextResponse:
    """Prometheus exposition, fail-closed when no bearer is configured."""
    expected = metrics_bearer()
    if not expected:
        raise HTTPException(
            status_code=503, detail="UCVE_METRICS_BEARER not configured."
        )
    supplied = authorization or ""
    if not hmac.compare_digest(supplied.encode(), f"Bearer {expected}".encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return PlainTextResponse(
        content=get_metrics_registry().export_prometheus_text(),
        headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"},
    )


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return str(path) if path else UNMATCHED_ROUTE


def _status_class(status_code: int) -> str:
    return f"{status_code // 100}xx"


def install_observability(app: FastAPI, service: str) -> None:
    """Attach request metrics, server spans and ``/metrics`` to ``app``."""
    app.state.observability_service = service
    install_log_redaction()
    tracer = get_tracer()

    @app.middleware("http")
    async def _observe_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        parent = parse_traceparent(request.headers.get("traceparent"))
        ObservabilityContext.bind(request_id=request_id, service=service)
        status_code = 500
        with tracer.start_span(
            f"{request.method} http",
            {"http.method": request.method, "service.name": service},
            parent=parent,
            kind="server",
        ) as span:
            try:
                response = await call_next(request)
                status_code = response.status_code
                response.headers.setdefault("traceparent", span.traceparent())
                return response
            finally:
                route = _route_template(request)
                span.name = f"{request.method} {route}"
                span.set_attribute("http.route", route)
                span.set_attribute("http.status_code", status_code)
                if status_code >= 500:
                    span.status = "ERROR"
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                ucve_http_requests_total.labels(
                    service=service,
                    method=request.method,
                    route=route,
                    status_class=_status_class(status_code),
                ).inc()
                ucve_http_request_duration_ms.labels(
                    service=service, method=request.method, route=route
                ).observe(elapsed_ms)

    existing = {getattr(r, "path", None) for r in app.router.routes}
    if "/metrics" not in existing:

        @app.get("/metrics", include_in_schema=False)
        async def _metrics(
            authorization: str | None = Header(None, alias="Authorization"),
        ) -> PlainTextResponse:
            return render_metrics(authorization)


class EventLoopLagMonitor:
    """Sample how late the event loop wakes a sleeping task."""

    def __init__(self, service: str, *, interval_s: float = 0.5) -> None:
        self.service = service
        self.interval_s = interval_s
        self.samples = 0
        self.max_lag_ms = 0.0
        self._task: asyncio.Task[None] | None = None

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        histogram = ucve_event_loop_lag_ms.labels(service=self.service)
        while True:
            expected = loop.time() + self.interval_s
            await asyncio.sleep(self.interval_s)
            lag_ms = max(0.0, (loop.time() - expected) * 1000.0)
            histogram.observe(lag_ms)
            self.samples += 1
            self.max_lag_ms = max(self.max_lag_ms, lag_ms)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(
                self._run(), name=f"event-loop-lag:{self.service}"
            )

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


@contextlib.asynccontextmanager
async def observability_runtime(app: FastAPI, service: str) -> AsyncIterator[None]:
    """Lifespan helper: tracing export and loop-lag monitoring for a service."""
    configure_tracing(service)
    monitor = EventLoopLagMonitor(service)
    app.state.event_loop_monitor = monitor
    monitor.start()
    try:
        yield
    finally:
        await monitor.stop()
        get_tracer().shutdown()
