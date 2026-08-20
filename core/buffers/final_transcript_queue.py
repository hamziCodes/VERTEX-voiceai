"""UCVE Final Transcript Queue Guard (Never Dropped)."""

from __future__ import annotations

import asyncio
from typing import Generic, TypeVar

T = TypeVar("T")


class FinalTranscriptQueue(Generic[T]):
    """Specialized queue for final transcripts ensuring zero data loss."""

    def __init__(
        self,
        maxsize: int = 0,
        high_watermark_alert: int = 500,
    ) -> None:
        # Internal queue is always unbounded (maxsize=0) to guarantee final transcripts are never dropped
        self.maxsize = maxsize
        self.high_watermark_alert = high_watermark_alert
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=0)
        self.dropped_final_count: int = 0
        self.watermark_alert_triggered: bool = False

    async def put_final(self, item: T) -> None:
        """Put final transcript into queue with zero-drop guarantee."""
        await self._queue.put(item)
        if self._queue.qsize() >= self.high_watermark_alert:
            self.watermark_alert_triggered = True

    async def put(self, item: T) -> None:
        """Alias to put_final."""
        await self.put_final(item)

    def put_nowait(self, item: T) -> None:
        """Put item into queue without awaiting."""
        self._queue.put_nowait(item)
        if self._queue.qsize() >= self.high_watermark_alert:
            self.watermark_alert_triggered = True

    async def get(self) -> T:
        """Get final transcript item from queue."""
        return await self._queue.get()

    def get_nowait(self) -> T:
        """Get final transcript item without awaiting."""
        return self._queue.get_nowait()

    def empty(self) -> bool:
        """Return True if queue is empty."""
        return self._queue.empty()

    def full(self) -> bool:
        """Return False because final transcript queue is unbounded."""
        return False

    def qsize(self) -> int:
        """Return number of pending final transcripts."""
        return self._queue.qsize()
