"""UCVE PCM16 Resampler Utility."""

from __future__ import annotations

import numpy as np

SUPPORTED_RATES: set[int] = {8000, 16000, 22050, 24000, 44100, 48000}


class Resampler:
    """PCM16LE audio resampler with one-sample carry and linear interpolation."""

    SUPPORTED_RATES = SUPPORTED_RATES

    def __init__(self, source_rate: int, target_rate: int = 16000) -> None:
        if source_rate not in self.SUPPORTED_RATES:
            raise ValueError(
                f"Unsupported source sample rate: {source_rate}. Supported: {self.SUPPORTED_RATES}"
            )
        if target_rate not in self.SUPPORTED_RATES:
            raise ValueError(
                f"Unsupported target sample rate: {target_rate}. Supported: {self.SUPPORTED_RATES}"
            )
        self.source_rate = source_rate
        self.target_rate = target_rate
        self._carry_sample: float = 0.0
        self._carry_set = False

    def process(self, pcm_bytes: bytes) -> bytes:
        """Resample mono 16-bit signed Little-Endian PCM byte sequence."""
        if len(pcm_bytes) % 2 != 0:
            raise ValueError("PCM16 input data length must be even (2 bytes per sample).")

        if self.source_rate == self.target_rate or not pcm_bytes:
            return pcm_bytes

        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float64)
        if samples.size == 0:
            return b""

        if self._carry_set:
            samples = np.concatenate(([self._carry_sample], samples))
        else:
            samples = np.concatenate(([samples[0]], samples))

        ratio = self.source_rate / self.target_rate
        n_out = int(np.floor((len(samples) - 1) / ratio))
        if n_out <= 0:
            self._carry_sample = float(samples[-1])
            self._carry_set = True
            return b""

        out_idx = np.arange(n_out, dtype=np.float64) * ratio
        idx_floor = np.floor(out_idx).astype(np.int64)
        idx_ceil = np.minimum(idx_floor + 1, len(samples) - 1)
        frac = out_idx - idx_floor
        out = samples[idx_floor] * (1.0 - frac) + samples[idx_ceil] * frac
        out = np.clip(np.round(out), -32768, 32767).astype(np.int16)

        self._carry_sample = float(samples[-1])
        self._carry_set = True
        return out.tobytes()
