import struct
import math
import logging
import asyncio
import collections
import statistics
import contextlib
import threading
import glob
import os
from typing import Callable, Awaitable
import numpy as np
import torch

logger = logging.getLogger(__name__)

_TORCH_THREADS_CONFIGURED = False

def configure_torch_threads() -> None:
    global _TORCH_THREADS_CONFIGURED
    if not _TORCH_THREADS_CONFIGURED:
        try:
            import torch
            torch.set_num_threads(1)
            _TORCH_THREADS_CONFIGURED = True
            logger.info("[VAD] PyTorch global threads configured to 1.")
        except Exception as e:
            logger.error(f"[VAD] Failed to configure PyTorch threads: {e}")

def find_silero_jit_path() -> str:
    import torch
    import glob
    import os
    hub_dir = torch.hub.get_dir()
    # Search recursively inside torch hub directory
    pattern = os.path.join(hub_dir, "**", "silero_vad.jit")
    matches = glob.glob(pattern, recursive=True)
    if matches:
        return matches[0]
    raise FileNotFoundError("silero_vad.jit not found in torch hub directory")

class SileroModelPool:
    def __init__(self) -> None:
        self._models = []
        self._lock = threading.Lock()
        self._jit_path = None

    def initialize(self, first_model, jit_path: str) -> None:
        with self._lock:
            self._jit_path = jit_path
            if first_model is not None:
                self._models.append(first_model)
            logger.info(f"[VAD] Model pool initialized with cached model path: {self._jit_path}")

    def checkout(self):
        with self._lock:
            if self._models:
                model = self._models.pop()
                logger.debug(f"[VAD] Checked out model from pool. Remaining: {len(self._models)}")
                return model
            
            # If empty, load a new instance lazily
            if self._jit_path is None:
                try:
                    self._jit_path = find_silero_jit_path()
                except Exception as e:
                    logger.error(f"[VAD] Failed to find jit path during checkout: {e}")
                    raise
            
            logger.info("[VAD] Model pool empty. Loading a new Silero instance lazily...")
            import torch
            model = torch.jit.load(self._jit_path)
            model.eval()
            return model

    def checkin(self, model) -> None:
        if model is None:
            return
        try:
            if hasattr(model, 'reset_states'):
                model.reset_states()
        except Exception as e:
            logger.error(f"[VAD] Failed to reset model states during checkin: {e}")
            
        with self._lock:
            self._models.append(model)
            logger.debug(f"[VAD] Checked in model to pool. Pool size: {len(self._models)}")

_MODEL_POOL = SileroModelPool()

def get_model_pool() -> SileroModelPool:
    return _MODEL_POOL

SILERO_FRAME_DURATION_MS = 32  # 512 samples @ 16000Hz
ENERGY_FRAME_DURATION_MS = 20  # 20ms frames


class AdaptiveNoiseGate:
    """
    Tracks rolling window baseline noise during call silence to dynamically adapt VAD energy threshold.
    """
    def __init__(self, k: float = 3.0, window: int = 50, default_floor: float = 0.015) -> None:
        self._floor_samples = collections.deque(maxlen=window)
        self.k = k
        self.default_floor = default_floor

    def update_floor(self, rms: float, is_agent_speaking: bool) -> None:
        if not is_agent_speaking:
            self._floor_samples.append(rms)

    @property
    def floor(self) -> float:
        return statistics.median(self._floor_samples) if self._floor_samples else self.default_floor

    def is_above_floor(self, rms: float) -> bool:
        threshold = max(0.005, self.floor * self.k)
        return rms > threshold


