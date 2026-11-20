"""Canonical framing and lossless ingress/backpressure contracts."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from core.buffers.policy import INBOUND_MIC_POLICY, OverflowPolicy
from core.types.constants import FRAME_BYTES
from worker_raw.ws_session import WebSocketSessionRunner


def _runner(
    *,
    warn_ms: int = 10_000,
    events: list[dict[str, object]] | None = None,
) -> WebSocketSessionRunner:
    recorded = events if events is not None else []

    class Transport:
        async def send_control_event(self, _event_type, payload) -> None:
            recorded.append(payload)

    orchestrator = SimpleNamespace(
        listening_config=SimpleNamespace(
            ingress_backpressure_warn_ms=warn_ms
        )
    )
    return WebSocketSessionRunner(
        websocket=SimpleNamespace(),
        transport=Transport(),
        orchestrator=orchestrator,
        config=SimpleNamespace(),
    )


def test_inbound_audio_uses_blocking_policy() -> None:
    assert INBOUND_MIC_POLICY.overflow is OverflowPolicy.BLOCK


@pytest.mark.asyncio
async def test_transport_boundary_slicing_is_packet_size_invariant() -> None:
    pcm = bytes(index % 251 for index in range(FRAME_BYTES * 3 + 73))
    one_chunk = _runner()
    irregular = _runner()

    await one_chunk._enqueue_pcm(pcm)
    for start in range(0, len(pcm), 317):
        await irregular._enqueue_pcm(pcm[start : start + 317])

    frames_a = [
        one_chunk._ingress_queue.get_nowait()
        for _ in range(one_chunk._ingress_queue.qsize())
    ]
    frames_b = [
        irregular._ingress_queue.get_nowait()
        for _ in range(irregular._ingress_queue.qsize())
    ]

    assert [frame.pcm16 for frame in frames_a] == [frame.pcm16 for frame in frames_b]
    assert all(len(frame.pcm16) == FRAME_BYTES for frame in frames_a)
    assert one_chunk._frame_slicer.pending_bytes == 73
    assert irregular._frame_slicer.pending_bytes == 73


@pytest.mark.asyncio
async def test_blocking_ingress_never_drops_when_full() -> None:
    runner = _runner()
    frame = bytes(FRAME_BYTES)
    for _ in range(INBOUND_MIC_POLICY.maxsize):
        await runner._enqueue_pcm(frame)

    blocked_put = asyncio.create_task(runner._enqueue_pcm(frame))
    await asyncio.sleep(0)

    assert blocked_put.done() is False
    assert runner._ingress_queue.drop_count == 0
    runner._ingress_queue.get_nowait()
    await blocked_put
    assert runner._ingress_queue.drop_count == 0


@pytest.mark.asyncio
async def test_ingress_saturation_emits_backpressure_metric() -> None:
    events: list[dict[str, object]] = []
    runner = _runner(warn_ms=1, events=events)
    frame = bytes(FRAME_BYTES)
    for _ in range(INBOUND_MIC_POLICY.maxsize):
        await runner._enqueue_pcm(frame)

    blocked_put = asyncio.create_task(runner._enqueue_pcm(frame))
    while runner._ingress_seq <= INBOUND_MIC_POLICY.maxsize:
        await asyncio.sleep(0)
    await asyncio.sleep(0.01)
    runner._ingress_queue.get_nowait()
    await blocked_put

    assert events[-1]["kind"] == "ingress_backpressure"
    assert events[-1]["dropped_frames"] == 0
