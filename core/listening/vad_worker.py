"""UCVE VAD Worker — serialized single-thread executor for VAD inference.

Running Silero/energy inference with ``asyncio.to_thread`` spawns unbounded
threads under concurrent sessions and can starve the event loop. This worker
serializes all inference onto a single dedicated thread (``max_workers=1``),
keeping event-loop lag low under load.

Harvested pattern: v3 ``websocket.py`` ``_vad_worker`` queue.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

_T = TypeVar("_T")


class VADWorker:
    """Serializes VAD / speech-capture inference on one background thread."""

    def __init__(self, thread_name_prefix: str = "ucve-vad") -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=thread_name_prefix
        )
        self._closed = False

    async def submit(self, fn: Callable[..., _T], *args: Any) -> _T:
        """Run ``fn(*args)`` on the dedicated inference thread and await it."""
        if self._closed:
            # Fall back to inline execution after shutdown to avoid races.
            return fn(*args)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, fn, *args)

    def shutdown(self) -> None:
        if not self._closed:
            self._closed = True
            self._executor.shutdown(wait=False)
