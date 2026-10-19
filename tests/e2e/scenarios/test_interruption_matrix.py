"""Offline Phase 04 interruption matrix and played-context invariants."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from uuid import uuid4

import pytest

from core.fsm.cancel_contract import ThreePointCancel
from core.fsm.events import SessionEvent
from core.fsm.interrupt_buffer import InterruptBuffer
from core.fsm.states import SessionState
from core.listening.barge_verify import BargeVerifyEngine
from core.listening.config import ListeningPipelineConfig
from core.playback.turn_commit import TurnCommitTracker
from core.types.events import ControlEventType
from sdk.python.ucve.client import UCVEVoiceClient
from worker_raw.orchestration.pipeline import PipelineOrchestrator


def test_played_text_commit_uses_pcm_boundary_and_is_idempotent() -> None:
    tracker = TurnCommitTracker()
    tracker.start_segment("turn-1", "one two three four")
    tracker.add_audio("turn-1", 3200)  # 100 ms at 16 kHz mono PCM16

    first = tracker.commit("turn-1", played_audio_ms=50)
    duplicate = tracker.commit("turn-1", played_audio_ms=100)

    assert first.text == "one two"
    assert first.complete is False
    assert duplicate == first


def test_full_playback_commits_all_generated_segments() -> None:
    tracker = TurnCommitTracker()
    tracker.start_segment("turn-2", "first sentence")
    tracker.add_audio("turn-2", 1600)
    tracker.start_segment("turn-2", "second sentence")
    tracker.add_audio("turn-2", 3200)

    result = tracker.commit("turn-2", complete=True)

    assert result.text == "first sentence second sentence"
    assert result.complete is True
    assert result.played_pcm_bytes == 4800


def test_interrupting_transcript_is_retained_once_across_overlapping_finals() -> None:
    buffer = InterruptBuffer()
    buffer.append_partial("please stop")
    buffer.append_final("please stop")
    buffer.append_final("please stop")
    buffer.append_final("stop right now")

    assert buffer.get_next_turn_input() == "please stop right now"
    assert buffer.get_next_turn_input() == ""


@pytest.mark.asyncio
async def test_barge_verification_resolves_as_soon_as_speech_is_sustained() -> None:
    config = ListeningPipelineConfig(
        enabled_phases=frozenset({"barge_verify"}),
        barge_verify_window_ms=500,
        barge_min_sustained_speech_ms=30,
        barge_text_backup_words=2,
    )
    engine = BargeVerifyEngine(config)
    calls: list[str] = []

    async def feed() -> None:
        while not engine.is_verifying:
            await asyncio.sleep(0)
        engine.note_vad(0.9, frame_ms=30)

    started = time.perf_counter()
    feeder = asyncio.create_task(feed())
    decision = await engine.run(
        pause=lambda: calls.append("pause"),
        resume=lambda: calls.append("resume"),
        commit=lambda: calls.append("commit"),
    )
    await feeder

    assert decision.committed is True
    assert time.perf_counter() - started < 0.2
    assert calls == ["pause", "commit"]


@pytest.mark.asyncio
async def test_two_word_backup_commits_but_one_word_noise_resumes() -> None:
    config = ListeningPipelineConfig(
        enabled_phases=frozenset({"barge_verify"}),
        barge_verify_window_ms=30,
        barge_min_sustained_speech_ms=100,
        barge_text_backup_words=2,
    )

    async def decide(partial: str) -> bool:
        engine = BargeVerifyEngine(config)

        async def feed() -> None:
            while not engine.is_verifying:
                await asyncio.sleep(0)
            engine.note_partial(partial)

        feeder = asyncio.create_task(feed())
        decision = await engine.run(
            pause=lambda: None,
            resume=lambda: None,
            commit=lambda: None,
        )
        await feeder
        return decision.committed

    assert await decide("wait") is False
    assert await decide("wait please") is True


@pytest.mark.asyncio
async def test_lingering_vad_speaking_flag_without_evidence_is_false_alarm() -> None:
    config = ListeningPipelineConfig(
        enabled_phases=frozenset({"barge_verify"}),
        barge_verify_window_ms=10,
        barge_min_sustained_speech_ms=30,
        barge_text_backup_words=2,
    )
    engine = BargeVerifyEngine(config)
    resumed: list[bool] = []

    decision = await engine.run(
        pause=lambda: None,
        resume=lambda: resumed.append(True),
        commit=lambda: None,
        is_speaking=lambda: True,
    )

    assert decision.committed is False
    assert resumed == [True]


@pytest.mark.asyncio
async def test_three_point_cancel_waits_for_tasks_and_flushes_once() -> None:
    contract = ThreePointCancel()
    flushed: list[str] = []

    async def hanging() -> None:
        await asyncio.Event().wait()

    task = asyncio.create_task(hanging())
    contract.register_task(task)
    contract.register_flush_callback(lambda: flushed.append("flush"))

    cancelled = await contract.cancel_and_wait()

    assert cancelled == 1
    assert task.done()
    assert flushed == ["flush"]


@pytest.mark.parametrize(
    "stage",
    ["stt", "rag", "llm", "tool_filler", "tts", "server_egress"],
)
@pytest.mark.asyncio
async def test_each_owned_pipeline_stage_is_cancellable(stage: str) -> None:
    contract = ThreePointCancel()
    exited = asyncio.Event()

    async def stage_work() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            exited.set()

    task = asyncio.create_task(stage_work(), name=f"phase04:{stage}")
    contract.register_task(task)
    await asyncio.sleep(0)

    assert await contract.cancel_and_wait() == 1
    assert exited.is_set()
    assert task.done()


def test_shared_schema_has_canonical_interruption_lifecycle_events() -> None:
    with open("sdk/shared/event_schema.json", encoding="utf-8") as handle:
        schema = json.load(handle)
    titles = {item["title"] for item in schema["oneOf"]}
    expected = {
        "ControlBargeIn",
        "ControlClearAudio",
        "ControlClearAudioAck",
        "ControlPlaybackDrained",
    }
    assert expected <= titles
    assert ControlEventType.BARGE_IN.value == "control.barge_in"
    assert ControlEventType.CLEAR_AUDIO.value == "control.clear_audio"


class _EventTransport:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def send_control_event(
        self, event_type: Any, payload: dict[str, Any]
    ) -> None:
        value = event_type.value if hasattr(event_type, "value") else str(event_type)
        self.events.append((value, payload))


@pytest.mark.asyncio
async def test_barge_in_emits_ordered_clear_and_commits_only_acknowledged_audio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    orchestrator = PipelineOrchestrator()
    transport = _EventTransport()
    orchestrator._ws_session = type("Session", (), {"transport": transport})()
    turn_id = str(uuid4())
    orchestrator._active_playback_turn_id = turn_id
    orchestrator._active_latency_turn_id = uuid4()
    orchestrator._pending_assistant_turns[turn_id] = ("session", "en")
    orchestrator._turn_commit_tracker.start_segment(turn_id, "one two three four")
    orchestrator._turn_commit_tracker.add_audio(turn_id, 3200)
    orchestrator.fsm.trigger(SessionEvent.SESSION_ADMITTED)
    orchestrator.fsm.trigger(SessionEvent.STT_FINAL)

    await orchestrator.execute_immediate_barge_in(reason="test")

    assert [event[0] for event in transport.events[:2]] == [
        "control.barge_in",
        "control.clear_audio",
    ]
    barge_payload = transport.events[0][1]
    clear_payload = transport.events[1][1]
    assert barge_payload["turn_id"] == turn_id
    assert clear_payload["sequence"] > barge_payload["sequence"]
    assert orchestrator.fsm.state == SessionState.BARGE_IN_INTERRUPTED

    accepted = await orchestrator.handle_clear_audio_ack(
        turn_id=turn_id,
        sequence=clear_payload["sequence"],
        played_audio_ms=50,
    )
    turns = await orchestrator.redis_store.get_turns("session")
    await orchestrator.shutdown_runtime_resources()

    assert accepted is True
    assert turns[-1]["text"] == "one two"
    assert turns[-1]["playback_complete"] is False


@pytest.mark.asyncio
async def test_sender_rejects_chunk_dequeued_before_barge_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    sent: list[bytes] = []
    orchestrator = PipelineOrchestrator(on_audio_out=sent.append)
    orchestrator.pause_playback()
    await orchestrator._emit_audio(b"\x00\x00" * 160)
    await asyncio.sleep(0)

    started = time.perf_counter()
    await orchestrator.execute_immediate_barge_in(reason="generation test")
    interruption_ms = (time.perf_counter() - started) * 1000
    await asyncio.sleep(0)
    await orchestrator.shutdown_runtime_resources()

    assert sent == []
    assert interruption_ms < 100


@pytest.mark.asyncio
async def test_duplicate_concurrent_barge_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    orchestrator = PipelineOrchestrator()
    transport = _EventTransport()
    orchestrator._ws_session = type("Session", (), {"transport": transport})()
    orchestrator._active_playback_turn_id = str(uuid4())

    await asyncio.gather(
        orchestrator.execute_immediate_barge_in(reason="first"),
        orchestrator.execute_immediate_barge_in(reason="duplicate"),
    )
    await orchestrator.shutdown_runtime_resources()

    assert [kind for kind, _ in transport.events].count("control.barge_in") == 1
    assert [kind for kind, _ in transport.events].count("control.clear_audio") == 1


@pytest.mark.asyncio
async def test_missing_clear_ack_commits_no_unplayed_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    orchestrator = PipelineOrchestrator()
    transport = _EventTransport()
    orchestrator._ws_session = type("Session", (), {"transport": transport})()
    turn_id = str(uuid4())
    orchestrator._active_playback_turn_id = turn_id
    orchestrator._pending_assistant_turns[turn_id] = ("session-timeout", "en")
    orchestrator._turn_commit_tracker.start_segment(turn_id, "must not be stored")
    orchestrator._turn_commit_tracker.add_audio(turn_id, 3200)

    await orchestrator.execute_immediate_barge_in(reason="no ack")
    await asyncio.sleep(0.55)
    turns = await orchestrator.redis_store.get_turns("session-timeout")
    await orchestrator.shutdown_runtime_resources()

    assert turns == []
    assert any(
        kind == "degraded_mode" and payload.get("kind") == "clear_audio_ack_timeout"
        for kind, payload in transport.events
    )


@pytest.mark.asyncio
async def test_rapid_back_to_back_turns_wait_for_each_playback_drain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    orchestrator = PipelineOrchestrator()
    orchestrator.fsm.trigger(SessionEvent.SESSION_ADMITTED)

    for index in (1, 2):
        turn_id = str(uuid4())
        orchestrator._pending_assistant_turns[turn_id] = ("rapid", "en")
        orchestrator._turn_commit_tracker.start_segment(turn_id, f"reply {index}")
        orchestrator._turn_commit_tracker.add_audio(turn_id, 1600)
        orchestrator.fsm.trigger(SessionEvent.STT_FINAL)
        orchestrator.fsm.trigger(SessionEvent.TTS_FIRST_BYTE)
        assert orchestrator.fsm.state == SessionState.AGENT_SPEAKING

        assert await orchestrator.handle_playback_drained(
            turn_id=turn_id,
            played_audio_ms=50,
        )
        assert orchestrator.fsm.state == SessionState.LISTENING

    turns = await orchestrator.redis_store.get_turns("rapid")
    await orchestrator.shutdown_runtime_resources()
    assert [turn["text"] for turn in turns] == ["reply 1", "reply 2"]


def test_typescript_sdk_exposes_clear_and_drain_contracts() -> None:
    source = open("sdk/typescript/src/client.ts", encoding="utf-8").read()
    assert "onClearAudio" in source
    assert "control.clear_audio_ack" in source
    assert "emitPlaybackDrained" in source
    assert "control.playback_drained" in source


class _SDKSocket:
    def __init__(self, message: str) -> None:
        self.message = message
        self.sent: list[str] = []
        self.delivered = False

    async def recv(self) -> str:
        if not self.delivered:
            self.delivered = True
            return self.message
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def send(self, message: str) -> None:
        self.sent.append(message)


@pytest.mark.asyncio
async def test_python_sdk_clears_playback_and_acks_sequence() -> None:
    message = json.dumps(
        {
            "event_type": "control.clear_audio",
            "payload": {"turn_id": "turn-1", "sequence": 7, "reason": "barge"},
        }
    )
    socket = _SDKSocket(message)
    client = UCVEVoiceClient("test-token", on_clear_audio=lambda _payload: 42.5)
    client._ws = socket
    client._running = True

    listener = asyncio.create_task(client._listen_loop())
    for _ in range(20):
        if socket.sent:
            break
        await asyncio.sleep(0)
    listener.cancel()
    await asyncio.gather(listener, return_exceptions=True)

    ack = json.loads(socket.sent[0])
    assert ack["event_type"] == "control.clear_audio_ack"
    assert ack["payload"] == {
        "turn_id": "turn-1",
        "sequence": 7,
        "played_audio_ms": 42.5,
    }
