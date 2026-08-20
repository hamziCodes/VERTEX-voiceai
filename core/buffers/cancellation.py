"""UCVE Task & Stream Cancellation Protocols."""

from __future__ import annotations

import asyncio
from typing import Protocol


class CancellationToken(Protocol):
    """Protocol for checking and signalling cancellation."""

    @property
    def is_cancelled(self) -> bool:
        ...

    def cancel(self) -> None:
        ...

    def raise_if_cancelled(self) -> None:
        ...


class AsyncioCancellationToken:
    """Asyncio Event-backed cancellation token implementation."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def is_cancelled(self) -> bool:
        """True if cancellation signal has been set."""
        return self._event.is_set()

    def cancel(self) -> None:
        """Trigger cancellation signal."""
        self._event.set()

    def reset(self) -> None:
        """Reset cancellation signal."""
        self._event.clear()

    def raise_if_cancelled(self) -> None:
        """Raise CancelledError if cancellation has been triggered."""
        if self.is_cancelled:
            raise asyncio.CancelledError("Operation cancelled via CancellationToken.")

    async def wait(self) -> None:
        """Await cancellation signal."""
        await self._event.wait()
