"""Wavia metrics registry with bounded cardinality and Prometheus exposition.

Design rules (Phase 14):

- Every metric declares its label names up front. Label names that identify a
  tenant, session, call, turn, person or phone number are rejected: those
  belong in logs and spans, never in metric series.
- Each metric holds at most ``max_series_per_metric`` label combinations. Extra
  combinations collapse into a single ``__overflow__`` series and increment
  ``ucve_metrics_series_overflow_total`` so the loss is visible.
- Histograms keep cumulative buckets, so the exposition is a valid Prometheus
  histogram and percentiles can be estimated in-process as well as by the
  scraper (``histogram_quantile``).
"""

from __future__ import annotations

import math
import threading
from collections.abc import Iterable, Sequence
from typing import Any

OVERFLOW_LABEL_VALUE = "__overflow__"
MAX_LABEL_VALUE_LENGTH = 96
DEFAULT_MAX_SERIES = 200

# Milliseconds; covers the sub-second voice budget and multi-second tails.
DEFAULT_LATENCY_BUCKETS_MS: tuple[float, ...] = (
    25.0,
    50.0,
    100.0,
    200.0,
    300.0,
    400.0,
    500.0,
    650.0,
    800.0,
    1000.0,
    1500.0,
    2000.0,
    3000.0,
    5000.0,
    10000.0,
)

FORBIDDEN_LABEL_NAMES = frozenset(
    {
        "tenant",
        "tenant_id",
        "session",
        "session_id",
        "call",
        "call_id",
        "turn",
        "turn_id",
        "user",
        "user_id",
        "actor",
        "actor_id",
        "email",
        "phone",
        "phone_number",
        "caller",
        "from",
        "to",
        "ip",
        "agent_id",
        "request_id",
        "job_id",
        "trace_id",
        "span_id",
    }
)

LabelKey = tuple[str, ...]


def _escape(value: str) -> str:
    if len(value) > MAX_LABEL_VALUE_LENGTH:
        value = value[: MAX_LABEL_VALUE_LENGTH - 1] + "~"
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _fmt(value: float) -> str:
    if math.isinf(value):
        return "+Inf" if value > 0 else "-Inf"
    if math.isnan(value):
        return "NaN"
    return repr(float(value))


def _render_labels(names: Sequence[str], values: Sequence[str], extra: str = "") -> str:
    parts = [f'{n}="{_escape(v)}"' for n, v in zip(names, values, strict=True)]
    if extra:
        parts.append(extra)
    return "{" + ",".join(parts) + "}" if parts else ""


class _Metric:
    kind = "untyped"

    def __init__(
        self,
        registry: MetricsRegistry,
        name: str,
        description: str,
        labelnames: Sequence[str],
    ) -> None:
        for label in labelnames:
            if label.lower() in FORBIDDEN_LABEL_NAMES:
                raise ValueError(
                    f"Label {label!r} on {name} is identifying or unbounded; "
                    "put it in logs or spans instead."
                )
        self._registry = registry
        self.name = name
        self.description = description
        self.labelnames: tuple[str, ...] = tuple(labelnames)
        self._lock = threading.Lock()
        self._series: dict[LabelKey, Any] = {}

    # -- series management -------------------------------------------------
    def _new_child(self) -> Any:  # pragma: no cover - abstract
        raise NotImplementedError

    def _key(self, labels: dict[str, Any]) -> LabelKey:
        if set(labels) != set(self.labelnames):
            raise ValueError(
                f"{self.name} expects labels {self.labelnames}, got {tuple(labels)}"
            )
        return tuple(str(labels[n]) for n in self.labelnames)

    def labels(self, **labels: Any) -> Any:
        if not self.labelnames:
            raise ValueError(f"{self.name} has no labels")
        key = self._key(labels)
        with self._lock:
            child = self._series.get(key)
            if child is not None:
                return child
            if len(self._series) >= self._registry.max_series_per_metric:
                overflow_key = tuple(OVERFLOW_LABEL_VALUE for _ in self.labelnames)
                child = self._series.get(overflow_key)
                if child is None:
                    child = self._new_child()
                    self._series[overflow_key] = child
                self._registry._record_overflow(self.name)
                return child
            child = self._new_child()
            self._series[key] = child
            return child

    def _unlabelled(self) -> Any:
        if self.labelnames:
            raise ValueError(f"{self.name} requires labels {self.labelnames}")
        with self._lock:
            child = self._series.get(())
            if child is None:
                child = self._new_child()
                self._series[()] = child
            return child

    def _snapshot(self) -> list[tuple[LabelKey, Any]]:
        with self._lock:
            return sorted(self._series.items(), key=lambda item: item[0])

    def export_lines(self) -> list[str]:  # pragma: no cover - abstract
        raise NotImplementedError


