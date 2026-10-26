"""Play spoken filler audio during long tool calls."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class FillerConfig:
    """Config for audio filler trigger."""

    trigger_after_ms: int = 400  # Default 400 ms
    filler_phrase: str = "Checking that for you..."


class ConversationalFillerSynth:
    """Trigger a filler phrase when a tool call exceeds its threshold."""

    def __init__(
        self,
        config: FillerConfig | None = None,
        on_filler_triggered: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config or FillerConfig()
        self.on_filler_triggered = on_filler_triggered
        self.is_active = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start timer for filler phrase."""
        self.is_active = True
        self._task = asyncio.create_task(self._wait_and_trigger())

    async def _wait_and_trigger(self) -> None:
        await asyncio.sleep(self.config.trigger_after_ms / 1000.0)
        if self.is_active and self.on_filler_triggered:
            self.on_filler_triggered(self.config.filler_phrase)

    def cancel(self) -> None:
        """Cancel filler task on tool completion or barge-in."""
        self.is_active = False
        if self._task and not self._task.done():
            self._task.cancel()
