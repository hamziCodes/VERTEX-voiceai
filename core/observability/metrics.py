"""UCVE Metrics Registry & Prometheus-compatible Exporter."""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Any


@dataclass
class CounterMetric:
    """In-memory counter metric."""

    name: str
    description: str
    _value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    @property
    def value(self) -> float:
        with self._lock:
            return self._value


@dataclass
class HistogramMetric:
    """In-memory histogram metric for latency tracking."""

    name: str
    description: str
    _count: int = 0
    _sum: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def observe(self, amount: float) -> None:
        with self._lock:
            self._count += 1
            self._sum += amount

    @property
    def count(self) -> int:
        with self._lock:
            return self._count

    @property
    def sum(self) -> float:
        with self._lock:
            return self._sum


class MetricsRegistry:
    """In-memory Prometheus-compatible metrics registry."""

    def __init__(self) -> None:
        self.counters: dict[str, CounterMetric] = {}
        self.histograms: dict[str, HistogramMetric] = {}

    def counter(self, name: str, description: str = "") -> CounterMetric:
        if name not in self.counters:
            self.counters[name] = CounterMetric(name=name, description=description)
        return self.counters[name]

    def histogram(self, name: str, description: str = "") -> HistogramMetric:
        if name not in self.histograms:
            self.histograms[name] = HistogramMetric(name=name, description=description)
        return self.histograms[name]

    def export_prometheus_text(self) -> str:
        """Export accumulated metrics in Prometheus text format."""
        lines = []
        for name, counter in self.counters.items():
            lines.append(f"# HELP {name} {counter.description}")
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {counter.value}")

        for name, hist in self.histograms.items():
            lines.append(f"# HELP {name} {hist.description}")
            lines.append(f"# TYPE {name} histogram")
            lines.append(f"{name}_count {hist.count}")
            lines.append(f"{name}_sum {hist.sum}")

        return "\n".join(lines) + "\n"


_global_registry = MetricsRegistry()

# Standard UCVE Metrics
ucve_turn_latency_ms = _global_registry.histogram("ucve_turn_latency_ms", "Turn execution latency in milliseconds")
ucve_barge_in_total = _global_registry.counter("ucve_barge_in_total", "Total barge-in interrupt events")
ucve_provider_failover_total = _global_registry.counter("ucve_provider_failover_total", "Total provider failover events")
ucve_buffer_drop_total = _global_registry.counter("ucve_buffer_drop_total", "Total dropped audio frames due to buffer overflow")


def get_metrics_registry() -> MetricsRegistry:
    return _global_registry
