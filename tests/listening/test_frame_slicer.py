"""Unit tests for ``core.listening.frame_slicer.FrameSlicer``."""

from __future__ import annotations

from core.listening.frame_slicer import FrameSlicer
from core.types.constants import FRAME_BYTES


def test_empty_input_returns_no_frames() -> None:
    slicer = FrameSlicer(frame_bytes=FRAME_BYTES)

    assert slicer.push(b"") == []
    assert slicer.push(None) == []
    assert slicer.pending_bytes == 0


def test_exactly_one_frame_emits_and_clears_buffer() -> None:
    slicer = FrameSlicer(frame_bytes=FRAME_BYTES)
    chunk = bytes(FRAME_BYTES)

    frames = slicer.push(chunk)

    assert len(frames) == 1
    assert frames[0] == chunk
    assert slicer.pending_bytes == 0


def test_partial_remainder_held_after_one_full_frame() -> None:
    slicer = FrameSlicer(frame_bytes=FRAME_BYTES)
    chunk = bytes(FRAME_BYTES + 500)

    frames = slicer.push(chunk)

    assert len(frames) == 1
    assert len(frames[0]) == FRAME_BYTES
    assert slicer.pending_bytes == 500


def test_multiple_frames_with_remainder() -> None:
    slicer = FrameSlicer(frame_bytes=FRAME_BYTES)
    chunk = bytes(5000)

    frames = slicer.push(chunk)

    assert len(frames) == 4
    assert all(len(f) == FRAME_BYTES for f in frames)
    # 5000 - 4 * 1024 = 904 bytes held (plan §9.2 typo says 976)
    assert slicer.pending_bytes == 904
