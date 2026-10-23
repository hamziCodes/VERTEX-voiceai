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
            open=False,
        )
        await self._pool.open()

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
        pool = self._require_pool()
        async with pool.connection() as connection:
            async with connection.transaction():
                await connection.execute(TENANT_SETTING_SQL, (normalized,))
                yield connection

    @asynccontextmanager
    async def platform_transaction(self) -> AsyncIterator[Any]:
        """Open a transaction for platform-global operations such as migrations."""

        pool = self._require_pool()
        async with pool.connection() as connection:
            async with connection.transaction():
                yield connection
