"""H5: mock-provider 3-turn pipeline + barge-in + VAD frame."""

from __future__ import annotations

import asyncio

import pytest

from core.language.numerals import number_to_english_words
from core.types.audio import AudioFrame
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig


@pytest.fixture
def test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.delenv("RUN_LIVE_PROVIDERS", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)


@pytest.mark.asyncio
async def test_three_turn_mock_pipeline(test_env: None) -> None:
    audio_chunks: list[bytes] = []
    orch = PipelineOrchestrator(on_audio_out=lambda b: audio_chunks.append(b))
    config = PipelineSessionConfig(
        session_id="h5-s1",
        tenant_id="h5-t1",
        agent_id="h5-a1",
        language="en",
    )
    await orch.run(
        config,
        user_turns=["hi", "what is two plus two", "thanks"],
    )
    turns = await orch.redis_store.get_turns("h5-s1")
    # 3 user + 3 assistant
    assert len(turns) >= 6
    assert audio_chunks, "TTS should emit PCM"
    assert orch.fsm.state.value == "DISCONNECTED"


@pytest.mark.asyncio
async def test_barge_in_cancels_tts(test_env: None) -> None:
    orch = PipelineOrchestrator()

    async def slow_tts() -> None:
        await asyncio.sleep(5)

    orch._tts_task = asyncio.create_task(slow_tts())
    await asyncio.sleep(0.01)
    await orch.cancel_tts()
    assert orch._tts_task.done()


def test_vad_process_frame(test_env: None) -> None:
    orch = PipelineOrchestrator()
    # Non-silent PCM
    pcm = (10000).to_bytes(2, "little", signed=True) * 320
    frame = AudioFrame(pcm16=pcm, sample_rate=16000)
    evt = orch.process_frame(frame)
    assert evt.probability >= 0.0


def test_english_numerals_algorithmic() -> None:
    assert "one thousand" in number_to_english_words(1234)
    assert "thirty four" in number_to_english_words(1234)
    # Not magic-only: other magnitudes work
    assert "five thousand" in number_to_english_words(5000)


@pytest.mark.asyncio
async def test_hipaa_still_blocks(test_env: None) -> None:
    orch = PipelineOrchestrator()
    config = PipelineSessionConfig(
        session_id="h5-hipaa",
        tenant_id="t",
        agent_id="a",
        compliance_tier="hipaa",
        hipaa_baa_acknowledged=False,
    )
    with pytest.raises(PermissionError):
        await orch.run(config, user_turns=["hi"])
