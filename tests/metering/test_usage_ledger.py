from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import pytest

from control_plane.routes.usage import query_usage
from core.db.models import UsageEvent
from core.db.repos.usage_pg import PostgresUsageRepository, UsageSnapshot
from core.metering.quota_enforcer import QuotaEnforcer
from core.metering.usage_meter import UsageMeter


class _Cursor:
    def __init__(
        self,
        row: tuple[Any, ...] | None = None,
        rows: list[tuple[Any, ...]] | None = None,
    ) -> None:
        self.row = row
        self.rows = rows or []

    async def fetchone(self) -> tuple[Any, ...] | None:
        return self.row

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows


class _Connection:
    def __init__(self) -> None:
        self.results: list[_Cursor] = []
        self.executions: list[tuple[str, tuple[object, ...]]] = []

    async def execute(
        self, sql: str, params: tuple[object, ...] = ()
    ) -> _Cursor:
        self.executions.append((sql, params))
        return self.results.pop(0) if self.results else _Cursor()


class _Database:
    def __init__(self) -> None:
        self.connection = _Connection()

    @asynccontextmanager
    async def tenant_transaction(self, _tenant_id: str):  # type: ignore[no-untyped-def]
        yield self.connection


@pytest.mark.asyncio
async def test_postgres_usage_insert_is_idempotent_by_event_key() -> None:
    database = _Database()
    database.connection.results.append(_Cursor(row=("event-id",)))
    repository = PostgresUsageRepository(database)
    event = UsageEvent(
        id="event-id",
        event_key="session-a:stt:final",
        tenant_id="tenant-a",
        session_id="session-a",
        usage_kind="stt_sec",
        quantity=12.5,
        unit="seconds",
        provider_id="gladia",
        provider_request_id="provider-request-a",
        recorded_at=datetime.now(UTC),
    )

    assert await repository.record_usage("tenant-a", event) is True

    sql, params = database.connection.executions[0]
    assert "ON CONFLICT (tenant_id, event_key) DO NOTHING" in sql
    assert "session-a:stt:final" in params
    assert "provider-request-a" in params


@pytest.mark.asyncio
async def test_quota_enforcer_uses_durable_snapshot_instead_of_caller_values() -> None:
    class Repository:
        async def get_usage_snapshot(self, tenant_id: str) -> UsageSnapshot:
            assert tenant_id == "tenant-a"
            return UsageSnapshot(
                tenant_id=tenant_id,
                max_concurrent=2,
                monthly_seconds_limit=60.0,
                monthly_seconds_used=60.0,
                max_llm_tokens_month=100,
                monthly_llm_tokens=0.0,
                soft_cap_percent=80,
                hard_cap_percent=100,
                totals={},
            )

    enforcer = QuotaEnforcer(repository=Repository())

    result = await enforcer.check_mint(
        "tenant-a",
        current_concurrent=0,
        current_monthly_minutes=0,
    )

    assert result.allowed is False
    assert "hard cap" in str(result.reason).lower()
    assert result.max_concurrent == 2


@pytest.mark.asyncio
async def test_memory_usage_meter_deduplicates_same_event_key() -> None:
    meter = UsageMeter(force_memory=True)

    first = await meter.arecord(
        "tenant-a",
        "session-a",
        "tts_sec",
        2.0,
        event_key="session-a:tts:final",
    )
    duplicate = await meter.arecord(
        "tenant-a",
        "session-a",
        "tts_sec",
        2.0,
        event_key="session-a:tts:final",
    )

    assert first is True
    assert duplicate is False


@pytest.mark.asyncio
async def test_usage_query_returns_repository_totals_and_admission_count() -> None:
    class Repository:
        async def get_usage_snapshot(self, tenant_id: str) -> UsageSnapshot:
            return UsageSnapshot(
                tenant_id=tenant_id,
                max_concurrent=3,
                monthly_seconds_limit=600.0,
                monthly_seconds_used=90.0,
                max_llm_tokens_month=1_000,
                monthly_llm_tokens=125.0,
                soft_cap_percent=80,
                hard_cap_percent=100,
                totals={"agent_sec": 90.0, "stt_sec": 42.0, "tts_sec": 12.0},
            )

    class Admission:
        async def current_tenant_count(self, tenant_id: str) -> int:
            assert tenant_id == "tenant-a"
            return 2

    status, body = await query_usage(
        "tenant-a", "tenant-a", repository=Repository(), admission=Admission()
    )

    assert status == 200
    assert body["quota"]["current_concurrent"] == 2
    assert body["quota"]["current_monthly_minutes"] == 1.5
    assert body["totals"]["stt_sec"] == 42.0
