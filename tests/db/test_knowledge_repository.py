from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from core.db.repos.knowledge_repo import PostgresKnowledgeRepository


class _Cursor:
    def __init__(self, row: tuple[Any, ...] | None = None) -> None:
        self.row = row

    async def fetchone(self) -> tuple[Any, ...] | None:
        return self.row

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return [] if self.row is None else [self.row]


class _Connection:
    def __init__(self, row: tuple[Any, ...] | None = None) -> None:
        self.row = row
        self.executions: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, sql: str, params: tuple[object, ...] = ()) -> _Cursor:
        self.executions.append((sql, params))
        return _Cursor(self.row)


class _Database:
    def __init__(self, row: tuple[Any, ...] | None = None) -> None:
        self.connection = _Connection(row)
        self.tenants: list[str] = []

    @asynccontextmanager
    async def tenant_transaction(self, tenant_id: str):  # type: ignore[no-untyped-def]
        self.tenants.append(tenant_id)
        yield self.connection


@pytest.mark.asyncio
async def test_postgres_get_filters_before_grouping_and_uses_tenant_transaction() -> (
    None
):
    tenant_id = uuid4()
    base_id = uuid4()
    now = datetime.now(UTC)
    database = _Database((base_id, "Support", "draft", 0, now, now, 0, 0, 0))
    repository = PostgresKnowledgeRepository(database)

    record = await repository.get_knowledge_base(tenant_id, base_id)

    sql, params = database.connection.executions[0]
    assert sql.index("AND kb.id = %s::uuid") < sql.index("GROUP BY kb.id")
    assert params == (str(tenant_id), str(base_id))
    assert database.tenants == [str(tenant_id)]
    assert record.knowledge_base_id == base_id
