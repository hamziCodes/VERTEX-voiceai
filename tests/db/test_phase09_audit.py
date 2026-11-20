from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from core.compliance.audit.queries import AuditQueries
from core.compliance.audit.writer import AuditWriter


class _Connection:
    def __init__(self) -> None:
        self.executions: list[tuple[str, tuple[object, ...]]] = []
        self.rows: list[tuple[object, ...]] = []

    async def execute(self, sql: str, params: tuple[object, ...]):  # type: ignore[no-untyped-def]
        self.executions.append((sql, params))
        connection = self

        class Cursor:
            async def fetchall(self) -> list[tuple[object, ...]]:
                return connection.rows

        return Cursor()


class _Database:
    def __init__(self) -> None:
        self.connection = _Connection()
        self.tenants: list[str] = []

    @asynccontextmanager
    async def tenant_transaction(self, tenant_id: str):  # type: ignore[no-untyped-def]
        self.tenants.append(tenant_id)
        yield self.connection


@pytest.mark.asyncio
async def test_audit_writer_persists_event_with_tenant_transaction() -> None:
    database = _Database()
    writer = AuditWriter(database=database)

    event_id = await writer.arecord(
        tenant_id="tenant-a",
        action="session_minted",
        resource_type="session",
        resource_id="session-a",
    )

    assert event_id != "failed-audit-insert"
    assert database.tenants == ["tenant-a"]
    sql, params = database.connection.executions[0]
    assert "INSERT INTO audit_log" in sql
    assert "tenant-a" in params


@pytest.mark.asyncio
async def test_audit_queries_read_durable_tenant_events() -> None:
    from datetime import UTC, datetime

    database = _Database()
    database.connection.rows = [
        (
            "event-id",
            "tenant-a",
            "actor-a",
            "api_key",
            "session_minted",
            "session",
            "session-a",
            {"ok": True},
            None,
            None,
            datetime.now(UTC),
        )
    ]
    queries = AuditQueries(database=database)

    events = await queries.aquery_tenant_audit_logs("tenant-a", "tenant-a")

    assert len(events) == 1
    assert events[0].id == "event-id"
    assert database.tenants == ["tenant-a"]
