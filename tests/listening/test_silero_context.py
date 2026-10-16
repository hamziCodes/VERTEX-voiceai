"""Regression tests for the bundled Silero ONNX streaming contract."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.providers.interfaces.vad import VADConfig
from core.types.audio import AudioFrame
from core.types.constants import FRAME_SAMPLES
from core.vad.silero_adapter import SileroVADAdapter


@dataclass
class _Input:
    name: str


class _RecordingSession:
    def __init__(self) -> None:
        self.inputs: list[np.ndarray] = []

    def get_inputs(self) -> list[_Input]:
        return [_Input("input"), _Input("state"), _Input("sr")]

    def run(
        self, _outputs: object, values: dict[str, np.ndarray]
    ) -> list[np.ndarray]:
        self.inputs.append(values["input"].copy())
        return [
            np.array([[0.9]], dtype=np.float32),
            np.ones((2, 1, 128), dtype=np.float32),
        ]


def _frame(value: int, samples: int = FRAME_SAMPLES) -> AudioFrame:
    pcm = np.full(samples, value, dtype=np.int16).tobytes()
    return AudioFrame(pcm16=pcm, sample_rate=16000, channel_count=1)


def test_silero_prepends_64_sample_context_and_rolls_it_forward() -> None:
    adapter = SileroVADAdapter(
        VADConfig(min_speech_frames=1, min_silence_frames=1)
    )
    session = _RecordingSession()
    adapter._session = session

    adapter.process_frame(_frame(1000))
    adapter.process_frame(_frame(2000))

    assert session.inputs[0].shape == (1, 576)
    assert np.count_nonzero(session.inputs[0][:, :64]) == 0
    expected_context = np.full((1, 64), 1000 / 32768.0, dtype=np.float32)
    np.testing.assert_allclose(session.inputs[1][:, :64], expected_context)


def test_silero_reset_clears_context_and_recurrent_state() -> None:
    adapter = SileroVADAdapter(
        VADConfig(min_speech_frames=1, min_silence_frames=1)
    )
    session = _RecordingSession()
    adapter._session = session
    adapter.process_frame(_frame(1000))

    adapter.reset()
    adapter.process_frame(_frame(2000))

    assert np.count_nonzero(session.inputs[1][:, :64]) == 0


def test_noncanonical_frame_uses_energy_fallback_without_calling_onnx() -> None:
    adapter = SileroVADAdapter(
        VADConfig(min_speech_frames=1, min_silence_frames=1)
    )
    session = _RecordingSession()
    adapter._session = session

    event = adapter.process_frame(_frame(12000, samples=320))

    assert session.inputs == []
    assert event.speech_start is True