class EnergyVADProcessor:
    """
    Zero-dependency, local RMS (Root Mean Square) energy-based VAD.
    Uses an AdaptiveNoiseGate to automatically adjust sensitivity to ambient noise.
    """
    def __init__(
        self,
        on_speech_start: Callable[[], Awaitable[None]],
        on_speech_end: Callable[[], Awaitable[None]],
        is_agent_speaking_fn: Callable[[], bool],
        threshold: float = 0.015,
        speech_frames_threshold: int = 3,
        silence_frames_threshold: int = 15,
        frame_duration_ms: int = 20,
        sample_rate: int = 16000,
        noise_gate_k: float = 3.0,
        noise_gate_window: int = 50
    ) -> None:
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end
        self.is_agent_speaking_fn = is_agent_speaking_fn
        
        self.noise_gate = AdaptiveNoiseGate(k=noise_gate_k, window=noise_gate_window, default_floor=threshold)
        self.speech_frames_threshold = speech_frames_threshold
        self.silence_frames_threshold = silence_frames_threshold
        
        self.bytes_per_frame = int(sample_rate * (frame_duration_ms / 1000) * 2)
        self.is_speech_active = False
        self.speech_frames_counter = 0
        self.silence_frames_counter = 0
        self._buffer = b''

    def update_thresholds(self, threshold: float, speech_duration_ms: int, silence_duration_ms: int) -> None:
        self.noise_gate.default_floor = threshold
        self.speech_frames_threshold = max(1, int(speech_duration_ms / ENERGY_FRAME_DURATION_MS))
        self.silence_frames_threshold = max(1, int(silence_duration_ms / ENERGY_FRAME_DURATION_MS))
        logger.info(f"[VAD] EnergyVAD thresholds updated: threshold={threshold:.4f}, speech_frames={self.speech_frames_threshold}, silence_frames={self.silence_frames_threshold}")

    async def process_audio(self, chunk: bytes) -> None:
        self._buffer += chunk
        
        while len(self._buffer) >= self.bytes_per_frame:
            frame = self._buffer[:self.bytes_per_frame]
            self._buffer = self._buffer[self.bytes_per_frame:]
            
            try:
                shorts = np.frombuffer(frame, dtype=np.int16)
            except Exception as e:
                logger.error(f"[VAD] Energy frame unpacking error: {e}")
                continue
                
            if len(shorts) == 0:
                continue
                
            audio_float = shorts.astype(np.float32) / 32768.0
            rms = np.sqrt(np.mean(audio_float ** 2)).item()
            
            self.noise_gate.update_floor(rms, self.is_agent_speaking_fn())
            is_speech_frame = self.noise_gate.is_above_floor(rms)
            
            if is_speech_frame:
                self.silence_frames_counter = 0
                if not self.is_speech_active:
                    self.speech_frames_counter += 1
                    if self.speech_frames_counter >= self.speech_frames_threshold:
                        self.is_speech_active = True
                        logger.info(f"[VAD] Energy speech START (RMS: {rms:.4f})")
                        try:
                            await self.on_speech_start()
                        except Exception as e:
                            logger.error(f"Error in on_speech_start callback: {e}")
            else:
                self.speech_frames_counter = 0
                if self.is_speech_active:
                    self.silence_frames_counter += 1
                    if self.silence_frames_counter >= self.silence_frames_threshold:
                        self.is_speech_active = False
                        logger.info(f"[VAD] Energy speech END")
                        try:
                            await self.on_speech_end()
                        except Exception as e:
                            logger.error(f"Error in on_speech_end callback: {e}")

    def reset(self) -> None:
        self.is_speech_active = False
        self.speech_frames_counter = 0
        self.silence_frames_counter = 0
        self._buffer = b''


