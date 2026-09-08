"""UCVE Adaptive Noise Gate — rolling RMS baseline to reject ambient room noise.

Harvested from ``Multilingual_AI_Voice_Agent`` ``vad_service.py`` AdaptiveNoiseGate.
Two-stage design: this RMS gate runs *before* Silero inference so that fans,
AC hum and idle keyboard noise never reach the (more expensive) neural VAD.

The noise floor is a rolling median of recent frame RMS values, updated only
while neither the agent nor the user is speaking, so loud speech never inflates
the baseline. A frame passes the gate when its RMS exceeds ``floor * k``.
"""

from __future__ import annotations

import statistics
from collections import deque

import numpy as np


class AdaptiveNoiseGate:
    """Rolling-median RMS gate placed ahead of neural VAD inference."""

    def __init__(
        self,
        k: float = 3.0,
        window: int = 50,
        default_floor: float = 0.015,
    ) -> None:
        self._k = float(k)
        self._window = int(window)
        self._default_floor = float(default_floor)
        self._floor = float(default_floor)
        self._history: deque[float] = deque(maxlen=self._window)

    @property
    def floor(self) -> float:
        """Current adaptive noise floor (normalized RMS in [0, 1])."""
        return self._floor

    @property
    def threshold(self) -> float:
        """RMS level a frame must exceed to pass the gate."""
        return self._floor * self._k

    @staticmethod
    def compute_rms(pcm16: bytes) -> float:
        """Normalized RMS of a PCM16 frame in the range [0, 1]."""
        if not pcm16:
            return 0.0
        samples = np.frombuffer(pcm16, dtype=np.int16).astype(np.float64)
        if samples.size == 0:
            return 0.0
        rms = float(np.sqrt(np.mean(samples * samples)))
        return rms / 32768.0

    def _update_floor(self, rms: float) -> None:
        self._history.append(rms)
        median = statistics.median(self._history) if self._history else self._default_floor
        # The floor never drops below the configured default to keep the gate
        # from collapsing to zero in a perfectly silent (digital) stream.
        self._floor = max(self._default_floor, float(median))

    def is_speech(
        self,
        pcm16: bytes,
        *,
        agent_speaking: bool = False,
        user_speaking: bool = False,
    ) -> bool:
        """Return True when the frame's energy clears the adaptive gate."""
        rms = self.compute_rms(pcm16)
        if not agent_speaking and not user_speaking:
            self._update_floor(rms)
        return rms >= self.threshold

    def reset(self) -> None:
        self._history.clear()
        self._floor = self._default_floor
