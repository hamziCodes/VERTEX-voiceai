from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0

    def monotonic(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds

    async def sleep(self, seconds: float) -> None:
        self.advance(max(0.0, seconds))
        await asyncio.sleep(0)


class FakeTelnyxSocket:
    def __init__(self, clock: FakeClock | None = None) -> None:
        self.clock = clock or FakeClock()
        self.incoming: asyncio.Queue[str | None] = asyncio.Queue()
        self.sent: list[tuple[float, dict[str, Any]]] = []
        self.closed = False
        self.send_gate: asyncio.Event | None = None

    async def feed(self, payload: dict[str, Any]) -> None:
        await self.incoming.put(json.dumps(payload, separators=(",", ":")))

    async def disconnect(self) -> None:
        await self.incoming.put(None)

    async def receive_text(self) -> str:
        item = await self.incoming.get()
        if item is None:
            raise EOFError("fake carrier disconnected")
        return item

    async def send_json(self, payload: dict[str, Any]) -> None:
        if self.send_gate is not None:
            await self.send_gate.wait()
        self.sent.append((self.clock.monotonic(), payload))

    async def close(self, code: int = 1000) -> None:
        del code
        self.closed = True


async def wait_until(predicate: Callable[[], bool], *, attempts: int = 100) -> None:
    for _ in range(attempts):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition did not become true")
