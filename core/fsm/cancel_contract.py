"""UCVE Three-Point Cancellation Contract (Producer, Sender, Transport)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ThreePointCancel:
    """Cancel producers and senders, then flush their bounded queues."""

    active_tasks: set[asyncio.Task[Any]] = field(default_factory=set)
    flush_callbacks: list[Callable[[], Awaitable[None] | None]] = field(
        default_factory=list
    )
    cancelled: bool = False

    def register_task(self, task: asyncio.Task[Any]) -> None:
        """Register an active async task (e.g. LLM generator or TTS streaming task)."""
        self.active_tasks.add(task)
        task.add_done_callback(lambda t: self.active_tasks.discard(t))

    def register_flush_callback(
        self, cb: Callable[[], Awaitable[None] | None]
    ) -> None:
        """Register a queue or transport flush callback."""
        if cb not in self.flush_callbacks:
            self.flush_callbacks.append(cb)

    def execute_cancel_and_flush(self) -> int:
        """Atomically cancel all registered tasks and trigger queue flush callbacks."""
        self.cancelled = True
        cancelled_count = 0
        for task in list(self.active_tasks):
            if not task.done():
                task.cancel()
                cancelled_count += 1
        self.active_tasks.clear()

        for cb in self.flush_callbacks:
            try:
                cb()
            except Exception:
                pass
        return cancelled_count

    async def cancel_and_wait(self) -> int:
        """Cancel owned work, flush buffers, and wait until tasks have exited."""
        self.cancelled = True
        current = asyncio.current_task()
        tasks = [
            task
            for task in self.active_tasks
            if task is not current and not task.done()
        ]
        for task in tasks:
            task.cancel()
        self.active_tasks.clear()

        for callback in self.flush_callbacks:
            try:
                result = callback()
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return len(tasks)

    def reset(self) -> None:
        """Reset cancel state for new turn."""
        self.cancelled = False
        self.active_tasks.clear()
        # Keep registered flush_callbacks persistent across turns!
