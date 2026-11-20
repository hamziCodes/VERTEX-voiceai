"""SpeechCaptureEngine + process_frame_async wiring tests."""

from __future__ import annotations

import struct

import pytest

from core.listening.config import ListeningPipelineConfig
from core.listening.speech_capture import SpeechCaptureEngine
from core.providers.interfaces.vad import VADConfig
from core.types.audio import AudioFrame
from core.types.constants import FRAME_SAMPLES
from core.vad.silero_adapter import SileroVADAdapter
from worker_raw.orchestration.pipeline import PipelineOrchestrator


def _loud_frame() -> AudioFrame:
    pcm = struct.pack(f"<{FRAME_SAMPLES}h", *([12000] * FRAME_SAMPLES))
    return AudioFrame(pcm16=pcm, sample_rate=16000, channel_count=1)


def _silent_frame() -> AudioFrame:
    pcm = struct.pack(f"<{FRAME_SAMPLES}h", *([0] * FRAME_SAMPLES))
    return AudioFrame(pcm16=pcm, sample_rate=16000, channel_count=1)


def test_pre_roll_seeded_into_utterance() -> None:
    vad = SileroVADAdapter(VADConfig(min_speech_frames=2, min_silence_frames=3))
    vad._session = None
    cfg = ListeningPipelineConfig(
        enabled_phases=frozenset({"pre_roll"}),
        vad_pre_speech_ms=200,
    )
    engine = SpeechCaptureEngine(vad, cfg)
    lookback = struct.pack(f"<{FRAME_SAMPLES}h", *([80] * FRAME_SAMPLES))
    for _ in range(8):
        engine.observe(AudioFrame(pcm16=lookback, sample_rate=16000, channel_count=1))
    loud = _loud_frame()
    started = False
    for _ in range(6):
        evt = engine.observe(loud)
        if evt.speech_start:
            started = True
            break
    assert started
    data = engine.take_utterance()
    assert len(data) >= 1024


@pytest.mark.asyncio
async def test_process_frame_async_does_not_clear_on_onset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_PIPELINE_V2", "quick_wins")
    monkeypatch.delenv("RUN_LIVE_PROVIDERS", raising=False)
    orch = PipelineOrchestrator()
    # This test isolates capture-buffer behavior. Its constant DC fixture is not
    # speech, so use the deterministic energy backend instead of neural VAD.
    orch.vad_adapter._session = None
    orch._speech_buffer.extend(b"\x01\x00" * 16)
    loud = _loud_frame()
    # Drive enough frames to trip onset (quick_wins => 4 speech frames).
    for _ in range(6):
        await orch.process_frame_async(loud)
    assert orch._capturing_speech is True
    assert len(orch._speech_buffer) > 32  # lookback preserved + new frames