class SileroVADProcessor:
    """
    Silero VAD implementation using PyTorch.
    Downloads model via PyTorch Hub and processes frames in a threadpool executor.
    """
    def __init__(
        self,
        on_speech_start: Callable[[], Awaitable[None]],
        on_speech_end: Callable[[], Awaitable[None]],
        is_agent_speaking_fn: Callable[[], bool],
        threshold: float = 0.5,
        energy_threshold: float = 0.015,
        speech_duration_ms: int = 100,
        silence_duration_ms: int = 350,
        sample_rate: int = 16000,
        noise_gate_k: float = 3.0,
        noise_gate_window: int = 50
    ) -> None:
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end
        self.is_agent_speaking_fn = is_agent_speaking_fn
        self.threshold = threshold
        self.sample_rate = sample_rate
        
        self.model = _MODEL_POOL.checkout()
        
        self.frame_size = 512
        self.bytes_per_frame = self.frame_size * 2
        
        self.is_speech_active = False
        self.speech_frames_threshold = max(1, int(speech_duration_ms / SILERO_FRAME_DURATION_MS))
        self.silence_frames_threshold = max(1, int(silence_duration_ms / SILERO_FRAME_DURATION_MS))
        
        self.speech_frames_counter = 0
        self.silence_frames_counter = 0
        self._buffer = b''
        self._loop = None
        
        # Dynamic energy/volume noise gate to ignore background room fan hums or non-vocal hums
        self.noise_gate = AdaptiveNoiseGate(k=noise_gate_k, window=noise_gate_window, default_floor=energy_threshold)
        
        if hasattr(self.model, 'reset_states'):
            self.model.reset_states()

    def update_thresholds(self, threshold: float, speech_duration_ms: int, silence_duration_ms: int) -> None:
        self.threshold = threshold
        self.speech_frames_threshold = max(1, int(speech_duration_ms / SILERO_FRAME_DURATION_MS))
        self.silence_frames_threshold = max(1, int(silence_duration_ms / SILERO_FRAME_DURATION_MS))
        logger.info(f"[VAD] SileroVAD thresholds updated: threshold={threshold:.4f}, speech_frames={self.speech_frames_threshold}, silence_frames={self.silence_frames_threshold}")

    def reset(self) -> None:
        self.is_speech_active = False
        self.speech_frames_counter = 0
        self.silence_frames_counter = 0
        self._buffer = b''
        if hasattr(self, 'model') and hasattr(self.model, 'reset_states'):
            try:
                self.model.reset_states()
            except Exception:
                pass

    def shutdown(self) -> None:
        if hasattr(self, 'model') and self.model is not None:
            _MODEL_POOL.checkin(self.model)
            self.model = None

    def __del__(self) -> None:
        try:
            self.shutdown()
        except Exception:
            pass

    def _infer(self, frame: bytes) -> float:
        shorts = np.frombuffer(frame, dtype=np.int16)
        audio_float = shorts.astype(np.float32) / 32768.0
        input_tensor = torch.from_numpy(audio_float)
        with torch.no_grad():
            return self.model(input_tensor.unsqueeze(0), self.sample_rate).item()

    async def process_audio(self, chunk: bytes) -> None:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
            
        self._buffer += chunk
        
        while len(self._buffer) >= self.bytes_per_frame:
            frame = self._buffer[:self.bytes_per_frame]
            self._buffer = self._buffer[self.bytes_per_frame:]
            
            try:
                shorts = np.frombuffer(frame, dtype=np.int16)
            except Exception as e:
                logger.error(f"[VAD] Silero frame RMS unpacking error: {e}")
                continue
                
            if len(shorts) == 0:
                continue
                
            audio_float = shorts.astype(np.float32) / 32768.0
            rms = np.sqrt(np.mean(audio_float ** 2)).item()
            
            # Update the noise floor dynamically during non-vocal background periods
            self.noise_gate.update_floor(rms, self.is_agent_speaking_fn())
            
            # First level check: Amplitude energy gate must exceed baseline noise floor
            is_above_floor = self.noise_gate.is_above_floor(rms)
            
            is_speech_frame = False
            speech_prob = 0.0
            
            if is_above_floor:
                try:
                    # Offload Torch CPU calculations to avoid stalling asyncio loop
                    speech_prob = await self._loop.run_in_executor(None, self._infer, frame)
                    is_speech_frame = speech_prob > self.threshold
                except Exception as e:
                    logger.error(f"[VAD] Offloaded Silero inference error: {e}")
                    continue
            
            if is_speech_frame:
                self.silence_frames_counter = 0
                if not self.is_speech_active:
                    self.speech_frames_counter += 1
                    if self.speech_frames_counter >= self.speech_frames_threshold:
                        self.is_speech_active = True
                        logger.info(f"[VAD] Silero speech START (prob: {speech_prob:.4f}, RMS: {rms:.4f})")
                        try:
                            await self.on_speech_start()
                        except Exception as e:
                            logger.error(f"Error in on_speech_start callback: {e}")
            else:
                self.speech_frames_counter = 0
                if self.is_speech_active:
                    self.silence_frames_counter += 1
                    if self.silence_frames_counter >= self.silence_frames_threshold:
                        self.is_speech_active = False
                        logger.info(f"[VAD] Silero speech END")
                        try:
                            await self.on_speech_end()
                        except Exception as e:
                            logger.error(f"Error in on_speech_end callback: {e}")


