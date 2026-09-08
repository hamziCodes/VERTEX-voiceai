"""Unit tests for ``core.listening.pre_speech_buffer.PreSpeechRingBuffer``."""

from __future__ import annotations

from core.listening.pre_speech_buffer import PreSpeechRingBuffer

_CAPACITY_BYTES = 6400  # 200 ms @ 16 kHz PCM16
_MS300_BYTES = 300 * 16 * 2  # 9600 bytes


def test_drain_returns_last_200ms_after_300ms_push() -> None:
    buf = PreSpeechRingBuffer(capacity_bytes=_CAPACITY_BYTES)
    payload = bytes(range(256)) * (_MS300_BYTES // 256 + 1)
    buf.push(payload[:_MS300_BYTES])

    drained = buf.drain()

    assert len(drained) == _CAPACITY_BYTES
    assert drained == payload[_MS300_BYTES - _CAPACITY_BYTES : _MS300_BYTES]
    assert len(buf) == 0


def test_capacity_never_exceeds_limit() -> None:
    buf = PreSpeechRingBuffer(capacity_bytes=_CAPACITY_BYTES)
    chunk = b"\x01\x02" * 512  # 1024 bytes per push

    for _ in range(20):
        buf.push(chunk)
        assert len(buf) <= _CAPACITY_BYTES

    assert len(buf) == _CAPACITY_BYTES
