"""UCVE Three-Point Cancellation Contract (Producer, Sender, Transport)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ThreePointCancel:
    """Manages atomic three-point cancellation across LLM/TTS producers, senders, and queues."""

    active_tasks: set[asyncio.Task[None]] = field(default_factory=set)
    flush_callbacks: list[Callable[[], None]] = field(default_factory=list)
    cancelled: bool = False

    def register_task(self, task: asyncio.Task[None]) -> None:
        """Register an active async task (e.g. LLM generator or TTS streaming task)."""
        self.active_tasks.add(task)
        task.add_done_callback(lambda t: self.active_tasks.discard(t))

    def register_flush_callback(self, cb: Callable[[], None]) -> None:
        """Register a queue or transport flush callback."""
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

    def reset(self) -> None:
        """Reset cancel state for new turn."""
        self.cancelled = False
        self.active_tasks.clear()
        self.flush_callbacks.clear()
