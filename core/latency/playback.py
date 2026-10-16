"""Playback acknowledgement helpers with explicit clock-domain handling."""

from __future__ import annotations

import time

from core.latency.waterfall import LatencyWaterfall


class PlaybackMetricHandler:
    """Attach playback evidence without mixing client and server clocks."""

    @staticmethod
    def record_client_ack(
        waterfall: LatencyWaterfall,
        *,
        client_playback_started_ms: float,
        receipt_monotonic_ms: float | None = None,
        client_scheduled_playback_ms: float | None = None,
        underrun: bool | None = None,
        prebuffer_ms: float | None = None,
    ) -> float | None:
        if waterfall.playback_ack_received_ms is not None:
            return waterfall.user_perceived_latency_ms()
        waterfall.client_playback_started_ms = client_playback_started_ms
        waterfall.client_scheduled_playback_ms = client_scheduled_playback_ms
        waterfall.playback_ack_received_ms = (
            receipt_monotonic_ms
            if receipt_monotonic_ms is not None
            else time.monotonic() * 1000.0
        )
        waterfall.playback_underrun = underrun
        waterfall.prebuffer_ms = prebuffer_ms
        waterfall.measurement_quality = "server_ack_upper_bound"
        waterfall.compute_e2e_latency()
        return waterfall.user_perceived_latency_ms()

    @staticmethod
    def handle_playback_started(
        waterfall: LatencyWaterfall,
        client_timestamp_ms: float,
    ) -> float:
        """Compatibility path for legacy same-clock tests and callers.

        The realtime server uses ``record_client_ack`` and never subtracts this
        client timestamp from server monotonic timestamps.
        """
        waterfall.playback_start_ms = client_timestamp_ms
        return waterfall.compute_e2e_latency()
