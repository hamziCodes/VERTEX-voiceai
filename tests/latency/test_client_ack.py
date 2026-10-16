"""Turn-correlated client playback acknowledgement tests."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from core.latency.collector import LatencyCollector
from core.latency.waterfall import LatencyWaterfall
from sdk.python.ucve.client import UCVEVoiceClient
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig

REPO_ROOT = Path(__file__).resolve().parents[2]


def _turn(*, session_id=None, acoustic_end_ms: float = 1_000.0) -> LatencyWaterfall:
    return LatencyWaterfall(
        session_id=session_id or uuid4(),
        acoustic_end_ms=acoustic_end_ms,
    )


def test_ack_updates_only_the_matching_overlapping_turn() -> None:
    collector = LatencyCollector()
    first = _turn()
    second = _turn(session_id=first.session_id, acoustic_end_ms=2_000.0)
    collector.register_turn(first)
    collector.register_turn(second)

    result = collector.acknowledge_playback(
        turn_id=second.turn_id,
        client_playback_started_ms=50.0,
        client_scheduled_playback_ms=48.0,
        receipt_monotonic_ms=2_450.0,
        underrun=False,
        prebuffer_ms=50.0,
    )

    assert result.accepted is True
    assert first.playback_ack_received_ms is None
    assert second.playback_ack_received_ms == 2_450.0
    assert second.client_playback_started_ms == 50.0
    assert second.user_perceived_latency_ms() == 450.0
    assert second.measurement_quality == "server_ack_upper_bound"


def test_unknown_and_duplicate_acknowledgements_are_rejected() -> None:
    collector = LatencyCollector()
    waterfall = _turn()
    collector.register_turn(waterfall)

    unknown = collector.acknowledge_playback(
        turn_id=uuid4(),
        client_playback_started_ms=10.0,
        receipt_monotonic_ms=1_100.0,
    )
    first = collector.acknowledge_playback(
        turn_id=waterfall.turn_id,
        client_playback_started_ms=20.0,
        receipt_monotonic_ms=1_200.0,
    )
    duplicate = collector.acknowledge_playback(
        turn_id=waterfall.turn_id,
        client_playback_started_ms=5.0,
        receipt_monotonic_ms=1_300.0,
    )

    assert (unknown.accepted, unknown.reason) == (False, "unknown_turn")
    assert first.accepted is True
    assert (duplicate.accepted, duplicate.reason) == (False, "duplicate_ack")
    assert waterfall.client_playback_started_ms == 20.0


def test_late_ack_updates_a_turn_already_recorded() -> None:
    collector = LatencyCollector()
    waterfall = _turn(acoustic_end_ms=1_000.0)
    collector.record_turn(waterfall)

    result = collector.acknowledge_playback(
        turn_id=waterfall.turn_id,
        client_playback_started_ms=25.0,
        receipt_monotonic_ms=1_350.0,
    )

    assert result.accepted is True
    assert collector.percentile_summary()["p50_ms"] == 350.0


def test_client_clock_is_never_subtracted_from_server_clock() -> None:
    collector = LatencyCollector()
    waterfall = _turn(acoustic_end_ms=10_000.0)
    collector.register_turn(waterfall)

    collector.acknowledge_playback(
        turn_id=waterfall.turn_id,
        client_playback_started_ms=7.0,
        client_scheduled_playback_ms=9_999_999_999.0,
        receipt_monotonic_ms=10_600.0,
    )

    assert waterfall.user_perceived_latency_ms() == 600.0
    assert waterfall.client_playback_started_ms == 7.0


def test_disconnect_and_barge_in_mark_unfinished_turns() -> None:
    collector = LatencyCollector()
    session_id = uuid4()
    disconnected = _turn(session_id=session_id)
    other_session = _turn()
    collector.register_turn(disconnected)
    collector.register_turn(other_session)

    collector.cancel_turn(disconnected.turn_id, reason="barge_in")
    rejected = collector.acknowledge_playback(
        turn_id=disconnected.turn_id,
        client_playback_started_ms=10.0,
        receipt_monotonic_ms=1_100.0,
    )
    collector.clear_session(session_id)

    assert disconnected.excluded_reason == "barge_in"
    assert (rejected.accepted, rejected.reason) == (False, "turn_excluded")
    assert collector.get_turn(disconnected.turn_id) is None
    assert collector.get_turn(other_session.turn_id) is other_session


def test_shared_schema_requires_turn_correlated_playback_ack() -> None:
    schema = json.loads(
        (REPO_ROOT / "sdk" / "shared" / "event_schema.json").read_text(
            encoding="utf-8"
        )
    )
    playback = next(
        item for item in schema["oneOf"] if item["title"] == "ControlPlaybackStarted"
    )
    latency = next(
        item for item in schema["oneOf"] if item["title"] == "MetricWaterfall"
    )

    assert "turn_id" in playback["properties"]["payload"]["required"]
    assert "client_playback_started_ms" in playback["properties"]["payload"]["required"]
    assert latency["properties"]["payload"]["properties"]["kind"]["const"] == "latency"


@pytest.mark.asyncio
async def test_python_sdk_emits_performance_clock_and_turn_id() -> None:
    class FakeWebSocket:
        sent: list[str]

        def __init__(self) -> None:
            self.sent = []

        async def send(self, payload: str) -> None:
            self.sent.append(payload)

    client = UCVEVoiceClient("ephemeral-token")
    socket = FakeWebSocket()
    client._ws = socket
    turn_id = str(uuid4())

    await client.emit_playback_started(
        turn_id,
        client_scheduled_playback_ms=25.0,
        prebuffer_ms=50.0,
        underrun=False,
    )
    payload = json.loads(socket.sent[0])["payload"]

    assert payload["turn_id"] == turn_id
    assert payload["client_clock_domain"] == "client_performance_ms"
    assert payload["client_playback_started_ms"] >= 0
    assert payload["prebuffer_ms"] == 50.0


@pytest.mark.asyncio
async def test_python_sdk_exposes_server_audio_start_turn_id() -> None:
    turn_id = str(uuid4())
    received: list[dict[str, object]] = []

    client = UCVEVoiceClient("ephemeral-token")

    def on_audio_start(payload: dict[str, object]) -> None:
        received.append(payload)
        client._running = False

    class ReceivingWebSocket:
        async def recv(self) -> str:
            return json.dumps(
                {
                    "event_type": "audio_start",
                    "payload": {
                        "turn_id": turn_id,
                        "server_send_ms": 1_000.0,
                        "clock_domain": "server_monotonic_ms",
                    },
                }
            )

    client.on_audio_start = on_audio_start
    client._ws = ReceivingWebSocket()
    client._running = True

    await client._listen_loop()

    assert received[0]["turn_id"] == turn_id


def test_browser_reports_ack_at_scheduled_audio_start() -> None:
    browser = (REPO_ROOT / "examples" / "web-client" / "index.html").read_text(
        encoding="utf-8"
    )

    assert "type === 'audio_start'" in browser
    assert "turn_id: turnId" in browser
    assert "client_clock_domain: 'client_performance_ms'" in browser
    assert "setTimeout(() =>" in browser
    assert "playbackAckTimers.forEach" in browser


@pytest.mark.asyncio
async def test_greeting_is_registered_before_audio_and_emits_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    orchestrator = PipelineOrchestrator()
    config = PipelineSessionConfig(
        session_id="greeting-session",
        tenant_id="test-tenant",
        agent_id="test-agent",
    )
    emitted: list[LatencyWaterfall] = []

    async def fake_finish(
        sentences: list[str],
        session_config: PipelineSessionConfig,
        waterfall: LatencyWaterfall,
    ) -> None:
        assert sentences == ["Welcome"]
        assert session_config is config
        assert orchestrator.latency_collector.get_turn(waterfall.turn_id) is waterfall
        waterfall.server_send_ms = orchestrator.latency_hooks.now_ms()
        result = orchestrator.latency_collector.acknowledge_playback(
            turn_id=waterfall.turn_id,
            client_playback_started_ms=25.0,
            receipt_monotonic_ms=orchestrator.latency_hooks.now_ms(),
        )
        assert result.accepted is True

    async def fake_emit(waterfall: LatencyWaterfall) -> None:
        emitted.append(waterfall)

    monkeypatch.setattr(orchestrator, "_finish_turn_tts", fake_finish)
    monkeypatch.setattr(orchestrator, "_emit_latency_telemetry", fake_emit)

    await orchestrator.run_greeting(config, "Welcome")

    assert len(emitted) == 1
    assert emitted[0].acoustic_end_ms is None
    assert emitted[0].measurement_quality == "playback_ack_only"
    assert orchestrator._active_latency_turn_id is None
