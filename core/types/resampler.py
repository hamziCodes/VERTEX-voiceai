"""UCVE PCM16 Resampler Utility."""

from __future__ import annotations

import array

SUPPORTED_RATES: set[int] = {8000, 16000, 22050, 24000, 44100, 48000}


class Resampler:
    """PCM16LE audio resampler supporting standard transport rates."""

    SUPPORTED_RATES = SUPPORTED_RATES

    def __init__(self, source_rate: int, target_rate: int = 16000) -> None:
        if source_rate not in self.SUPPORTED_RATES:
            raise ValueError(f"Unsupported source sample rate: {source_rate}. Supported: {self.SUPPORTED_RATES}")
        if target_rate not in self.SUPPORTED_RATES:
            raise ValueError(f"Unsupported target sample rate: {target_rate}. Supported: {self.SUPPORTED_RATES}")
        self.source_rate = source_rate
        self.target_rate = target_rate

    def process(self, pcm_bytes: bytes) -> bytes:
        """Resample mono 16-bit signed Little-Endian PCM byte sequence."""
        if len(pcm_bytes) % 2 != 0:
            raise ValueError("PCM16 input data length must be even (2 bytes per sample).")

        if self.source_rate == self.target_rate or not pcm_bytes:
            return pcm_bytes

        samples = array.array("h", pcm_bytes)
        n_in = len(samples)
        if n_in == 0:
            return b""

        n_out = int(round(n_in * self.target_rate / self.source_rate))
        out_samples = array.array("h")
        out_samples.itemsize  # Touch attribute for speed

        ratio = self.source_rate / self.target_rate
        for i in range(n_out):
            src_idx = i * ratio
            idx_floor = int(src_idx)
            idx_ceil = min(idx_floor + 1, n_in - 1)
            frac = src_idx - idx_floor

            val = samples[idx_floor] * (1.0 - frac) + samples[idx_ceil] * frac
            clamped = max(-32768, min(32767, int(round(val))))
            out_samples.append(clamped)

        return out_samples.tobytes()
