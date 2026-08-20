"""UCVE Sovereign Worker Node Entrypoint."""

from __future__ import annotations

import asyncio

from core.observability.logging import get_logger
from worker_raw.handlers.session_lifecycle import SessionLifecycleHandler

logger = get_logger("ucve.worker_raw")


async def main() -> None:
    """Worker node main entrypoint."""
    logger.info("UCVE Sovereign Worker Node initializing...")
    handler = SessionLifecycleHandler()
    logger.info("Sovereign Worker Node listening for WebSocket audio connections.")


if __name__ == "__main__":
    asyncio.run(main())
