"""Telephony Frame Rebuffer — Aggregates 20 ms PSTN frames into 512-sample canonical audio chunks."""

from __future__ import annotations


class TelephonyRebuffer:
    """Buffers incoming PCM16 audio bytes and yields canonical 512-sample (1024-byte) frames."""

    def __init__(self, target_samples_per_frame: int = 512) -> None:
        self.target_samples = target_samples_per_frame
        self.target_bytes = target_samples_per_frame * 2  # PCM16 mono = 2 bytes/sample
        self._buffer = bytearray()

    def push(self, pcm16_bytes: bytes) -> list[bytes]:
        """Push arbitrary PCM16 bytes and return all complete 512-sample frame blocks."""
        self._buffer.extend(pcm16_bytes)
        frames: list[bytes] = []

        while len(self._buffer) >= self.target_bytes:
            frame = bytes(self._buffer[: self.target_bytes])
            del self._buffer[: self.target_bytes]
            frames.append(frame)

        return frames

    def flush(self) -> bytes:
        """Flush any remaining buffered samples (padded with zeros to target_bytes if non-empty)."""
        if not self._buffer:
            return b""
        remaining = bytes(self._buffer)
        self._buffer.clear()
        padding = self.target_bytes - len(remaining)
        return remaining + (b"\x00" * padding)
