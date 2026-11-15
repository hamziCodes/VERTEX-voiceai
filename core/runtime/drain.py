"""Graceful drain for services that hold live calls (Phase 14).

Plain uvicorn treats SIGTERM as "shut down now": it stops the server and
closes open WebSockets with 1012, which cuts every live call. A rolling deploy
or scale-in must instead:

1. mark the process not-ready (load balancers stop routing new sessions here);
2. refuse new sessions while letting active ones finish;
3. exit once the last session ends, or when the drain timeout expires;
4. exit immediately on a second signal (operator override).

:class:`DrainingServer` implements that around any uvicorn config. Pair it
with a container stop grace period at least as long as the drain timeout.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from types import FrameType
from typing import Any

import uvicorn

from core.runtime.health import ReadinessProbe

logger = logging.getLogger(__name__)


class DrainingServer(uvicorn.Server):
    def __init__(
        self,
        config: uvicorn.Config,
        *,
        probe: ReadinessProbe,
        active_sessions: Callable[[], int],
        drain_timeout_s: float,
        poll_interval_s: float = 0.5,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(config)
        self.probe = probe
        self.active_sessions = active_sessions
        self.drain_timeout_s = drain_timeout_s
        self.poll_interval_s = poll_interval_s
        self.clock = clock
        self.drain_started_at: float | None = None
        self.drain_outcome: str | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def serve(self, sockets: Any = None) -> None:
        self._loop = asyncio.get_running_loop()
        await super().serve(sockets)

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        if self.drain_started_at is not None or self._loop is None:
            # Second signal, or no loop yet: behave like plain uvicorn (exit now).
            super().handle_exit(sig, frame)
            if self.drain_started_at is not None:
                self.force_exit = True
            return
        self.drain_started_at = self.clock()
        self.probe.start_draining()
        logger.warning(
            "drain started: %s active session(s), timeout %ss",
            self.active_sessions(),
            self.drain_timeout_s,
        )
        self._loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self.drain()))

    async def drain(self) -> str:
        """Wait for active sessions to finish (or time out), then stop."""
        if self.drain_started_at is None:
            self.drain_started_at = self.clock()
            self.probe.start_draining()
        while self.active_sessions() > 0:
            if self.clock() - self.drain_started_at >= self.drain_timeout_s:
                self.drain_outcome = "timeout"
                logger.warning(
                    "drain timed out with %s active session(s)", self.active_sessions()
                )
                break
            await asyncio.sleep(self.poll_interval_s)
        else:
            self.drain_outcome = "drained"
            logger.warning("drain complete; stopping")
        self.should_exit = True
        return self.drain_outcome