class VADProcessor:
    """
    Unified VAD Processor wrapper running inside a single background consumer task.
    Prevents parallel executor pool oversubscription by queueing and sequencing frame inferences.
    """
    def __init__(
        self,
        on_speech_start: Callable[[], Awaitable[None]],
        on_speech_end: Callable[[], Awaitable[None]],
        is_agent_speaking_fn: Callable[[], bool],
        threshold: float = 0.5,
        energy_threshold: float = 0.015,
        speech_duration_ms: int = 100,
        silence_duration_ms: int = 350,
        sample_rate: int = 16000,
        noise_gate_k: float = 3.0,
        noise_gate_window: int = 50
    ) -> None:
        self._processor = None
        self._queue = asyncio.Queue(maxsize=200)
        self._worker_task = None
        self._running = True
        self._reset_generation = 0
        
        try:
            logger.info("[VAD] Attempting to load Silero VAD via PyTorch Hub...")
            self._processor = SileroVADProcessor(
                on_speech_start=on_speech_start,
                on_speech_end=on_speech_end,
                is_agent_speaking_fn=is_agent_speaking_fn,
                threshold=threshold,
                energy_threshold=energy_threshold,
                speech_duration_ms=speech_duration_ms,
                silence_duration_ms=silence_duration_ms,
                sample_rate=sample_rate,
                noise_gate_k=noise_gate_k,
                noise_gate_window=noise_gate_window
            )
            logger.info("[VAD] Silero VAD loaded successfully.")
        except Exception as e:
            logger.warning(f"[VAD] Failed to load Silero VAD ({e}). Falling back to local EnergyVADProcessor.")
            self._processor = EnergyVADProcessor(
                on_speech_start=on_speech_start,
                on_speech_end=on_speech_end,
                is_agent_speaking_fn=is_agent_speaking_fn,
                threshold=energy_threshold,
                speech_frames_threshold=max(1, int(speech_duration_ms / ENERGY_FRAME_DURATION_MS)),
                silence_frames_threshold=max(1, int(silence_duration_ms / ENERGY_FRAME_DURATION_MS)),
                sample_rate=sample_rate,
                noise_gate_k=noise_gate_k,
                noise_gate_window=noise_gate_window
            )

        self._worker_task = asyncio.create_task(self._vad_worker())

    async def _vad_worker(self) -> None:
        """Sequentially consumes and processes audio chunks from the queue."""
        logger.debug("[VAD] Background consumer task started.")
        while self._running:
            try:
                item = await self._queue.get()
                if item is None:
                    self._queue.task_done()
                    break
                chunk, gen = item
                if gen != self._reset_generation:
                    self._queue.task_done()
                    continue
                await self._processor.process_audio(chunk)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[VAD] Error in VAD worker loop: {e}")
        logger.debug("[VAD] Background consumer task stopped.")

    async def process_audio(self, chunk: bytes) -> None:
        """Enqueue audio chunk non-blockingly."""
        if not self._running:
            return
        try:
            self._queue.put_nowait((chunk, self._reset_generation))
        except asyncio.QueueFull:
            # Backpressure: drop the chunk if the queue is overloaded
            logger.warning("[VAD] Queue full - dropping chunk to prevent memory bloat.")

    def reset(self) -> None:
        self._reset_generation += 1
        # Flush VAD worker queue and reset internal buffers
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break
        self._processor.reset()

    def update_thresholds(self, threshold: float, speech_duration_ms: int, silence_duration_ms: int) -> None:
        if self._processor:
            self._processor.update_thresholds(threshold, speech_duration_ms, silence_duration_ms)

    @property
    def is_speech_active(self) -> bool:
        if self._processor:
            return self._processor.is_speech_active
        return False

    async def shutdown(self) -> None:
        self._running = False
        await self._queue.put(None)
        if self._worker_task:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
        if hasattr(self._processor, 'shutdown'):
            self._processor.shutdown()
