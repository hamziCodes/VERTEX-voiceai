from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from control_plane.agents.models.agent_config import AgentConfig
from control_plane.agents.pg_repo import PostgresAgentConfigRepo
from core.db.async_pg import DatabaseConfigurationError
from core.db.models import Agent, Session, Tenant
from core.db.repos.pg_repos import (
    PostgresSessionRepository,
    PostgresTenantRepository,
    build_tenant_repository,
)


class _Cursor:
    def __init__(self, row: tuple[Any, ...] | None = None) -> None:
        self.row = row

    async def fetchone(self) -> tuple[Any, ...] | None:
        return self.row


class _Connection:
    def __init__(self) -> None:
        self.executions: list[tuple[str, tuple[object, ...]]] = []
        self.next_row: tuple[Any, ...] | None = None

    async def execute(self, sql: str, params: tuple[object, ...] = ()) -> _Cursor:
        self.executions.append((sql, params))
        return _Cursor(self.next_row)


class _Database:
    def __init__(self) -> None:
        self.connection = _Connection()
        self.tenants: list[str] = []

    @asynccontextmanager
    async def tenant_transaction(self, tenant_id: str):  # type: ignore[no-untyped-def]
        self.tenants.append(tenant_id)
        yield self.connection


@pytest.mark.asyncio
async def test_postgres_tenant_repository_uses_async_tenant_transaction() -> None:
    database = _Database()
    repository = PostgresTenantRepository(database)
    tenant = Tenant(id="00000000-0000-0000-0000-000000000101", name="tenant")

    saved = await repository.create_tenant(tenant)

    assert saved is tenant
    assert database.tenants == [tenant.id]
    assert "INSERT INTO tenants" in database.connection.executions[0][0]
    assert database.connection.executions[0][1][0] == tenant.id


@pytest.mark.asyncio
async def test_postgres_session_repository_round_trips_runtime_pin() -> None:
    database = _Database()
    repository = PostgresSessionRepository(database)
    tenant_id = "00000000-0000-0000-0000-000000000101"
    session = Session(
        id="00000000-0000-0000-0000-000000000201",
        tenant_id=tenant_id,
        agent_id="00000000-0000-0000-0000-000000000301",
        config_version_id="00000000-0000-0000-0000-000000000401",
        agent_config_version=4,
        runtime_plan_hash="hash",
        runtime_plan_snapshot={"plan": "snapshot"},
        session_language="ur",
        session_voice_id="voice-a",
    )

    await repository.create_session(tenant_id, session)

    sql, params = database.connection.executions[0]
    assert "runtime_plan_snapshot" in sql
    assert "hash" in params
    assert database.tenants == [tenant_id]


def test_protected_repository_builder_never_falls_back_to_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(DatabaseConfigurationError):
        build_tenant_repository()


@pytest.mark.asyncio
async def test_postgres_repository_does_not_swallow_database_failure() -> None:
    class FailingDatabase:
        @asynccontextmanager
        async def tenant_transaction(self, _tenant_id: str):  # type: ignore[no-untyped-def]
            raise ConnectionError("database unavailable")
            yield

    repository = PostgresTenantRepository(FailingDatabase())
    agent = Agent(
        id="00000000-0000-0000-0000-000000000301",
        tenant_id="00000000-0000-0000-0000-000000000101",
        name="agent",
    )

    with pytest.raises(ConnectionError, match="database unavailable"):
        await repository.save_agent(agent)


def test_session_runtime_pin_columns_have_forward_migration() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "infra"
        / "db"
        / "migrations"
        / "019_durable_runtime_state.sql"
    )
    sql = migration.read_text(encoding="utf-8")

    for column in (
        "agent_config_version",
        "runtime_plan_hash",
        "runtime_plan_snapshot",
        "session_language",
        "session_voice_id",
    ):
        assert column in sql


@pytest.mark.asyncio
async def test_postgres_agent_config_loads_immutable_published_snapshot() -> None:
    from uuid import UUID

    tenant_id = UUID("00000000-0000-0000-0000-000000000101")
    agent_id = UUID("00000000-0000-0000-0000-000000000301")
    config = AgentConfig(tenant_id=tenant_id, agent_id=agent_id, name="agent")
    snapshot = config.model_copy(
        update={"version": 3, "is_published": True}
    ).model_dump(mode="json")
    database = _Database()
    database.connection.next_row = (snapshot,)
    repository = PostgresAgentConfigRepo(database)

    loaded = await repository.get_published_version(tenant_id, agent_id, version=3)

    assert loaded.version == 3
    assert loaded.is_published is True
    assert database.tenants == [str(tenant_id)]
    assert "agent_config_versions" in database.connection.executions[0][0]
