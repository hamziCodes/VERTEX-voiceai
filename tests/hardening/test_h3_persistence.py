"""H3: persistence contracts (Postgres/Redis when available; else in-process)."""

from __future__ import annotations

import os

import pytest

from core.compliance.audit.queries import AuditQueries
from core.compliance.audit.writer import (
    AuditWriter,
    clear_shared_audit_logs,
    shared_audit_logs,
)
from core.db.session import TenantScopedDBSession
from core.secrets.kms.aws_kms import AWSKMSBackend, KMSNotConfigured
from core.session.redis_store import RedisSessionStore


@pytest.fixture(autouse=True)
def _clean_audit() -> None:
    clear_shared_audit_logs()


def test_set_app_tenant_id_is_parameterized() -> None:
    sess = TenantScopedDBSession("tenant-abc")
    sql, params = sess.set_app_tenant_id_params()
    assert "%s" in sql
    assert "set_config" in sql
    assert params == ("tenant-abc",)
    # Must not interpolate tenant id into SQL string
    assert "tenant-abc" not in sql


def test_audit_writer_shared_with_queries() -> None:
    writer = AuditWriter()
    eid = writer.record(
        tenant_id="t1",
        action="session_minted",
        resource_type="session",
        resource_id="s1",
    )
    assert eid != "failed-audit-insert"
    queries = AuditQueries()
    logs = queries.query_tenant_audit_logs("t1", "t1")
    assert len(logs) == 1
    assert logs[0].resource_id == "s1"
    assert shared_audit_logs()[0].id == logs[0].id


@pytest.mark.asyncio
async def test_redis_session_store_memory_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.delenv("REDIS_URL", raising=False)
    store = RedisSessionStore()
    await store.append_turn("sess-1", {"role": "user", "text": "hi"})
    await store.append_turn("sess-1", {"role": "assistant", "text": "hello"})
    turns = await store.get_turns("sess-1")
    assert len(turns) == 2
    await store.clear_session("sess-1")
    assert await store.get_turns("sess-1") == []


def test_aws_kms_no_fernet_fallback() -> None:
    with pytest.raises(KMSNotConfigured):
        AWSKMSBackend(key_id="alias/does-not-matter")


def test_foundation_hardening_migration_exists() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    path = root / "infra" / "db" / "migrations" / "017_foundation_hardening.sql"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "ON DELETE RESTRICT" in text
    assert "idx_sessions_purge_after_active" in text


def test_migrate_module_importable() -> None:
    from infra.db.migrate import list_migrations

    names = [p.name for p in list_migrations()]
    assert "001_core_tenant_schema.sql" in names
    assert "017_foundation_hardening.sql" in names


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DB_TESTS") != "1",
    reason="RUN_LIVE_DB_TESTS!=1 — compose/integration only",
)
def test_live_postgres_migrate_and_session() -> None:
    from infra.db.migrate import apply_migrations

    applied = apply_migrations()
    assert isinstance(applied, list)
