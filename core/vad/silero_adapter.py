"""UCVE Silero+Energy Hybrid VAD Adapter implementing BaseVADProvider."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from core.providers.interfaces.vad import BaseVADProvider, VADConfig, VADEvent
from core.types.audio import AudioFrame

logger = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).resolve().parent / "models"
_ONNX_NAME = "silero_vad.onnx"
_MAX_SILERO_BYTES = 512 * 1024


class SileroVADAdapter(BaseVADProvider):
    """Silero VAD (ONNX when model present) with numpy RMS energy fallback."""

    def __init__(self, config: VADConfig | None = None) -> None:
        self.config = config or VADConfig()
        self.energy_threshold_db: float = -45.0
        self._is_speaking: bool = False
        self._session = None
        self._backend = "energy"
        self._silero_state: np.ndarray | None = None
        self._hangover_frames = 0
        self._min_speech_frames = 2
        self._min_silence_frames = 3
        model_path = _MODEL_DIR / _ONNX_NAME
        if model_path.is_file():
            try:
                import onnxruntime as ort

                self._session = ort.InferenceSession(
                    str(model_path), providers=["CPUExecutionProvider"]
                )
                self._backend = "silero_onnx"
            except Exception as exc:
                logger.warning("Silero ONNX unavailable; using energy fallback: %s", exc)
                self._session = None
                self._backend = "energy"

    def health_check(self) -> bool:
        return True

    def reset(self) -> None:
        self._is_speaking = False
        self._hangover_frames = 0
        self._silero_state = None

    def process_frame(self, frame: AudioFrame) -> VADEvent:
        """Process a single 16kHz PCM audio frame and return VADEvent."""
        if not frame.pcm16:
            return VADEvent(speech_start=False, speech_end=False, probability=0.0)

        if self._session is not None and len(frame.pcm16) <= _MAX_SILERO_BYTES:
            try:
                samples = np.frombuffer(frame.pcm16, dtype=np.int16).astype(np.float32) / 32768.0
                inp_name = self._session.get_inputs()[0].name
                ort_inputs: dict[str, np.ndarray] = {inp_name: samples[np.newaxis, :]}
                if len(self._session.get_inputs()) > 1:
                    if self._silero_state is None:
                        self._silero_state = np.zeros((2, 1, 128), dtype=np.float32)
                    ort_inputs[self._session.get_inputs()[1].name] = self._silero_state
                outs = self._session.run(None, ort_inputs)
                if len(outs) > 1:
                    self._silero_state = outs[1]
                prob = float(np.asarray(outs[0]).reshape(-1)[0])
                return self._apply_hangover(prob)
            except Exception as exc:
                logger.debug("Silero frame failed; energy fallback: %s", exc)

        return self._energy_vad(frame)

    def _apply_hangover(self, prob: float) -> VADEvent:
        is_speech = prob >= 0.5
        if is_speech:
            self._hangover_frames = 0
        else:
            self._hangover_frames += 1
        effective_speech = is_speech or (
            self._is_speaking and self._hangover_frames < self._min_silence_frames
        )
        speech_start = effective_speech and not self._is_speaking
        speech_end = not effective_speech and self._is_speaking
        if speech_start or (effective_speech and not self._is_speaking):
            self._is_speaking = True
        if speech_end:
            self._is_speaking = False
        return VADEvent(
            speech_start=speech_start,
            speech_end=speech_end,
            probability=prob,
        )

    def _energy_vad(self, frame: AudioFrame) -> VADEvent:
        samples = np.frombuffer(frame.pcm16, dtype=np.int16).astype(np.float64)
        if samples.size == 0:
            return VADEvent(speech_start=False, speech_end=False, probability=0.0)

        rms = float(np.sqrt(np.mean(samples * samples)))
        db = 20 * np.log10(max(rms, 1.0)) - 90.0
        is_speech = db > self.energy_threshold_db
        prob = 0.95 if is_speech else 0.05
        return self._apply_hangover(prob)
