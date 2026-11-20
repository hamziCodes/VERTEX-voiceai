from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from control_plane.auth.api_keys_async import AsyncAPIKeyManager


class _Cursor:
    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self.row = row

    async def fetchone(self) -> tuple[Any, ...] | None:
        return self.row


class _Connection:
    def __init__(self) -> None:
        self.rows: list[tuple[Any, ...] | None] = []
        self.executions: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, sql: str, params: tuple[object, ...] = ()) -> _Cursor:
        self.executions.append((sql, params))
        row = self.rows.pop(0) if self.rows else None
        return _Cursor(row)


class _Database:
    def __init__(self) -> None:
        self.connection = _Connection()
        self.tenants: list[str] = []
        self.platform_transactions = 0

    @asynccontextmanager
    async def tenant_transaction(self, tenant_id: str):  # type: ignore[no-untyped-def]
        self.tenants.append(tenant_id)
        yield self.connection

    @asynccontextmanager
    async def platform_transaction(self):  # type: ignore[no-untyped-def]
        self.platform_transactions += 1
        yield self.connection


@pytest.mark.asyncio
async def test_durable_api_key_persists_hash_without_raw_secret() -> None:
    database = _Database()
    manager = AsyncAPIKeyManager(database)

    raw, _key_id = await manager.generate_api_key("tenant-a", "automation")

    sql, params = database.connection.executions[0]
    assert "INSERT INTO api_keys" in sql
    assert raw not in repr(params)
    assert len(str(params[5])) == 64


@pytest.mark.asyncio
async def test_durable_api_key_authenticates_then_updates_inside_tenant_scope() -> None:
    database = _Database()
    now = datetime.now(UTC)
    database.connection.rows.append(
        (
            "key-id",
            "subject-id",
            "tenant-a",
            "automation",
            ["session:mint"],
            "tenant_editor",
            now,
            None,
            None,
            None,
        )
    )
    manager = AsyncAPIKeyManager(database)

    record = await manager.verify_api_key(
        "ucve_live_valid-material", required_scope="session:mint", now=now
    )

    assert record["tenant_id"] == "tenant-a"
    assert database.platform_transactions == 1
    assert database.tenants == ["tenant-a"]
    assert "authenticate_api_key" in database.connection.executions[0][0]
    assert "last_used_at" in database.connection.executions[1][0]


def test_auth_lookup_function_is_security_definer_and_hash_only() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "infra"
        / "db"
        / "migrations"
        / "020_api_key_auth_lookup.sql"
    )
    sql = migration.read_text(encoding="utf-8")

    assert "SECURITY DEFINER" in sql
    assert "authenticate_api_key" in sql
    assert "key_hash = p_key_hash" in sql
    assert "GRANT EXECUTE" in sql
