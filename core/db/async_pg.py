"""Async Psycopg database boundary with transaction-local tenant isolation."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from core.runtime.env import is_protected_environment

TENANT_SETTING_SQL = "SELECT set_config('app.tenant_id', %s, true)"


class DatabaseConfigurationError(RuntimeError):
    """Raised when durable database configuration is unavailable."""


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    try:
        value = float(raw) if raw else default
    except ValueError:
        return default
    return value if value > 0 else default


def pool_wait_timeout_s() -> float:
    """How long a request waits for a pooled connection before failing."""
    return _env_float("UCVE_DB_POOL_TIMEOUT_S", 5.0)


def connection_kwargs() -> dict[str, Any]:
    """libpq settings that turn a lost database into a fast, clean failure.

    Without them a dropped network leaves connections blocked on a dead TCP
    link: the Phase 15 network drill froze the whole control plane (even
    liveness) for ~15 s and mint took 30 s to fail.
    """
    connect_timeout = max(1, int(_env_float("UCVE_DB_CONNECT_TIMEOUT_S", 3.0)))
    user_timeout_ms = int(_env_float("UCVE_DB_TCP_USER_TIMEOUT_S", 5.0) * 1000)
    return {
        "connect_timeout": connect_timeout,
        "tcp_user_timeout": user_timeout_ms,
        "keepalives": 1,
        "keepalives_idle": 10,
        "keepalives_interval": 5,
        "keepalives_count": 2,
    }


class AsyncDatabase:
    """Own one async connection pool and tenant-scoped transaction boundary."""

    def __init__(
        self,
        *,
        pool: Any | None = None,
        database_url: str | None = None,
        min_size: int = 1,
        max_size: int = 10,
    ) -> None:
        self._pool = pool
        self.database_url = database_url
        self.min_size = min_size
        self.max_size = max_size

    @property
    def pool(self) -> Any | None:
        return self._pool

    @classmethod
    def from_environment(cls) -> AsyncDatabase:
        url = (os.environ.get("DATABASE_URL") or "").strip() or None
        if url is None and is_protected_environment():
            raise DatabaseConfigurationError(
                "Protected environments require DATABASE_URL."
            )
        return cls(database_url=url)

    async def open(self) -> None:
        if self._pool is not None:
            return
        if not self.database_url:
            raise DatabaseConfigurationError("DATABASE_URL is not configured.")
        try:
            from psycopg_pool import AsyncConnectionPool
        except ImportError as exc:  # pragma: no cover - packaging failure
            raise DatabaseConfigurationError(
                "psycopg_pool is required for durable database access."
            ) from exc
        self._pool = AsyncConnectionPool(
            conninfo=self.database_url,
            min_size=self.min_size,
            max_size=self.max_size,
            timeout=pool_wait_timeout_s(),
            kwargs=connection_kwargs(),
            # Verify each connection before handing it out: after a network
            # outage idle connections are dead, and the first request on each
            # would fail even though the database is back.
            check=AsyncConnectionPool.check_connection,
            open=False,
        )
        await self._pool.open()

    async def ensure_open(self) -> None:
        if self._pool is None:
            await self.open()

    async def close(self) -> None:
        if self._pool is not None and hasattr(self._pool, "close"):
            await self._pool.close()
        self._pool = None

    def _require_pool(self) -> Any:
        if self._pool is None:
            raise DatabaseConfigurationError("Database pool is not open.")
        return self._pool

    @asynccontextmanager
    async def tenant_transaction(self, tenant_id: str) -> AsyncIterator[Any]:
        normalized = tenant_id.strip()
        if not normalized:
            raise PermissionError("tenant_id is required for tenant transaction.")
        await self.ensure_open()
        pool = self._require_pool()
        async with pool.connection() as connection:
            async with connection.transaction():
                await connection.execute(TENANT_SETTING_SQL, (normalized,))
                yield connection

    @asynccontextmanager
    async def platform_transaction(self) -> AsyncIterator[Any]:
        """Open a transaction for platform-global operations such as migrations."""

        await self.ensure_open()
        pool = self._require_pool()
        async with pool.connection() as connection:
            async with connection.transaction():
                yield connection


_default_database: AsyncDatabase | None = None


def get_default_database() -> AsyncDatabase:
    global _default_database
    if _default_database is None:
        _default_database = AsyncDatabase.from_environment()
    return _default_database


def reset_default_database() -> None:
    """Forget the process database handle; tests must close an open pool first."""

    global _default_database
    _default_database = None
