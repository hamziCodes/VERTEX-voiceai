from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest

from core.runtime.admission import CapacityExceededError, SessionAdmissionController

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_REDIS_TESTS") != "1",
    reason="RUN_LIVE_REDIS_TESTS!=1 - disposable Redis only",
)


@pytest.mark.asyncio
async def test_disposable_redis_atomic_limit_expiry_and_release() -> None:
    from redis.asyncio import Redis

    redis_url = os.environ.get("REDIS_URL")
    assert redis_url, "REDIS_URL must name a disposable Redis instance"
    redis = Redis.from_url(redis_url, decode_responses=True)
    prefix = f"ucve:phase09:{uuid4()}"
    now = [100.0]
    controller = SessionAdmissionController(
        max_sessions=3,
        redis_client=redis,
        lease_ttl_sec=10,
        clock=lambda: now[0],
        key_prefix=prefix,
    )

    async def attempt(index: int) -> str | None:
        session_id = f"session-{index}"
        try:
            await controller.acquire(
                session_id, "tenant-a", max_tenant_sessions=3
            )
            return session_id
        except CapacityExceededError:
            return None

    try:
        results = await asyncio.gather(*(attempt(index) for index in range(20)))
        admitted = [session_id for session_id in results if session_id is not None]
        assert len(admitted) == 3
        assert await controller.current_tenant_count("tenant-a") == 3
        await controller.release(admitted[0], "tenant-a")
        await controller.release(admitted[0], "tenant-a")
        assert await controller.current_tenant_count("tenant-a") == 2
        now[0] = 111.0
        assert await controller.current_tenant_count("tenant-a") == 0
    finally:
        keys = [key async for key in redis.scan_iter(match=f"{prefix}:*")]
        if keys:
            await redis.delete(*keys)
        await redis.aclose()
