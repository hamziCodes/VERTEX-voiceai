"""UCVE Silero+Energy Hybrid VAD Adapter implementing BaseVADProvider."""

from __future__ import annotations

import math
from pathlib import Path

from core.providers.interfaces.vad import BaseVADProvider, VADConfig, VADEvent
from core.types.audio import AudioFrame

_MODEL_DIR = Path(__file__).resolve().parent / "models"
_ONNX_NAME = "silero_vad.onnx"


class SileroVADAdapter(BaseVADProvider):
    """Silero VAD (ONNX when model present) with RMS energy fallback."""

    def __init__(self, config: VADConfig | None = None) -> None:
        self.config = config or VADConfig()
        self.energy_threshold_db: float = -45.0
        self._is_speaking: bool = False
        self._session = None
        self._backend = "energy"
        model_path = _MODEL_DIR / _ONNX_NAME
        if model_path.is_file():
            try:
                import onnxruntime as ort

                self._session = ort.InferenceSession(
                    str(model_path), providers=["CPUExecutionProvider"]
                )
                self._backend = "silero_onnx"
            except Exception:
                self._session = None
                self._backend = "energy"

    def health_check(self) -> bool:
        return True

    def reset(self) -> None:
        self._is_speaking = False

    def process_frame(self, frame: AudioFrame) -> VADEvent:
        """Process a single 16kHz PCM audio frame and return VADEvent."""
        if not frame.pcm16:
            return VADEvent(speech_start=False, speech_end=False, probability=0.0)

        if self._session is not None:
            try:
                import numpy as np

                samples = np.frombuffer(frame.pcm16, dtype=np.int16).astype(np.float32) / 32768.0
                # Silero expects specific window sizes; fall back on shape mismatch
                ort_inputs = {self._session.get_inputs()[0].name: samples[np.newaxis, :]}
                outs = self._session.run(None, ort_inputs)
                prob = float(outs[0].reshape(-1)[0])
                is_speech = prob >= 0.5
                speech_start = is_speech and not self._is_speaking
                speech_end = not is_speech and self._is_speaking
                self._is_speaking = is_speech
                return VADEvent(
                    speech_start=speech_start, speech_end=speech_end, probability=prob
                )
            except Exception:
                pass

        return self._energy_vad(frame)

    def _energy_vad(self, frame: AudioFrame) -> VADEvent:
        num_samples = len(frame.pcm16) // 2
        if num_samples == 0:
            return VADEvent(speech_start=False, speech_end=False, probability=0.0)

        sum_sq = 0
        for i in range(0, len(frame.pcm16) - 1, 2):
            sample = int.from_bytes(frame.pcm16[i : i + 2], byteorder="little", signed=True)
            sum_sq += sample * sample

        rms = math.sqrt(sum_sq / num_samples)
        db = 20 * math.log10(max(rms, 1.0)) - 90.0
        is_speech = db > self.energy_threshold_db
        prob = 0.95 if is_speech else 0.05
        speech_start = is_speech and not self._is_speaking
        speech_end = not is_speech and self._is_speaking
        self._is_speaking = is_speech
        return VADEvent(speech_start=speech_start, speech_end=speech_end, probability=prob)
