"""Phase 02: Stream Buffering and Backpressure Policy."""

from __future__ import annotations

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