class _CounterChild:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value = 0.0

    def inc(self, amount: float = 1.0) -> None:
        if amount < 0:
            raise ValueError("Counters only increase.")
        with self._lock:
            self._value += amount

    @property
    def value(self) -> float:
        with self._lock:
            return self._value


class CounterMetric(_Metric):
    kind = "counter"

    def _new_child(self) -> _CounterChild:
        return _CounterChild()

    def inc(self, amount: float = 1.0) -> None:
        self._unlabelled().inc(amount)

    @property
    def value(self) -> float:
        return float(self._unlabelled().value)

    def export_lines(self) -> list[str]:
        return [
            f"{self.name}{_render_labels(self.labelnames, key)} {_fmt(child.value)}"
            for key, child in self._snapshot()
        ]


class _GaugeChild(_CounterChild):
    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value -= amount

    def set(self, value: float) -> None:
        with self._lock:
            self._value = float(value)


class GaugeMetric(CounterMetric):
    kind = "gauge"

    def _new_child(self) -> _GaugeChild:
        return _GaugeChild()

    def dec(self, amount: float = 1.0) -> None:
        self._unlabelled().dec(amount)

    def set(self, value: float) -> None:
        self._unlabelled().set(value)


class _HistogramChild:
    def __init__(self, buckets: tuple[float, ...]) -> None:
        self._lock = threading.Lock()
        self.buckets = buckets
        self._counts = [0] * (len(buckets) + 1)  # last slot is +Inf
        self._sum = 0.0
        self._count = 0

    def observe(self, amount: float) -> None:
        value = float(amount)
        if math.isnan(value):
            return
        with self._lock:
            self._sum += value
            self._count += 1
            for index, bound in enumerate(self.buckets):
                if value <= bound:
                    self._counts[index] += 1
                    return
            self._counts[-1] += 1

    @property
    def count(self) -> int:
        with self._lock:
            return self._count

    @property
    def sum(self) -> float:
        with self._lock:
            return self._sum

    def cumulative(self) -> tuple[list[int], float, int]:
        with self._lock:
            running = 0
            cumulative: list[int] = []
            for c in self._counts:
                running += c
                cumulative.append(running)
            return cumulative, self._sum, self._count

    def quantile(self, q: float) -> float | None:
        """Estimate a quantile by linear interpolation inside its bucket.

        Values in the ``+Inf`` bucket are reported as the highest finite bound,
        the same convention Prometheus ``histogram_quantile`` uses.
        """
        if not 0.0 <= q <= 1.0:
            raise ValueError("q must be within [0, 1]")
        cumulative, _, total = self.cumulative()
        if total == 0:
            return None
        rank = q * total
        lower_bound = 0.0
        previous = 0
        for index, bound in enumerate(self.buckets):
            if cumulative[index] >= rank:
                in_bucket = cumulative[index] - previous
                if in_bucket == 0:
                    return bound
                return lower_bound + (bound - lower_bound) * (
                    (rank - previous) / in_bucket
                )
            lower_bound = bound
            previous = cumulative[index]
        return self.buckets[-1] if self.buckets else None


