"""Unit tests for SileroVADAdapter energy-path hysteresis."""

from __future__ import annotations

import struct

from core.providers.interfaces.vad import VADConfig
from core.types.audio import AudioFrame
from core.types.constants import FRAME_BYTES, FRAME_SAMPLES
from core.vad.silero_adapter import SileroVADAdapter

_LOUD_SAMPLE = 32767 // 2  # int16 max / 2


def _make_frame(sample_value: int) -> AudioFrame:
    pcm16 = struct.pack(f"<{FRAME_SAMPLES}h", *([sample_value] * FRAME_SAMPLES))
    assert len(pcm16) == FRAME_BYTES
    return AudioFrame(pcm16=pcm16, sample_rate=16000)


def _energy_vad(*, min_speech: int = 4, min_silence: int = 12) -> SileroVADAdapter:
    """Return a VAD adapter forced onto the numpy energy fallback path."""
    vad = SileroVADAdapter(
        VADConfig(min_speech_frames=min_speech, min_silence_frames=min_silence)
    )
    vad._session = None
    vad._backend = "energy"
    vad.configure(min_speech_frames=min_speech, min_silence_frames=min_silence)
    return vad


def test_three_loud_frames_no_speech_start() -> None:
    vad = _energy_vad()
    loud = _make_frame(_LOUD_SAMPLE)

    for _ in range(3):
        event = vad.process_frame(loud)
        assert event.speech_start is False

    assert vad.is_speaking is False


def test_four_loud_frames_triggers_speech_start() -> None:
    vad = _energy_vad()
    loud = _make_frame(_LOUD_SAMPLE)

    speech_start_seen = False
    for i in range(4):
        event = vad.process_frame(loud)
        if i == 3:
            assert event.speech_start is True
            speech_start_seen = True

    assert speech_start_seen
    assert vad.is_speaking is True


def test_eleven_silence_frames_while_speaking_no_speech_end() -> None:
    vad = _energy_vad()
    loud = _make_frame(_LOUD_SAMPLE)
    silence = _make_frame(0)

    for _ in range(4):
        vad.process_frame(loud)

    for _ in range(11):
        event = vad.process_frame(silence)
        assert event.speech_end is False

    assert vad.is_speaking is True


def test_twelfth_silence_frame_triggers_speech_end() -> None:
    vad = _energy_vad()
    loud = _make_frame(_LOUD_SAMPLE)
    silence = _make_frame(0)

    for _ in range(4):
        vad.process_frame(loud)

    speech_end_seen = False
    for i in range(12):
        event = vad.process_frame(silence)
        if i == 11:
            assert event.speech_end is True
            speech_end_seen = True

    assert speech_end_seen
    assert vad.is_speaking is False
