"""UCVE Pre-Speech Ring Buffer — lookback audio to avoid clipping onsets.

VAD detects speech a few frames *after* it actually begins, so the first
consonant ("Hello" -> "ello") is lost unless we retain a short pre-roll. This
fixed-capacity ring buffer is fed every frame regardless of capture state and
drained onto the capture buffer at ``speech_start``.

Default capacity: 200 ms * 16 kHz * 2 bytes = 6400 bytes.
"""

from __future__ import annotations

_DEFAULT_CAPACITY_BYTES = 200 * 16 * 2  # 200 ms @ 16 kHz PCM16 = 6400 bytes


class PreSpeechRingBuffer:
    """Bounded FIFO of the most recent PCM bytes preceding VAD onset."""

    def __init__(self, capacity_bytes: int = _DEFAULT_CAPACITY_BYTES) -> None:
        if capacity_bytes <= 0:
            raise ValueError("capacity_bytes must be positive")
        self._capacity = capacity_bytes
        self._buffer = bytearray()

    @property
    def capacity_bytes(self) -> int:
        return self._capacity

    def __len__(self) -> int:
        return len(self._buffer)

    def push(self, pcm16: bytes | bytearray | memoryview | None) -> None:
        """Append a frame, evicting oldest bytes beyond capacity."""
        if not pcm16:
            return
        self._buffer.extend(pcm16)
        overflow = len(self._buffer) - self._capacity
        if overflow > 0:
            del self._buffer[:overflow]

    def peek(self) -> bytes:
        """Return the retained pre-roll without clearing it."""
        return bytes(self._buffer)

    def drain(self) -> bytes:
        """Return the retained pre-roll and clear the buffer."""
        data = bytes(self._buffer)
        self._buffer.clear()
        return data

    def reset(self) -> None:
        self._buffer.clear()
