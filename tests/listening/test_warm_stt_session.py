"""Warm streaming-STT lifecycle and provider-selection contracts."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest

from core.listening.config import ListeningPipelineConfig
from core.providers.adapters.gladia_live_stt import GladiaLiveSTTSession
from core.providers.interfaces.stt import Transcript
from core.providers.live_stt_factory import build_live_stt_session
from worker_raw.orchestration import pipeline as pipeline_module
from worker_raw.orchestration.pipeline import PipelineOrchestrator


class _FakeLiveSession:
    def __init__(self, *, delay: float = 0.0) -> None:
        self.delay = delay
        self.start_calls = 0
        self.closed = False
        self._live = False

    @property
    def is_live(self) -> bool:
        return self._live

    async def start(self) -> bool:
        self.start_calls += 1
        await asyncio.sleep(self.delay)
        self._live = True
        return True

    async def send_audio(self, pcm16: bytes) -> None:
        return None

    async def transcripts(self):
        while True:
            await asyncio.sleep(60)
            if False:
                yield None

    async def close(self) -> None:
        self.closed = True
        self._live = False


class _TranscriptSession(_FakeLiveSession):
    def __init__(self, texts: tuple[str, ...]) -> None:
        super().__init__()
        self._live = True
        self.texts = texts

    async def transcripts(self):
        for text in self.texts:
            yield Transcript(text=text, is_final=True)


def test_live_stt_factory_follows_selected_provider() -> None:
    assert isinstance(
        build_live_stt_session("gladia", api_key=None), GladiaLiveSTTSession
    )
    assert build_live_stt_session("deepgram", api_key=None) is None


@pytest.mark.asyncio
async def test_streaming_stt_is_warmed_once_before_first_speech(monkeypatch) -> None:
    fake = _FakeLiveSession()
    monkeypatch.setattr(
        pipeline_module,
        "build_live_stt_session",
        lambda *args, **kwargs: fake,
    )
    orchestrator = PipelineOrchestrator()
    orchestrator.listening_config = replace(
        ListeningPipelineConfig(),
        enabled_phases=frozenset({"streaming_stt"}),
        stt_connect_timeout_ms=100,
    )
    orchestrator._active_stt_id = "gladia"
    orchestrator._ws_session = SimpleNamespace(
        config=SimpleNamespace(language="en")
    )

    first = await orchestrator.prepare_live_stt()
    second = await orchestrator.prepare_live_stt()

    assert first == "ready"
    assert second == "ready"
    assert fake.start_calls == 1
    await orchestrator._close_live_stt()


@pytest.mark.asyncio
async def test_streaming_stt_start_timeout_closes_partial_session(monkeypatch) -> None:
    fake = _FakeLiveSession(delay=0.2)
    monkeypatch.setattr(
        pipeline_module,
        "build_live_stt_session",
        lambda *args, **kwargs: fake,
    )
    orchestrator = PipelineOrchestrator()
    orchestrator.listening_config = replace(
        ListeningPipelineConfig(),
        enabled_phases=frozenset({"streaming_stt"}),
        stt_connect_timeout_ms=10,
    )
    orchestrator._ws_session = SimpleNamespace(
        config=SimpleNamespace(language="en")
    )

    status = await orchestrator.prepare_live_stt()

    assert status == "timeout"
    assert fake.closed is True
    assert orchestrator._live_stt is None


@pytest.mark.asyncio
async def test_unsupported_live_provider_uses_explicit_batch_fallback() -> None:
    orchestrator = PipelineOrchestrator()
    orchestrator.listening_config = replace(
        ListeningPipelineConfig(),
        enabled_phases=frozenset({"streaming_stt"}),
    )
    orchestrator._active_stt_id = "deepgram"
    orchestrator._ws_session = SimpleNamespace(
        config=SimpleNamespace(language="en")
    )

    assert await orchestrator.prepare_live_stt() == "batch_fallback"
    assert orchestrator._live_stt is None


@pytest.mark.asyncio
async def test_live_stt_reconnect_attempts_are_bounded(monkeypatch) -> None:
    sessions: list[_FakeLiveSession] = []

    def build(*args, **kwargs):
        session = _FakeLiveSession(delay=0.1)
        sessions.append(session)
        return session

    monkeypatch.setattr(pipeline_module, "build_live_stt_session", build)
    orchestrator = PipelineOrchestrator()
    orchestrator.listening_config = replace(
        ListeningPipelineConfig(),
        enabled_phases=frozenset({"streaming_stt"}),
        stt_connect_timeout_ms=1,
        stt_reconnect_max_attempts=2,
    )
    orchestrator._ws_session = SimpleNamespace(
        config=SimpleNamespace(language="en")
    )

    assert await orchestrator.prepare_live_stt() == "timeout"
    assert await orchestrator.prepare_live_stt() == "timeout"
    assert await orchestrator.prepare_live_stt() == "failed"
    assert len(sessions) == 2
    assert all(session.closed for session in sessions)


@pytest.mark.asyncio
async def test_stale_stream_cannot_emit_duplicate_finals_after_reconnect() -> None:
    queued: list[str] = []

    async def enqueue(text: str) -> None:
        queued.append(text)

    orchestrator = PipelineOrchestrator()
    stale = _TranscriptSession(("old final",))
    current = _TranscriptSession(("new first", "new second"))
    orchestrator._ws_session = SimpleNamespace(enqueue_voice_turn=enqueue)
    orchestrator._live_stt = current
    orchestrator._live_stt_generation = 2

    await orchestrator._consume_live_stt(stale, 1)
    await orchestrator._consume_live_stt(current, 2)

    assert queued == ["new first", "new second"]
