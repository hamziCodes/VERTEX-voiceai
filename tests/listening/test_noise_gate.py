"""Unit tests for ``core.listening.noise_gate.AdaptiveNoiseGate``."""

from __future__ import annotations

import struct

import pytest

from core.listening.noise_gate import AdaptiveNoiseGate
from core.types.constants import FRAME_SAMPLES

_DEFAULT_FLOOR = 0.015
_GATE_K = 3.0


def _pcm_constant_rms(normalized_rms: float) -> bytes:
    """Build a PCM16 frame whose normalized RMS equals ``normalized_rms``."""
    sample = int(normalized_rms * 32768)
    sample = max(-32767, min(32767, sample))
    return struct.pack(f"<{FRAME_SAMPLES}h", *([sample] * FRAME_SAMPLES))


def test_low_rms_frames_stabilize_floor() -> None:
    gate = AdaptiveNoiseGate(k=_GATE_K, window=50, default_floor=_DEFAULT_FLOOR)
    low = _pcm_constant_rms(0.01)

    for _ in range(50):
        gate.is_speech(low)

    assert gate.floor == _DEFAULT_FLOOR
    assert gate.threshold == pytest.approx(_DEFAULT_FLOOR * _GATE_K)


def test_rms_below_threshold_blocks() -> None:
    gate = AdaptiveNoiseGate(k=_GATE_K, window=50, default_floor=_DEFAULT_FLOOR)
    low = _pcm_constant_rms(0.01)

    for _ in range(50):
        gate.is_speech(low)

    below = _pcm_constant_rms(0.02)
    assert gate.is_speech(below) is False


def test_rms_above_threshold_passes() -> None:
    gate = AdaptiveNoiseGate(k=_GATE_K, window=50, default_floor=_DEFAULT_FLOOR)
    low = _pcm_constant_rms(0.01)

    for _ in range(50):
        gate.is_speech(low)

    above = _pcm_constant_rms(0.06)
    assert gate.is_speech(above) is True


def test_floor_frozen_when_agent_speaking() -> None:
    gate = AdaptiveNoiseGate(k=_GATE_K, window=50, default_floor=_DEFAULT_FLOOR)
    low = _pcm_constant_rms(0.01)
    high = _pcm_constant_rms(0.08)

    for _ in range(50):
        gate.is_speech(low)

    floor_before = gate.floor

    for _ in range(50):
        gate.is_speech(high, agent_speaking=True)

    assert gate.floor == floor_before
