from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.db.async_pg import AsyncDatabase, DatabaseConfigurationError
from infra.db.migrate import MigrationDriftError, discover_migrations, validate_applied


class _Transaction:
    def __init__(self, events: list[object]) -> None:
        self.events = events

    async def __aenter__(self) -> None:
        self.events.append("transaction.enter")

    async def __aexit__(self, *args: object) -> None:
        self.events.append("transaction.exit")


class _Connection:
    def __init__(self, events: list[object]) -> None:
        self.events = events

    def transaction(self) -> _Transaction:
        return _Transaction(self.events)

    async def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.events.append((sql, params))


class _Pool:
    def __init__(self) -> None:
        self.events: list[object] = []
        self.conn = _Connection(self.events)

    @asynccontextmanager
    async def connection(self):  # type: ignore[no-untyped-def]
        self.events.append("connection.enter")
        yield self.conn
        self.events.append("connection.exit")


@pytest.mark.asyncio
async def test_tenant_transaction_sets_one_rls_variable_inside_transaction() -> None:
    pool = _Pool()
    database = AsyncDatabase(pool=pool)

    async with database.tenant_transaction("tenant-a") as connection:
        assert connection is pool.conn

    assert pool.events == [
        "connection.enter",
        "transaction.enter",
        ("SELECT set_config('app.tenant_id', %s, true)", ("tenant-a",)),
        "transaction.exit",
        "connection.exit",
    ]


def test_protected_environment_requires_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "staging")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(DatabaseConfigurationError):
        AsyncDatabase.from_environment()


def test_migration_numbers_are_unique_and_pgvector_precedes_knowledge_schema() -> None:
    migrations = discover_migrations()
    versions = [migration.version for migration in migrations]

    assert len(versions) == len(set(versions))
    vector_migration = next(
        migration
        for migration in migrations
        if "knowledge_base_pgvector" in migration.name
    )
    assert vector_migration.version == 13


def test_migration_checksum_drift_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "001_example.sql"
    path.write_text("SELECT 1;", encoding="utf-8")
    migration = discover_migrations(tmp_path)[0]

    with pytest.raises(MigrationDriftError):
        validate_applied(migration, "different-checksum")


def test_all_tenant_rls_migrations_use_canonical_variable() -> None:
    root = Path(__file__).resolve().parents[2] / "infra" / "db" / "migrations"
    tenant_sql = "\n".join(
        path.read_text(encoding="utf-8") for path in root.glob("*.sql")
    )

    assert "app.current_tenant_id" not in tenant_sql
    assert "app.tenant_id" in tenant_sql


def test_compose_uses_pgvector_postgres_image() -> None:
    root = Path(__file__).resolve().parents[2]
    compose = (root / "infra" / "docker" / "docker-compose.yml").read_text(
        encoding="utf-8"
    )

    assert "pgvector/pgvector:pg16" in compose


def test_rls_upgrade_migration_rebuilds_policies_for_unprivileged_role() -> None:
    root = Path(__file__).resolve().parents[2]
    migration = (
        root / "infra" / "db" / "migrations" / "018_canonical_rls_app_role.sql"
    )

    sql = migration.read_text(encoding="utf-8")
    assert "CREATE ROLE ucve_app NOLOGIN" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "DROP POLICY IF EXISTS" in sql
    assert "current_setting('app.tenant_id', true)" in sql


@pytest.mark.asyncio
async def test_owned_migration_connection_uses_autocommit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from infra.db import migrate

    connect_kwargs: dict[str, object] = {}

    class Cursor:
        async def fetchall(self) -> list[tuple[str, str]]:
            return []

    class Connection:
        def transaction(self) -> _Transaction:
            return _Transaction([])

        async def execute(
            self, _sql: str, _params: tuple[object, ...] = ()
        ) -> Cursor:
            return Cursor()

        async def close(self) -> None:
            return None

    class AsyncConnection:
        @classmethod
        async def connect(cls, _url: str, **kwargs: object) -> Connection:
            connect_kwargs.update(kwargs)
            return Connection()

    monkeypatch.setitem(
        sys.modules,
        "psycopg",
        SimpleNamespace(AsyncConnection=AsyncConnection),
    )
    monkeypatch.setattr(migrate, "discover_migrations", lambda: [])

    assert await migrate.apply_migrations_async("postgresql://disposable") == []
    assert connect_kwargs == {"autocommit": True}
