"""Worker Raw Monotonic Latency Timestamp Hooks."""

from __future__ import annotations

import time
from uuid import UUID

from core.latency.collector import LatencyCollector
from core.latency.waterfall import LatencyWaterfall


class LatencyHooks:
    """Timestamp injection helper for pipeline orchestration stages."""

    def __init__(self, collector: LatencyCollector | None = None) -> None:
        self.collector = collector or LatencyCollector()

    @staticmethod
    def now_ms() -> float:
        """Get monotonic timestamp in milliseconds."""
        return time.monotonic() * 1000.0

    def start_turn(self, session_id: UUID) -> LatencyWaterfall:
        """Initialize turn waterfall with VAD speech-end timestamp."""
        waterfall = LatencyWaterfall(session_id=session_id)
        waterfall.vad_end_of_speech_ms = self.now_ms()
        return waterfall
