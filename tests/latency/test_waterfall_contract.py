"""Truthful, versioned latency telemetry contract tests."""

from __future__ import annotations

from uuid import uuid4

from core.latency.collector import LatencyCollector
from core.latency.waterfall import LatencyWaterfall
from worker_raw.orchestration.latency_hooks import LatencyHooks


def test_start_turn_does_not_fabricate_speech_or_vad_timestamps() -> None:
    waterfall = LatencyHooks().start_turn(uuid4())

    assert waterfall.acoustic_end_ms is None
    assert waterfall.vad_end_of_speech_ms is None
    assert waterfall.stt_final_ms is None


def test_metric_payload_preserves_missing_data_and_clock_domains() -> None:
    session_id = uuid4()
    turn_id = uuid4()
    waterfall = LatencyWaterfall(
        session_id=session_id,
        turn_id=turn_id,
        acoustic_end_ms=1_000.0,
        vad_end_of_speech_ms=1_120.0,
        stt_final_ms=2_500.0,
    )

    payload = waterfall.to_metric_payload()

    assert payload["kind"] == "latency"
    assert payload["schema_version"] == "1.0"
    assert payload["session_id"] == str(session_id)
    assert payload["turn_id"] == str(turn_id)
    assert payload["clock_domain"] == "server_monotonic_ms"
    assert payload["timestamps_ms"]["client_playback_started"] is None
    assert payload["durations_ms"]["stt_after_acoustic_end"] == 1_500.0
    assert payload["durations_ms"]["user_perceived_e2e"] is None
    assert "playback_ack_missing" in payload["missing_reasons"]
    assert payload["slo"]["status"] == "provisional"


def test_population_percentiles_use_recorded_complete_turns() -> None:
    collector = LatencyCollector()
    for latency_ms in (100.0, 200.0, 300.0, 400.0, 500.0):
        waterfall = LatencyWaterfall(
            session_id=uuid4(),
            acoustic_end_ms=1_000.0,
            playback_ack_received_ms=1_000.0 + latency_ms,
        )
        collector.record_turn(waterfall)

    summary = collector.percentile_summary()

    assert summary == {
        "sample_count": 5,
        "p50_ms": 300.0,
        "p95_ms": 500.0,
        "p99_ms": 500.0,
    }


def test_server_send_is_not_reported_as_audible_playback() -> None:
    waterfall = LatencyWaterfall(
        session_id=uuid4(),
        acoustic_end_ms=1_000.0,
        server_send_ms=1_250.0,
    )

    assert waterfall.user_perceived_latency_ms() is None
    assert waterfall.to_metric_payload()["measurement_quality"] == "incomplete"
