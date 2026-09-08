"""UCVE Frame Slicer — normalize arbitrary WS chunk sizes into canonical frames.

Silero VAD requires exact 512-sample (1024-byte) PCM16 windows. WebSocket
ingress delivers arbitrarily sized binary messages, so this accumulator holds a
byte buffer and emits only complete canonical frames, retaining the remainder.

Harvested pattern: v3 ``silero_service.py`` byte-buffer slicer.
"""

from __future__ import annotations

from core.types.constants import FRAME_BYTES


class FrameSlicer:
    """Accumulates PCM bytes and yields complete canonical frames."""

    def __init__(self, frame_bytes: int = FRAME_BYTES) -> None:
        if frame_bytes <= 0:
            raise ValueError("frame_bytes must be positive")
        self._frame_bytes = frame_bytes
        self._buffer = bytearray()

    @property
    def frame_bytes(self) -> int:
        return self._frame_bytes

    @property
    def pending_bytes(self) -> int:
        """Number of bytes currently held (not yet a full frame)."""
        return len(self._buffer)

    def push(self, chunk: bytes | bytearray | memoryview | None) -> list[bytes]:
        """Append ``chunk`` and return every complete frame now available."""
        if not chunk:
            return []
        self._buffer.extend(chunk)
        frames: list[bytes] = []
        fb = self._frame_bytes
        while len(self._buffer) >= fb:
            frames.append(bytes(self._buffer[:fb]))
            del self._buffer[:fb]
        return frames

    def flush(self, *, pad: bool = False) -> bytes:
        """Return and clear any residual bytes.

        When ``pad`` is True the residue is zero-padded up to a full frame so it
        can still be fed to a fixed-window consumer; otherwise the raw residue is
        returned (possibly shorter than one frame).
        """
        if not self._buffer:
            return b""
        residue = bytes(self._buffer)
        self._buffer.clear()
        if pad and len(residue) < self._frame_bytes:
            residue = residue + bytes(self._frame_bytes - len(residue))
        return residue

    def reset(self) -> None:
        self._buffer.clear()
