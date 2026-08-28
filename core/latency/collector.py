"""Latency Collector — Aggregates per-stage timestamps & computes waterfall traces."""

from __future__ import annotations

from collections import deque
import logging
from uuid import UUID

from core.latency.demotion import LatencyDemotionRule
from core.latency.slo_policy import SLOPolicy
from core.latency.waterfall import LatencyWaterfall, StageBudget

logger = logging.getLogger(__name__)

DEFAULT_STAGE_BUDGETS: list[StageBudget] = [
    StageBudget(name="stt", budget_ms=150.0, warn_ms=250.0),
    StageBudget(name="rag", budget_ms=100.0, warn_ms=200.0),
    StageBudget(name="llm", budget_ms=200.0, warn_ms=400.0),
    StageBudget(name="tts", budget_ms=150.0, warn_ms=250.0),
]


class LatencyCollector:
    """Collects per-stage latency deltas and evaluates SLO policies."""

    def __init__(
        self,
        budgets: list[StageBudget] | None = None,
        slo_policy: SLOPolicy | None = None,
    ) -> None:
        self.budgets = {b.name: b for b in (budgets or DEFAULT_STAGE_BUDGETS)}
        self.slo_policy = slo_policy or SLOPolicy()
        self.demotion_rule = LatencyDemotionRule()
        self.collected_waterfalls: deque[LatencyWaterfall] = deque(maxlen=256)
        self.warnings_emitted: list[str] = []

    def clear_session(self) -> None:
        """Drop in-memory waterfall traces for completed session."""
        self.collected_waterfalls.clear()
        self.warnings_emitted.clear()

    def record_turn(self, waterfall: LatencyWaterfall) -> LatencyWaterfall:
        """Process turn waterfall trace and log budget breach warnings."""
        e2e = waterfall.compute_e2e_latency()

        if self.slo_policy.alert_on_breach and e2e > self.slo_policy.e2e_p50_target_ms:
            msg = f"Latency SLO breach: e2e latency ({e2e:.1f} ms) exceeded p50 target ({self.slo_policy.e2e_p50_target_ms:.1f} ms)"
            logger.warning(msg)
            self.warnings_emitted.append(msg)

        self.collected_waterfalls.append(waterfall)
        return waterfall
