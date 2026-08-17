import time
import logging
import numpy as np
import torch
from backend.app.core.config.config import get_settings

logger = logging.getLogger(__name__)
frame_logger = logging.getLogger("vad.frames")  # isolated — see core/logging_config.py

class SileroVADService:
    """Production-ready wrapper around Silero VAD."""

    def __init__(self) -> None:
        self._cfg = get_settings()
        
        # Config-driven parameters
        self.threshold: float = self._cfg.vad_threshold
        self.sample_rate: int = self._cfg.vad_sample_rate
        self.window_size: int = self._cfg.vad_window_size_samples
        
        # Calculate frame counts required to meet duration thresholds
        self.min_speech_frames: int = max(
            1,
            int(
                (self._cfg.min_speech_duration_ms / 1000.0)
                * self.sample_rate
                / self.window_size
            ),
        )
        self.min_silence_frames: int = max(
            1,
            int(
                (self._cfg.min_silence_duration_ms / 1000.0)
                * self.sample_rate
                / self.window_size
            ),
        )

        logger.info(
            f"Initializing Silero VAD: sample_rate={self.sample_rate}, "
            f"window_size={self.window_size}, threshold={self.threshold}, "
            f"min_speech_frames={self.min_speech_frames}, "
            f"min_silence_frames={self.min_silence_frames}"
        )

        # Load Silero VAD model
        try:
            self._model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True
            )
            # Set to evaluation mode
            self._model.eval()
        except Exception as e:
            logger.error(f"Failed to load Silero VAD model via torch hub: {e}")
            raise

        # Internal audio byte buffer
        self._byte_buffer = bytearray()
        
        # State tracking variables
        self._speech_frames = 0
        self._silence_frames = 0
        self._is_speaking = False
        
        # Configure torch thread count to avoid oversubscription in worker pool
        torch.set_num_threads(1)

    @staticmethod
    def _bytes_to_tensor(data: bytes) -> torch.Tensor:
        """Converts raw PCM-16LE bytes to a normalized float32 torch tensor."""
        audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        return torch.from_numpy(audio)

    def feed(self, chunk: bytes) -> bool:
        """Adds raw PCM-16LE audio bytes and evaluates VAD state.
        
        Returns True if a transition into speaking or a sustained speech segment is detected.
        """
        t0 = time.perf_counter()
        self._byte_buffer += chunk
        
        # Process in steps of window_size (2 bytes per sample for 16-bit PCM)
        frame_byte_len = self.window_size * 2
        triggered = False

        while len(self._byte_buffer) >= frame_byte_len:
            frame_bytes = self._byte_buffer[:frame_byte_len]
            self._byte_buffer = self._byte_buffer[frame_byte_len:]

            tensor = self._bytes_to_tensor(frame_bytes)
            rms = float(np.sqrt(np.mean(tensor.numpy() ** 2))) if tensor.numel() else 0.0
            
            # Silero expects shape [batch, samples], i.e., [1, samples]
            tensor_in = tensor.unsqueeze(0)

            with torch.no_grad():
                # Silero VAD model returns speech probability
                prob = self._model(tensor_in, self.sample_rate).item()

            is_speech = prob > self.threshold

            # Every frame, unconditionally — goes ONLY to logs/vad_frames.log (and the
            # active session file if attached), never console/app.log.
            frame_logger.debug(
                f"prob={prob:.3f} rms={rms:.4f} is_speech={is_speech} "
                f"speech_frames={self._speech_frames} silence_frames={self._silence_frames} "
                f"is_speaking={self._is_speaking}"
            )

            if is_speech:
                self._speech_frames += 1
                self._silence_frames = 0
                
                # Transition to speaking if we exceed speech frames threshold
                if not self._is_speaking and self._speech_frames >= self.min_speech_frames:
                    self._is_speaking = True
                    triggered = True
                    logger.info(f"Silero VAD: SPEECH START TRIGGERED (prob={prob:.3f})")
            else:
                self._silence_frames += 1
                
                # Transition back to silence if we exceed silence frames threshold
                if self._is_speaking and self._silence_frames >= self.min_silence_frames:
                    self._is_speaking = False
                    self._speech_frames = 0
                    logger.debug("Silero VAD: Speech end detected.")

            # If currently in speaking state, we can also return True on continuous voice activity.
            # However, for barge-in, we primarily care about the transition/start of speech.
            # But the requirement asks: "trigger when the user speaks".
            # So if we detect speech start (i.e. self._is_speaking becomes True), we return True.
            
        elapsed_ms = (time.perf_counter() - t0) * 1000
        if elapsed_ms > 15:  # flag anything abnormally slow
            logger.warning(f"[VAD] slow inference: {elapsed_ms:.1f}ms for {len(chunk)}B (qsize of queue check needed)")
        if triggered:
            logger.info(f"[VAD] TRIGGERED at t={time.time():.3f}")
            
        return triggered

    def reset(self) -> None:
        """Resets the state of the VAD service."""
        self._byte_buffer.clear()
        self._speech_frames = 0
        self._silence_frames = 0
        self._is_speaking = False

_silero_healthy = True

def check_silero_status() -> bool:
    global _silero_healthy
    try:
        service = SileroVADService()
        dummy_data = b'\x00' * (service.window_size * 2)
        service.feed(dummy_data)
        _silero_healthy = True
    except Exception as e:
        logger.error(f"Silero VAD startup check failed: {e}")
        _silero_healthy = False
    return _silero_healthy

def is_silero_healthy() -> bool:
    return _silero_healthy
