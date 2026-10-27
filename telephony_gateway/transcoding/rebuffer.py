"""Fixed-size buffers for carrier and canonical audio frames."""

from __future__ import annotations


class FixedFrameBuffer:
    """Split arbitrary byte fragments into fixed frames without losing bytes."""

    def __init__(self, frame_bytes: int) -> None:
        if frame_bytes < 1:
            raise ValueError("frame_bytes must be positive")
        self.frame_bytes = frame_bytes
        self._buffer = bytearray()

    @property
    def pending_bytes(self) -> int:
        return len(self._buffer)

    def push(self, payload: bytes) -> list[bytes]:
        self._buffer.extend(payload)
        frames: list[bytes] = []
        while len(self._buffer) >= self.frame_bytes:
            frames.append(bytes(self._buffer[: self.frame_bytes]))
            del self._buffer[: self.frame_bytes]
        return frames

    def flush(self, *, pad_byte: int = 0, pad: bool = True) -> bytes:
        if not 0 <= pad_byte <= 255:
            raise ValueError("pad_byte must fit in one byte")
        if not self._buffer:
            return b""
        remaining = bytes(self._buffer)
        self._buffer.clear()
        if not pad:
            return remaining
        return remaining + bytes([pad_byte]) * (self.frame_bytes - len(remaining))

    def discard(self) -> int:
        size = len(self._buffer)
        self._buffer.clear()
        return size


class TelephonyRebuffer:
    """Buffer PCM16 audio into canonical 512-sample frames."""

    def __init__(self, target_samples_per_frame: int = 512) -> None:
        self.target_samples = target_samples_per_frame
        self.target_bytes = target_samples_per_frame * 2  # PCM16 mono = 2 bytes/sample
        self._buffer = bytearray()

    def push(self, pcm16_bytes: bytes) -> list[bytes]:
        """Push arbitrary PCM16 and return every complete canonical frame."""
        self._buffer.extend(pcm16_bytes)
        frames: list[bytes] = []

        while len(self._buffer) >= self.target_bytes:
            frame = bytes(self._buffer[: self.target_bytes])
            del self._buffer[: self.target_bytes]
            frames.append(frame)

        return frames

    def flush(self) -> bytes:
        """Flush remaining samples, padding a nonempty partial frame with zeros."""
        if not self._buffer:
            return b""
        remaining = bytes(self._buffer)
        self._buffer.clear()
        padding = self.target_bytes - len(remaining)
        return remaining + (b"\x00" * padding)
