from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from core.providers.exceptions import (
    NoProviderAvailableError,
    ProviderFailure,
    ProviderFailureCategory,
    ProviderInvocationError,
    ProviderStreamInterruptedError,
)
from core.providers.failover import FailoverRouter, ProviderStreamDeadlines


def _failure(
    provider_id: str,
    category: ProviderFailureCategory,
) -> ProviderInvocationError:
    return ProviderInvocationError(
        ProviderFailure(provider_id=provider_id, category=category, retryable=True)
    )


@pytest.mark.asyncio
async def test_stream_fails_over_before_first_meaningful_item() -> None:
    called: list[str] = []
    router = FailoverRouter(priority=["primary", "secondary"])

    def invoke(route: str) -> AsyncIterator[str]:
        async def stream() -> AsyncIterator[str]:
            called.append(route)
            if route == "primary":
                raise _failure(route, ProviderFailureCategory.TRANSIENT_SERVER)
            yield "safe fallback"

        return stream()

    output = [
        item
        async for item in router.stream_with_failover(
            "llm", "en", invoke, is_committed=bool
        )
    ]

    assert output == ["safe fallback"]
    assert called == ["primary", "secondary"]


@pytest.mark.asyncio
async def test_stream_never_replays_after_output_commit() -> None:
    called: list[str] = []
    router = FailoverRouter(priority=["primary", "secondary"])

    def invoke(route: str) -> AsyncIterator[str]:
        async def stream() -> AsyncIterator[str]:
            called.append(route)
            if route == "primary":
                yield "already emitted"
                raise _failure(route, ProviderFailureCategory.TRANSIENT_SERVER)
            yield "duplicate"

        return stream()

    output: list[str] = []
    with pytest.raises(ProviderStreamInterruptedError) as exc_info:
        async for item in router.stream_with_failover(
            "llm", "en", invoke, is_committed=bool
        ):
            output.append(item)

    assert output == ["already emitted"]
    assert called == ["primary"]
    assert exc_info.value.committed_items == 1
    assert "already emitted" not in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["first_item", "inter_item_idle", "overall"])
async def test_stream_deadlines_are_named_and_do_not_try_fallback_after_commit(
    stage: str,
) -> None:
    router = FailoverRouter(priority=["primary", "secondary"])
    deadlines = ProviderStreamDeadlines(
        first_item_seconds=0.01,
        idle_seconds=0.05 if stage == "overall" else 0.01,
        overall_seconds=0.025,
    )

    def invoke(route: str) -> AsyncIterator[str]:
        async def stream() -> AsyncIterator[str]:
            if stage == "first_item":
                await asyncio.sleep(0.05)
                yield route
                return
            yield route
            if stage == "inter_item_idle":
                await asyncio.sleep(0.05)
                yield "late"
                return
            while True:
                await asyncio.sleep(0.008)
                yield "progress"

        return stream()

    if stage == "first_item":
        with pytest.raises(NoProviderAvailableError, match="timeout"):
            async for _ in router.stream_with_failover(
                "llm", "en", invoke, deadlines=deadlines, is_committed=bool
            ):
                pass
    else:
        with pytest.raises(ProviderStreamInterruptedError) as exc_info:
            async for _ in router.stream_with_failover(
                "llm", "en", invoke, deadlines=deadlines, is_committed=bool
            ):
                pass
        assert exc_info.value.stage == stage


@pytest.mark.asyncio
async def test_stream_cancellation_closes_iterator_without_fallback() -> None:
    closed: list[str] = []
    called: list[str] = []
    router = FailoverRouter(priority=["primary", "secondary"])

    def invoke(route: str) -> AsyncIterator[str]:
        async def stream() -> AsyncIterator[str]:
            called.append(route)
            try:
                yield "first"
                await asyncio.sleep(10)
            finally:
                closed.append(route)

        return stream()

    stream = router.stream_with_failover(
        "llm", "en", invoke, is_committed=bool
    )
    assert await anext(stream) == "first"
    task = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert called == ["primary"]
    assert closed == ["primary"]
