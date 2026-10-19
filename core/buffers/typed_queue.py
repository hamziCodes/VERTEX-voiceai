"""UCVE Typed Async Queue with Enforced Overflow Policy."""

from __future__ import annotations

import asyncio
from typing import Generic, TypeVar

from core.buffers.cancellation import CancellationToken
from core.buffers.policy import BufferPolicy, OverflowPolicy

T = TypeVar("T")


class TypedAsyncQueue(Generic[T]):
    """Typed asyncio queue wrapper enforcing structured BufferPolicy."""

    def __init__(
        self,
        policy: BufferPolicy,
        cancellation_token: CancellationToken | None = None,
    ) -> None:
        self.policy = policy
        self.cancellation_token = cancellation_token
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=policy.maxsize)
        self.drop_count: int = 0
        self.overflow_count: int = 0
        self.high_watermark: int = 0

    def _record_high_watermark(self) -> None:
        self.high_watermark = max(self.high_watermark, self._queue.qsize())

    async def put(self, item: T) -> None:
        """Put item into queue with policy-enforced overflow handling."""
        if self.cancellation_token and self.cancellation_token.is_cancelled:
            raise asyncio.CancelledError("Queue put cancelled.")

        if self.policy.overflow == OverflowPolicy.BLOCK:
            await self._queue.put(item)
            self._record_high_watermark()
            return

        if self._queue.full() and self.policy.maxsize > 0:
            self.overflow_count += 1
            self.drop_count += 1
            if self.policy.overflow == OverflowPolicy.DROP_OLDEST:
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except asyncio.QueueEmpty:
                    pass
                self._queue.put_nowait(item)
                self._record_high_watermark()
            elif self.policy.overflow == OverflowPolicy.DROP_NEWEST:
                # Drop incoming item
                return
        else:
            await self._queue.put(item)
            self._record_high_watermark()

    def put_nowait(self, item: T) -> None:
        """Non-blocking put enforcing overflow policy."""
        if self.cancellation_token and self.cancellation_token.is_cancelled:
            raise asyncio.CancelledError("Queue put cancelled.")

        if self._queue.full() and self.policy.maxsize > 0:
            if self.policy.overflow == OverflowPolicy.BLOCK:
                raise asyncio.QueueFull("Queue is full and policy is BLOCK.")
            self.overflow_count += 1
            self.drop_count += 1
            if self.policy.overflow == OverflowPolicy.DROP_OLDEST:
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except asyncio.QueueEmpty:
                    pass
                self._queue.put_nowait(item)
                self._record_high_watermark()
            elif self.policy.overflow == OverflowPolicy.DROP_NEWEST:
                return
        else:
            self._queue.put_nowait(item)
            self._record_high_watermark()

    async def get(self) -> T:
        """Get item from queue."""
        if self.cancellation_token:
            self.cancellation_token.raise_if_cancelled()
        return await self._queue.get()

    def get_nowait(self) -> T:
        """Get item from queue without blocking."""
        if self.cancellation_token:
            self.cancellation_token.raise_if_cancelled()
        return self._queue.get_nowait()

    def empty(self) -> bool:
        """Return True if queue is empty."""
        return self._queue.empty()

    def full(self) -> bool:
        """Return True if queue is full."""
        return self._queue.full()

    def qsize(self) -> int:
        """Return current size of queue."""
        return self._queue.qsize()

    def reset_metrics(self) -> None:
        """Reset counters at a turn or measurement boundary."""
        self.drop_count = 0
        self.overflow_count = 0
        self.high_watermark = self._queue.qsize()

    def task_done(self) -> None:
        """Mark one item returned by get/get_nowait as processed."""
        self._queue.task_done()

    async def join(self) -> None:
        """Wait until every queued item has been processed or explicitly cleared."""
        await self._queue.join()

    def clear(self) -> None:
        """Drain all pending items from queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break
