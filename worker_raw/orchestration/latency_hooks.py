"""Worker monotonic latency timestamp hooks."""

from __future__ import annotations

import time
from uuid import UUID

from core.latency.collector import LatencyCollector
from core.latency.waterfall import LatencyWaterfall


class LatencyHooks:
    """Create traces without inventing speech or provider timestamps."""

    def __init__(self, collector: LatencyCollector | None = None) -> None:
        self.collector = collector or LatencyCollector()

    @staticmethod
    def now_ms() -> float:
        return time.monotonic() * 1000.0

    def start_turn(
        self,
        session_id: UUID,
        *,
        acoustic_end_ms: float | None = None,
        vad_end_ms: float | None = None,
    ) -> LatencyWaterfall:
        waterfall = LatencyWaterfall(
            session_id=session_id,
            acoustic_end_ms=acoustic_end_ms,
            vad_end_of_speech_ms=vad_end_ms,
        )
        self.collector.register_turn(waterfall)
        return waterfall
