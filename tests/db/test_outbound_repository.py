from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import time
from uuid import uuid4

import pytest

from core.db.repos.outbound_call_repo import PostgresOutboundCallRepository


class _Cursor:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row = row

    async def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class _Connection:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self.row = row
        self.params: tuple[object, ...] | None = None

    async def execute(
        self, sql: str, params: tuple[object, ...] = ()
    ) -> _Cursor:
        assert "telephony_outbound_policies" in sql
        self.params = params
        return _Cursor(self.row)


class _Database:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self.connection = _Connection(row)
        self.tenant_id = ""

    @asynccontextmanager
    async def tenant_transaction(self, tenant_id: str):
        self.tenant_id = tenant_id
        yield self.connection


@pytest.mark.asyncio
async def test_postgres_policy_provider_is_tenant_scoped_and_typed() -> None:
    tenant_id = uuid4()
    database = _Database(
        (
            ["+14155550199"],
            "America/New_York",
            time(9, 0),
            time(17, 0),
            2,
            3,
            500,
            20,
            600,
        )
    )
    repository = PostgresOutboundCallRepository(
        database=database,
        media_stream_url="wss://voice.example.test/v1/telephony/media",
    )

    policy = await repository.get_policy(tenant_id)

    assert database.tenant_id == str(tenant_id)
    assert database.connection.params == (str(tenant_id),)
    assert policy.allowed_destinations == frozenset({"+14155550199"})
    assert policy.calling_window.timezone == "America/New_York"
    assert policy.max_concurrent_calls == 2
    assert policy.max_call_duration_seconds == 600


@pytest.mark.asyncio
async def test_missing_or_disabled_outbound_policy_fails_closed() -> None:
    repository = PostgresOutboundCallRepository(
        database=_Database(None),
        media_stream_url="wss://voice.example.test/v1/telephony/media",
    )

    with pytest.raises(ValueError, match="outbound_policy_unavailable"):
        await repository.get_policy(uuid4())


def test_postgres_outbound_repository_requires_secure_media_url() -> None:
    with pytest.raises(ValueError, match="wss"):
        PostgresOutboundCallRepository(
            database=_Database(None),
            media_stream_url="ws://localhost/v1/telephony/media",
        )
