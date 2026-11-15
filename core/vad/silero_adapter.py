"""UCVE Silero+Energy Hybrid VAD Adapter implementing BaseVADProvider."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

import numpy as np

from core.providers.interfaces.vad import BaseVADProvider, VADConfig, VADEvent
from core.types.audio import AudioFrame

logger = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).resolve().parent / "models"
_ONNX_NAME = "silero_vad.onnx"
_MAX_SILERO_BYTES = 512 * 1024
_SILERO_CONTEXT_SAMPLES_16K = 64
_SHARED_SESSION_LOCK = threading.Lock()
_SHARED_ONNX_SESSION: Any | None = None
_SHARED_LOAD_ATTEMPTED = False


def _load_shared_onnx_session(model_path: Path) -> Any | None:
    """Load the immutable ONNX graph once; recurrent state remains per adapter."""
    global _SHARED_LOAD_ATTEMPTED, _SHARED_ONNX_SESSION
    with _SHARED_SESSION_LOCK:
        if _SHARED_LOAD_ATTEMPTED:
            return _SHARED_ONNX_SESSION
        _SHARED_LOAD_ATTEMPTED = True
        try:
            import onnxruntime as ort

            _SHARED_ONNX_SESSION = ort.InferenceSession(
                str(model_path), providers=["CPUExecutionProvider"]
            )
            try:
                import torch

                torch.set_num_threads(1)
            except Exception:
                pass
        except Exception as exc:
            logger.warning(
                "Silero ONNX unavailable; using energy fallback: %s", exc
            )
            _SHARED_ONNX_SESSION = None
        return _SHARED_ONNX_SESSION


def shared_model_status() -> str:
    """Return ``loaded``, ``unavailable`` or ``missing`` for readiness checks."""
    model_path = _MODEL_DIR / _ONNX_NAME
    if not model_path.is_file():
        return "missing"
    session = _load_shared_onnx_session(model_path)
    return "loaded" if session is not None else "unavailable"


class SileroVADAdapter(BaseVADProvider):
    """Silero VAD (ONNX when model present) with numpy RMS energy fallback.

    Uses dual-counter hysteresis: ``speech_start`` fires only after
    ``min_speech_frames`` consecutive speech frames while idle, and
    ``speech_end`` only after ``min_silence_frames`` consecutive silence frames
    while speaking. This prevents flicker and gives conversational endpointing.
    """

    def __init__(self, config: VADConfig | None = None) -> None:
        self.config = config or VADConfig()
        self.energy_threshold_db: float = -45.0
        self._is_speaking: bool = False
        self._session = None
        self._backend = "energy"
        self._silero_state: np.ndarray | None = None
        self._silero_context: np.ndarray | None = None
        self._onset_frames = 0
        self._silence_frames = 0
        self._min_speech_frames = self.config.min_speech_frames
        self._min_silence_frames = self.config.min_silence_frames
        model_path = _MODEL_DIR / _ONNX_NAME
        if model_path.is_file():
            self._session = _load_shared_onnx_session(model_path)
            if self._session is not None:
                self._backend = "silero_onnx"

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def backend(self) -> str:
        return self._backend

    def configure(
        self,
        *,
        min_speech_frames: int | None = None,
        min_silence_frames: int | None = None,
        threshold: float | None = None,
    ) -> None:
        """Apply timing/threshold overrides (used by the V2 ``vad_timing`` flag)."""
        if min_speech_frames is not None:
            self._min_speech_frames = max(1, int(min_speech_frames))
        if min_silence_frames is not None:
            self._min_silence_frames = max(1, int(min_silence_frames))
        if threshold is not None:
            self.config.threshold = float(threshold)

    def health_check(self) -> bool:
        return True

    def reset(self) -> None:
        self._is_speaking = False
        self._onset_frames = 0
        self._silence_frames = 0
        self._silero_state = None
        self._silero_context = None

    def process_frame(self, frame: AudioFrame) -> VADEvent:
        """Process a single 16kHz PCM audio frame and return VADEvent."""
        if not frame.pcm16:
            return VADEvent(speech_start=False, speech_end=False, probability=0.0)

        expected_bytes = self.config.window_samples * 2
        if (
            self._session is not None
            and len(frame.pcm16) == expected_bytes
            and len(frame.pcm16) <= _MAX_SILERO_BYTES
            and frame.sample_rate == self.config.sample_rate
        ):
            try:
                samples = (
                    np.frombuffer(frame.pcm16, dtype=np.int16)
                    .astype(np.float32)[np.newaxis, :]
                    / 32768.0
                )
                if self._silero_context is None:
                    self._silero_context = np.zeros(
                        (1, _SILERO_CONTEXT_SAMPLES_16K), dtype=np.float32
                    )
                model_input = np.concatenate((self._silero_context, samples), axis=1)
                inp_name = self._session.get_inputs()[0].name
                ort_inputs: dict[str, np.ndarray] = {inp_name: model_input}
                if len(self._session.get_inputs()) > 1:
                    if self._silero_state is None:
                        self._silero_state = np.zeros((2, 1, 128), dtype=np.float32)
                    ort_inputs[self._session.get_inputs()[1].name] = self._silero_state
                if len(self._session.get_inputs()) > 2:
                    ort_inputs[self._session.get_inputs()[2].name] = np.array(
                        16000, dtype=np.int64
                    )
                outs = self._session.run(None, ort_inputs)
                if len(outs) > 1:
                    self._silero_state = outs[1]
                self._silero_context = samples[:, -_SILERO_CONTEXT_SAMPLES_16K:]
                prob = float(np.asarray(outs[0]).reshape(-1)[0])
                return self._apply_hysteresis(prob)
            except Exception as exc:
                logger.debug("Silero frame failed; energy fallback: %s", exc)

        return self._energy_vad(frame)

    def _apply_hysteresis(self, prob: float) -> VADEvent:
        """Dual-counter hysteresis over per-frame speech probability."""
        is_speech = prob >= self.config.threshold
        speech_start = False
        speech_end = False

        if is_speech:
            self._onset_frames += 1
            self._silence_frames = 0
            if not self._is_speaking and self._onset_frames >= self._min_speech_frames:
                self._is_speaking = True
                speech_start = True
        else:
            self._silence_frames += 1
            self._onset_frames = 0
            if self._is_speaking and self._silence_frames >= self._min_silence_frames:
                self._is_speaking = False
                speech_end = True

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
        return self._apply_hysteresis(prob)