class HistogramMetric(_Metric):
    kind = "histogram"

    def __init__(
        self,
        registry: MetricsRegistry,
        name: str,
        description: str,
        labelnames: Sequence[str],
        buckets: Iterable[float] | None = None,
    ) -> None:
        super().__init__(registry, name, description, labelnames)
        chosen = tuple(
            sorted(float(b) for b in (buckets or DEFAULT_LATENCY_BUCKETS_MS))
        )
        if not chosen or any(math.isinf(b) for b in chosen):
            raise ValueError("Histogram buckets must be finite and non-empty.")
        self.buckets = chosen

    def _new_child(self) -> _HistogramChild:
        return _HistogramChild(self.buckets)

    def observe(self, amount: float) -> None:
        self._unlabelled().observe(amount)

    @property
    def count(self) -> int:
        return int(self._unlabelled().count)

    @property
    def sum(self) -> float:
        return float(self._unlabelled().sum)

    def quantile(self, q: float, **labels: Any) -> float | None:
        child: _HistogramChild = self.labels(**labels) if labels else self._unlabelled()
        return child.quantile(q)

    def export_lines(self) -> list[str]:
        lines: list[str] = []
        for key, child in self._snapshot():
            cumulative, total_sum, total = child.cumulative()
            for bound, count in zip(self.buckets, cumulative[:-1], strict=True):
                le = f'le="{_fmt(bound)}"'
                lines.append(
                    f"{self.name}_bucket"
                    f"{_render_labels(self.labelnames, key, le)} {count}"
                )
            inf = 'le="+Inf"'
            lines.append(
                f"{self.name}_bucket"
                f"{_render_labels(self.labelnames, key, inf)} {cumulative[-1]}"
            )
            rendered = _render_labels(self.labelnames, key)
            lines.append(f"{self.name}_sum{rendered} {_fmt(total_sum)}")
            lines.append(f"{self.name}_count{rendered} {total}")
        return lines


class MetricsRegistry:
    """Process-local registry exported in Prometheus text format."""

    def __init__(self, *, max_series_per_metric: int = DEFAULT_MAX_SERIES) -> None:
        if max_series_per_metric < 1:
            raise ValueError("max_series_per_metric must be positive")
        self.max_series_per_metric = max_series_per_metric
        self._lock = threading.Lock()
        self._metrics: dict[str, _Metric] = {}
        self._overflow = CounterMetric(
            self,
            "ucve_metrics_series_overflow_total",
            "Samples folded into the overflow series after a metric hit its series cap",
            ("metric",),
        )

    # Backwards-compatible views used by older callers and tests.
    @property
    def counters(self) -> dict[str, _Metric]:
        return {n: m for n, m in self._metrics.items() if m.kind == "counter"}

    @property
    def histograms(self) -> dict[str, _Metric]:
        return {n: m for n, m in self._metrics.items() if m.kind == "histogram"}

    def names(self) -> list[str]:
        with self._lock:
            return list(self._metrics)

    def get(self, name: str) -> _Metric | None:
        with self._lock:
            return self._metrics.get(name)

    def _register(self, metric: _Metric) -> Any:
        with self._lock:
            existing = self._metrics.get(metric.name)
            if existing is not None:
                if (
                    type(existing) is not type(metric)
                    or existing.labelnames != metric.labelnames
                ):
                    raise ValueError(
                        f"Metric {metric.name} already registered with a different "
                        "type or labels."
                    )
                return existing
            self._metrics[metric.name] = metric
            return metric

    def counter(
        self, name: str, description: str = "", labelnames: Sequence[str] = ()
    ) -> CounterMetric:
        result: CounterMetric = self._register(
            CounterMetric(self, name, description, labelnames)
        )
        return result

    def gauge(
        self, name: str, description: str = "", labelnames: Sequence[str] = ()
    ) -> GaugeMetric:
        result: GaugeMetric = self._register(
            GaugeMetric(self, name, description, labelnames)
        )
        return result

    def histogram(
        self,
        name: str,
        description: str = "",
        labelnames: Sequence[str] = (),
        buckets: Iterable[float] | None = None,
    ) -> HistogramMetric:
        result: HistogramMetric = self._register(
            HistogramMetric(self, name, description, labelnames, buckets)
        )
        return result

    def _record_overflow(self, metric_name: str) -> None:
        # The overflow counter's own label space is the set of metric names,
        # which is bounded by the code base; it never recurses.
        key = (metric_name,)
        with self._overflow._lock:
            child = self._overflow._series.get(key)
            if child is None:
                child = _CounterChild()
                self._overflow._series[key] = child
        child.inc()

    def export_prometheus_text(self) -> str:
        lines: list[str] = []
        with self._lock:
            metrics = list(self._metrics.values())
        for metric in [*metrics, self._overflow]:
            body = metric.export_lines()
            if metric is self._overflow and not body:
                continue
            lines.append(f"# HELP {metric.name} {metric.description}")
            lines.append(f"# TYPE {metric.name} {metric.kind}")
            lines.extend(body)
        return "\n".join(lines) + "\n"


