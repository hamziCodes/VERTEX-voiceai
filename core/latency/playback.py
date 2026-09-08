"""Client Playback Event Handler — Processes control.playback_started timestamps."""

from __future__ import annotations

import time
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
        """Record playback start on the same clock as other waterfall stages.

        Clients send ``Date.now()`` (wall clock). Pipeline stages use
        ``time.monotonic()`` ms — mixing them produced multi-year fake e2e
        latencies. Prefer server monotonic at ack receipt.
        """
        _ = client_timestamp_ms
        waterfall.playback_start_ms = time.monotonic() * 1000.0
        return waterfall.compute_e2e_latency()
