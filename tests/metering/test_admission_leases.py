from __future__ import annotations

import asyncio

import pytest

from core.runtime.admission import (
    AdmissionStoreUnavailableError,
    CapacityExceededError,
    SessionAdmissionController,
)


@pytest.mark.asyncio
async def test_memory_admission_is_atomic_under_concurrency() -> None:
    controller = SessionAdmissionController(max_sessions=5, force_memory=True)

    async def attempt(index: int) -> bool:
        try:
            return await controller.acquire(
                f"session-{index}", "tenant-a", max_tenant_sessions=5
            )
        except CapacityExceededError:
            return False

    results = await asyncio.gather(*(attempt(index) for index in range(20)))

    assert sum(results) == 5
    assert controller.active_session_count == 5


@pytest.mark.asyncio
async def test_admission_reacquire_and_double_release_are_idempotent() -> None:
    controller = SessionAdmissionController(max_sessions=1, force_memory=True)

    assert await controller.acquire("session-a", "tenant-a") is True
    assert await controller.acquire("session-a", "tenant-a") is True
    await controller.release("session-a", "tenant-a")
    await controller.release("session-a", "tenant-a")

    assert controller.active_session_count == 0


@pytest.mark.asyncio
async def test_expired_memory_lease_is_reconciled() -> None:
    now = [100.0]
    controller = SessionAdmissionController(
        max_sessions=1,
        lease_ttl_sec=10,
        force_memory=True,
        clock=lambda: now[0],
    )
    await controller.acquire("session-a", "tenant-a")
    now[0] = 111.0

    removed = await controller.reconcile()

    assert removed == 1
    assert controller.active_session_count == 0


class _Redis:
    def __init__(self, result: int = 1) -> None:
        self.result = result
        self.calls: list[tuple[str, int, tuple[object, ...]]] = []

    async def eval(self, script: str, key_count: int, *args: object) -> int:
        self.calls.append((script, key_count, args))
        return self.result


@pytest.mark.asyncio
async def test_redis_admission_uses_one_atomic_script() -> None:
    redis = _Redis()
    controller = SessionAdmissionController(
        max_sessions=10,
        redis_client=redis,
        lease_ttl_sec=30,
    )

    assert await controller.acquire(
        "session-a", "tenant-a", max_tenant_sessions=2
    )

    assert len(redis.calls) == 1
    script, key_count, args = redis.calls[0]
    assert "ZREMRANGEBYSCORE" in script
    assert "SET" in script
    assert key_count == 3
    assert "session-a" in args


def test_protected_environment_requires_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "staging")
    monkeypatch.delenv("REDIS_URL", raising=False)

    with pytest.raises(AdmissionStoreUnavailableError):
        SessionAdmissionController()
