from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from core.secrets.repository import CredentialRecord, PostgresSecretRepository


class _Cursor:
    def __init__(self, row: tuple[Any, ...] | None = None) -> None:
        self.row = row

    async def fetchone(self) -> tuple[Any, ...] | None:
        return self.row


class _Connection:
    def __init__(self) -> None:
        self.row: tuple[Any, ...] | None = None
        self.executions: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, sql: str, params: tuple[object, ...] = ()) -> _Cursor:
        self.executions.append((sql, params))
        return _Cursor(self.row)


class _Database:
    def __init__(self) -> None:
        self.connection = _Connection()
        self.tenants: list[str] = []

    @asynccontextmanager
    async def tenant_transaction(self, tenant_id: str):  # type: ignore[no-untyped-def]
        self.tenants.append(tenant_id)
        yield self.connection


@pytest.mark.asyncio
async def test_postgres_secret_repository_persists_encrypted_record_only() -> None:
    database = _Database()
    repository = PostgresSecretRepository(database)
    record = CredentialRecord(
        tenant_id="tenant-a",
        provider_id="groq",
        credential_type="api_key",
        credential_ref="primary",
        encrypted_blob="encrypted-envelope",
        key_version=2,
        rotation_version=4,
    )

    await repository.put(record)

    sql, params = database.connection.executions[0]
    assert "tenant_credentials" in sql
    assert "encrypted-envelope" in params
    assert "plaintext-secret" not in repr(params)
    assert database.tenants == ["tenant-a"]


@pytest.mark.asyncio
async def test_postgres_secret_repository_loads_rotation_metadata() -> None:
    database = _Database()
    database.connection.row = (
        "tenant-a",
        "groq",
        "api_key",
        "primary",
        "encrypted-envelope",
        2,
        4,
    )
    repository = PostgresSecretRepository(database)

    record = await repository.get("tenant-a", "groq", "api_key", "primary")

    assert record is not None
    assert record.rotation_version == 4
    assert record.encrypted_blob == "encrypted-envelope"
