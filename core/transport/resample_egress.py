"""Stateful PCM16 egress resampling with continuous fractional phase."""

from __future__ import annotations

import numpy as np


class StreamingEgressResampler:
    """Band-limited mono PCM16 resampler safe across arbitrary byte chunks."""

    _RADIUS = 24
    _MAX_OUTPUT_BATCH = 4096

    def __init__(
        self, source_sample_rate: int, target_sample_rate: int = 16000
    ) -> None:
        if source_sample_rate <= 0 or target_sample_rate <= 0:
            raise ValueError("Sample rates must be positive.")
        self.source_rate = int(source_sample_rate)
        self.target_rate = int(target_sample_rate)
        self._byte_carry = b""
        self._samples = np.empty(0, dtype=np.float64)
        self._output_index = 0
        self._flushed = False

    def process(self, pcm_bytes: bytes) -> bytes:
        if self._flushed:
            raise RuntimeError("Cannot process audio after flush().")
        data = self._byte_carry + pcm_bytes
        even_length = len(data) - (len(data) % 2)
        self._byte_carry = data[even_length:]
        if even_length:
            incoming = np.frombuffer(data[:even_length], dtype="<i2").astype(np.float64)
            self._samples = np.concatenate((self._samples, incoming))
        return self._render(flushing=False)

    def flush(self) -> bytes:
        if self._flushed:
            return b""
        self._flushed = True
        self._byte_carry = b""
        return self._render(flushing=True)

    def _render(self, *, flushing: bool) -> bytes:
        sample_count = len(self._samples)
        if sample_count == 0:
            return b""
        if self.source_rate == self.target_rate:
            limit = sample_count
        elif flushing:
            limit = round(sample_count * self.target_rate / self.source_rate)
        else:
            available_position = sample_count - 1 - self._RADIUS
            limit = max(
                0,
                int(np.floor(available_position * self.target_rate / self.source_rate))
                + 1,
            )
        if limit <= self._output_index:
            return b""

        if self.source_rate == self.target_rate:
            result = self._samples[self._output_index : limit]
            self._output_index = limit
            return np.clip(np.round(result), -32768, 32767).astype("<i2").tobytes()

        ratio = self.source_rate / self.target_rate
        cutoff = min(1.0, self.target_rate / self.source_rate) * 0.94
        offsets = np.arange(-self._RADIUS + 1, self._RADIUS + 1)
        batches: list[np.ndarray] = []
        for start in range(self._output_index, limit, self._MAX_OUTPUT_BATCH):
            end = min(limit, start + self._MAX_OUTPUT_BATCH)
            positions = np.arange(start, end, dtype=np.float64) * ratio
            centers = np.floor(positions).astype(np.int64)
            indices = centers[:, None] + offsets[None, :]
            distance = indices.astype(np.float64) - positions[:, None]
            window = 0.5 + 0.5 * np.cos(np.pi * distance / self._RADIUS)
            window[np.abs(distance) >= self._RADIUS] = 0.0
            kernel = cutoff * np.sinc(cutoff * distance) * window
            clipped = np.clip(indices, 0, sample_count - 1)
            weights = kernel.sum(axis=1)
            weighted = (self._samples[clipped] * kernel).sum(axis=1)
            fallback = self._samples[np.clip(centers, 0, sample_count - 1)]
            batches.append(
                np.divide(
                    weighted,
                    weights,
                    out=fallback.copy(),
                    where=np.abs(weights) > 1e-12,
                )
            )
        output = np.concatenate(batches)
        self._output_index = limit
        return np.clip(np.round(output), -32768, 32767).astype("<i2").tobytes()


class EgressResampler:
    """Compatibility facade for one-shot PCM16 conversion to 16 kHz."""

    @classmethod
    def resample_to_16k(
        cls, pcm_bytes: bytes, source_sample_rate: int = 24000
    ) -> bytes:
        converter = StreamingEgressResampler(source_sample_rate, 16000)
        return converter.process(pcm_bytes) + converter.flush()