_global_registry = MetricsRegistry()

# --- Standard Wavia metrics (labels are closed, low-cardinality sets) -------
ucve_turn_latency_ms = _global_registry.histogram(
    "ucve_turn_latency_ms",
    "End of user speech to first audible assistant sample, per completed turn",
    labelnames=("measurement_quality",),
)
ucve_turn_stage_ms = _global_registry.histogram(
    "ucve_turn_stage_ms",
    "Per-stage turn durations (stt, llm, tts, ...) from the latency waterfall",
    labelnames=("stage",),
)
ucve_barge_in_total = _global_registry.counter(
    "ucve_barge_in_total", "Committed barge-in interruptions"
)
ucve_provider_failover_total = _global_registry.counter(
    "ucve_provider_failover_total",
    "Provider failovers to the next route in a priority chain",
    labelnames=("category",),
)
ucve_buffer_drop_total = _global_registry.counter(
    "ucve_buffer_drop_total",
    "Audio frames or chunks dropped from a bounded buffer",
    labelnames=("buffer",),
)
ucve_active_sessions = _global_registry.gauge(
    "ucve_active_sessions",
    "Realtime sessions currently open in this process",
    labelnames=("service",),
)
ucve_http_requests_total = _global_registry.counter(
    "ucve_http_requests_total",
    "HTTP requests by route template and status class",
    labelnames=("service", "method", "route", "status_class"),
)
ucve_http_request_duration_ms = _global_registry.histogram(
    "ucve_http_request_duration_ms",
    "HTTP request duration by route template",
    labelnames=("service", "method", "route"),
)
ucve_event_loop_lag_ms = _global_registry.histogram(
    "ucve_event_loop_lag_ms",
    "Delay between a scheduled event-loop wake-up and when it actually ran",
    labelnames=("service",),
    buckets=(1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 5000.0),
)
ucve_jobs_total = _global_registry.counter(
    "ucve_jobs_total",
    "Background job executions by job and outcome",
    labelnames=("job", "outcome"),
)
ucve_job_queue_depth = _global_registry.gauge(
    "ucve_job_queue_depth",
    "Durable job rows by job family and state, as last observed by the jobs runner",
    labelnames=("job", "state"),
)
ucve_alerts_total = _global_registry.counter(
    "ucve_alerts_total",
    "Operational alerts raised, by code and severity",
    labelnames=("code", "severity"),
)
ucve_readiness = _global_registry.gauge(
    "ucve_readiness",
    "1 when the named dependency check passed on the last readiness probe",
    labelnames=("service", "check"),
)


def get_metrics_registry() -> MetricsRegistry:
    return _global_registry
