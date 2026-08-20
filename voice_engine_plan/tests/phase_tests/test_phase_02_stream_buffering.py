"""Phase 02: Stream Buffering and Backpressure Policy."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def buffers_module():
    try:
        from core import buffers  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 02 implementation pending: {exc}")
    return buffers


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_02_stream_buffering_and_backpressure_policy.md"
    )
    assert plan.is_file()


@pytest.mark.asyncio
async def test_inbound_drop_oldest_retains_newest(buffers_module) -> None:
    TypedAsyncQueue = buffers_module.TypedAsyncQueue
    BufferPolicy = buffers_module.BufferPolicy

    policy = BufferPolicy(name="inbound_mic", maxsize=3, overflow="drop_oldest")
    queue = TypedAsyncQueue(policy)
    for i in range(5):
        await queue.put(i)
    items = [await queue.get() for _ in range(3)]
    assert items == [2, 3, 4]


@pytest.mark.asyncio
async def test_final_transcripts_never_dropped(buffers_module) -> None:
    FinalTranscriptQueue = getattr(buffers_module, "FinalTranscriptQueue", None)
    if FinalTranscriptQueue is None:
        pytest.skip("FinalTranscriptQueue not implemented yet")

    queue = FinalTranscriptQueue(maxsize=2)
    await queue.put_final("first")
    await queue.put_final("second")
    await queue.put_final("third")
    assert await queue.get() == "first"
    assert queue.dropped_final_count == 0


@pytest.mark.asyncio
async def test_outbound_blocking_policy(buffers_module) -> None:
    TypedAsyncQueue = buffers_module.TypedAsyncQueue
    BufferPolicy = buffers_module.BufferPolicy

    policy = BufferPolicy(name="outbound_tts", maxsize=2, overflow="block")
    queue = TypedAsyncQueue(policy)
    await queue.put(1)
    await queue.put(2)
    assert queue.full()

    got_item = False

    async def producer():
        nonlocal got_item
        await queue.put(3)
        got_item = True

    task = asyncio.create_task(producer())
    await asyncio.sleep(0.01)
    assert not got_item  # Must be blocked

    item = await queue.get()
    assert item == 1
    await task
    assert got_item
    assert await queue.get() == 2
    assert await queue.get() == 3


@pytest.mark.asyncio
async def test_cancellation_token(buffers_module) -> None:
    AsyncioCancellationToken = buffers_module.AsyncioCancellationToken
    TypedAsyncQueue = buffers_module.TypedAsyncQueue
    BufferPolicy = buffers_module.BufferPolicy

    token = AsyncioCancellationToken()
    policy = BufferPolicy(name="test", maxsize=5, overflow="drop_oldest")
    queue = TypedAsyncQueue(policy, cancellation_token=token)

    await queue.put("a")
    token.cancel()
    assert token.is_cancelled

    with pytest.raises(asyncio.CancelledError):
        await queue.get()


@pytest.mark.asyncio
async def test_10k_synthetic_flood(buffers_module) -> None:
    FinalTranscriptQueue = buffers_module.FinalTranscriptQueue
    queue = FinalTranscriptQueue(maxsize=100)
    for i in range(10000):
        await queue.put_final(f"final_{i}")

    assert queue.qsize() == 10000
    assert queue.dropped_final_count == 0
    assert queue.watermark_alert_triggered is True

