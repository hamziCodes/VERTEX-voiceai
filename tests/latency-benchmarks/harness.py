"""Latency Benchmark Harness — Aggregates turn waterfalls & produces p50/p95/p99 report."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from core.latency.waterfall import LatencyWaterfall


@dataclass
class LatencyBenchmarkReport:
    """Aggregated latency report containing p50, p95, and p99 percentiles."""

    total_turns: int
    p50_ms: float
    p95_ms: float
    p99_ms: float


class LatencyBenchmarkHarness:
    """Scripted benchmark harness for latency aggregation."""

    def __init__(self) -> None:
        self.waterfalls: list[LatencyWaterfall] = []

    def add_waterfall(self, waterfall: LatencyWaterfall) -> None:
        self.waterfalls.append(waterfall)

    def generate_report(self) -> LatencyBenchmarkReport:
        """Calculate p50, p95, and p99 latency metrics across all recorded turns."""
        if not self.waterfalls:
            return LatencyBenchmarkReport(total_turns=0, p50_ms=0.0, p95_ms=0.0, p99_ms=0.0)

        latencies = sorted([w.compute_e2e_latency() for w in self.waterfalls])
        count = len(latencies)

        def percentile(p: float) -> float:
            idx = int(p * count)
            idx = min(idx, count - 1)
            return latencies[idx]

        return LatencyBenchmarkReport(
            total_turns=count,
            p50_ms=percentile(0.50),
            p95_ms=percentile(0.95),
            p99_ms=percentile(0.99),
        )
