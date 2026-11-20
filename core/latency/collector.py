"""Turn-correlated latency collection and population summaries."""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass
from uuid import UUID

from core.latency.demotion import LatencyDemotionRule
from core.latency.slo_policy import SLOPolicy
from core.latency.waterfall import LatencyWaterfall, StageBudget
from core.observability.metrics import ucve_turn_latency_ms, ucve_turn_stage_ms

_QUALITY_LABELS = frozenset(
    {"server_ack_upper_bound", "playback_ack_only", "incomplete", "excluded"}
)


def _observe_e2e(waterfall: LatencyWaterfall) -> None:
    if getattr(waterfall, "_e2e_metric_recorded", False):
        return
    value = waterfall.user_perceived_latency_ms()
    if value is None:
        return
    quality = waterfall.measurement_quality
    label = quality if quality in _QUALITY_LABELS else "other"
    ucve_turn_latency_ms.labels(measurement_quality=label).observe(value)
    waterfall._e2e_metric_recorded = True  # type: ignore[attr-defined]


def _observe_stages(waterfall: LatencyWaterfall) -> None:
    if getattr(waterfall, "_stage_metrics_recorded", False):
        return
    for stage, value in waterfall.stage_durations_ms().items():
        if stage == "user_perceived_e2e" or value is None:
            continue
        ucve_turn_stage_ms.labels(stage=stage).observe(value)
    waterfall._stage_metrics_recorded = True  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)

DEFAULT_STAGE_BUDGETS: list[StageBudget] = [
    StageBudget(name="stt", budget_ms=150.0, warn_ms=250.0),
    StageBudget(name="rag", budget_ms=100.0, warn_ms=200.0),
    StageBudget(name="llm", budget_ms=200.0, warn_ms=400.0),
    StageBudget(name="tts", budget_ms=150.0, warn_ms=250.0),
]


@dataclass(frozen=True, slots=True)
class PlaybackAckResult:
    accepted: bool
    reason: str
    waterfall: LatencyWaterfall | None = None


def _nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


class LatencyCollector:
    """Collect and correlate bounded per-turn latency traces."""

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
        self._turns: dict[UUID, LatencyWaterfall] = {}

    def register_turn(self, waterfall: LatencyWaterfall) -> LatencyWaterfall:
        self._turns[waterfall.turn_id] = waterfall
        while len(self._turns) > 256:
            self._turns.pop(next(iter(self._turns)))
        return waterfall

    def get_turn(self, turn_id: UUID) -> LatencyWaterfall | None:
        return self._turns.get(turn_id)

    def clear_session(self, session_id: UUID | None = None) -> None:
        """Drop all traces, or only traces belonging to one completed session."""
        if session_id is None:
            self.collected_waterfalls.clear()
            self._turns.clear()
            self.warnings_emitted.clear()
            return
        self._turns = {
            turn_id: waterfall
            for turn_id, waterfall in self._turns.items()
            if waterfall.session_id != session_id
        }
        self.collected_waterfalls = deque(
            (
                waterfall
                for waterfall in self.collected_waterfalls
                if waterfall.session_id != session_id
            ),
            maxlen=256,
        )

    def cancel_turn(self, turn_id: UUID, *, reason: str) -> bool:
        waterfall = self.get_turn(turn_id)
        if waterfall is None:
            return False
        waterfall.excluded_reason = reason
        waterfall.measurement_quality = "excluded"
        return True

    def acknowledge_playback(
        self,
        *,
        turn_id: UUID,
        client_playback_started_ms: float,
        receipt_monotonic_ms: float,
        client_scheduled_playback_ms: float | None = None,
        underrun: bool | None = None,
        prebuffer_ms: float | None = None,
    ) -> PlaybackAckResult:
        waterfall = self.get_turn(turn_id)
        if waterfall is None:
            return PlaybackAckResult(False, "unknown_turn")
        if waterfall.excluded_reason:
            return PlaybackAckResult(False, "turn_excluded", waterfall)
        if waterfall.playback_ack_received_ms is not None:
            return PlaybackAckResult(False, "duplicate_ack", waterfall)
        if client_playback_started_ms < 0 or receipt_monotonic_ms <= 0:
            return PlaybackAckResult(False, "invalid_timestamp", waterfall)
        waterfall.client_playback_started_ms = client_playback_started_ms
        waterfall.client_scheduled_playback_ms = client_scheduled_playback_ms
        waterfall.playback_ack_received_ms = receipt_monotonic_ms
        waterfall.playback_underrun = underrun
        waterfall.prebuffer_ms = prebuffer_ms
        waterfall.measurement_quality = (
            "server_ack_upper_bound"
            if waterfall.acoustic_end_ms is not None
            else "playback_ack_only"
        )
        waterfall.compute_e2e_latency()
        _observe_e2e(waterfall)
        return PlaybackAckResult(True, "accepted", waterfall)

    def record_turn(self, waterfall: LatencyWaterfall) -> LatencyWaterfall:
        """Record a turn without evaluating a single sample as a percentile."""
        self.register_turn(waterfall)
        waterfall.compute_e2e_latency()
        self.collected_waterfalls.append(waterfall)
        _observe_stages(waterfall)
        _observe_e2e(waterfall)
        return waterfall

    def percentile_summary(self) -> dict[str, int | float]:
        values = [
            value
            for waterfall in self.collected_waterfalls
            if (value := waterfall.user_perceived_latency_ms()) is not None
        ]
        return {
            "sample_count": len(values),
            "p50_ms": _nearest_rank(values, 0.50),
            "p95_ms": _nearest_rank(values, 0.95),
            "p99_ms": _nearest_rank(values, 0.99),
        }
