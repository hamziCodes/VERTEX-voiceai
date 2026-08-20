"""Phase 01: Canonical Audio Types and Frame Contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def audio_types_module():
    try:
        from core.types import audio  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 01 implementation pending: {exc}")
    return audio


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_01_canonical_audio_types_and_frame_contracts.md"
    )
    assert plan.is_file()


def test_audio_frame_rejects_odd_pcm_length(audio_types_module) -> None:
    AudioFrame = audio_types_module.AudioFrame
    with pytest.raises((ValueError, TypeError)):
        AudioFrame(
            pcm16=b"\x00\x01\x00",  # odd length
            sample_rate=16000,
            timestamp_ms=0.0,
            sequence=0,
        )


def test_audio_frame_accepts_valid_pcm(audio_types_module) -> None:
    AudioFrame = audio_types_module.AudioFrame
    frame = AudioFrame(
        pcm16=b"\x00" * 1024,
        sample_rate=16000,
        timestamp_ms=1.0,
        sequence=1,
    )
    assert len(frame.pcm16) == 1024
    assert frame.sample_rate == 16000


def test_resampler_8k_to_16k_output_length(audio_types_module) -> None:
    Resampler = audio_types_module.Resampler
    resampler = Resampler(source_rate=8000, target_rate=16000)
    pcm_8k = b"\x00\x01" * 160  # 320 bytes = 160 samples @ 16-bit
    out = resampler.process(pcm_8k)
    # Expect ~2x samples (within ±2 bytes for alignment)
    assert abs(len(out) - len(pcm_8k) * 2) <= 2


def test_control_event_json_round_trip() -> None:
    from core.types.events import ControlEvent, ControlEventType

    event = ControlEvent(
        event_type=ControlEventType.PLAYBACK_STARTED,
        timestamp_ms=123.45,
        payload={"stream_id": "test_1"},
    )
    json_str = event.to_json()
    recovered = ControlEvent.from_json(json_str)
    assert recovered.event_type == ControlEventType.PLAYBACK_STARTED
    assert recovered.timestamp_ms == 123.45
    assert recovered.payload == {"stream_id": "test_1"}


def test_audio_frame_frozen_immutability(audio_types_module) -> None:
    AudioFrame = audio_types_module.AudioFrame
    frame = AudioFrame(
        pcm16=b"\x00\x00" * 16,
        sample_rate=16000,
        timestamp_ms=10.0,
        sequence=1,
    )
    with pytest.raises(AttributeError):
        frame.sequence = 2  # type: ignore

