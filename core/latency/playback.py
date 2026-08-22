"""Client Playback Event Handler — Processes control.playback_started timestamps."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from core.latency.waterfall import LatencyWaterfall


class PlaybackMetricHandler:
    """Processes client-reported playback_started events for LatencyWaterfall traces."""

    @staticmethod
    def handle_playback_started(
        waterfall: LatencyWaterfall,
        client_timestamp_ms: float,
    ) -> float:
        """Attach client-reported audio delivery start timestamp to waterfall."""
        waterfall.playback_start_ms = client_timestamp_ms
        return waterfall.compute_e2e_latency()
