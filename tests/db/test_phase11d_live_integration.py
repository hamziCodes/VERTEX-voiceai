from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DB_TESTS") != "1",
    reason="RUN_LIVE_DB_TESTS!=1 - disposable PostgreSQL only",
)


@pytest.fixture(scope="module")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    """Psycopg async requires a selector loop on Windows."""
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.mark.asyncio
async def test_phase11d_restart_safe_deletion_and_secret_migration(tmp_path) -> None:
    import psycopg

    from core.compliance.privacy_jobs import PrivacyJobKind, PrivacyJobState
    from core.db.async_pg import AsyncDatabase
    from core.db.repos.privacy_repo import PostgresPrivacyJobRepository
    from core.secrets.kms.local_dev import LocalDevKMSBackend
    from core.secrets.repository import PostgresSecretRepository
    from core.secrets.vault import SecretVault
    from core.storage.post_call_objects import LocalPostCallObjectStore
    from infra.db.migrate import apply_migrations_async
    from post_call.webhook.legacy_migration import (
        LegacyWebhookMigrationState,
        LegacyWebhookSecretMigrator,
        PostgresLegacyWebhookRepository,
    )
    from worker_jobs.privacy_deletion import PrivacyDeletionWorker

    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must name a disposable database"
    await apply_migrations_async(database_url)

    tenant_retention, tenant_erasure, tenant_other = uuid4(), uuid4(), uuid4()
    retention_agent, erasure_agent = uuid4(), uuid4()
    retention_call, erasure_call = uuid4(), uuid4()
    retention_session, erasure_session = uuid4(), uuid4()
    target_id = uuid4()
    raw_fixture = f"generated-legacy-{uuid4()}"
    now = datetime(2026, 10, 27, tzinfo=UTC)

    connection = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with connection.transaction():
            await connection.execute(
                "INSERT INTO tenants (id, name) VALUES "
                "(%s, 'phase11-retention'), (%s, 'phase11-erasure'), "
                "(%s, 'phase11-other')",
                (tenant_retention, tenant_erasure, tenant_other),
            )
            await connection.execute(
                "INSERT INTO agents (id, tenant_id, name) VALUES "
                "(%s, %s, 'retention-agent'), (%s, %s, 'erasure-agent')",
                (
                    retention_agent,
                    tenant_retention,
                    erasure_agent,
                    tenant_erasure,
                ),
            )
            await connection.execute(
                "INSERT INTO call_records "
                "(call_id, tenant_id, agent_id, session_id, started_at, ended_at, "
                "finalized_at, purge_after, legal_hold) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, FALSE), "
                "(%s, %s, %s, %s, %s, %s, %s, %s, FALSE)",
                (
                    retention_call,
                    tenant_retention,
                    retention_agent,
                    retention_session,
                    now - timedelta(minutes=2),
                    now - timedelta(minutes=1),
                    now - timedelta(minutes=1),
                    now - timedelta(seconds=1),
                    erasure_call,
                    tenant_erasure,
                    erasure_agent,
                    erasure_session,
                    now - timedelta(minutes=2),
                    now - timedelta(minutes=1),
                    now - timedelta(minutes=1),
                    now + timedelta(days=1),
                ),
            )
            await connection.execute(
                "INSERT INTO audit_log "
                "(tenant_id, actor_id, action, resource_type, resource_id) "
                "VALUES (%s, 'phase11', 'fixture', 'tenant', %s)",
                (tenant_erasure, str(tenant_erasure)),
            )
            await connection.execute(
                "INSERT INTO webhook_targets (id, tenant_id, url, secret) "
                "VALUES (%s, %s, 'https://example.test/hook', %s)",
                (target_id, tenant_retention, raw_fixture),
            )
    finally:
        await connection.close()

    store = LocalPostCallObjectStore(tmp_path, region="test-region")
    object_ref = await store.put(
        tenant_retention, retention_session, b"generated-recording"
    )
    first_database = AsyncDatabase(database_url=database_url)
    await first_database.open()
    first_repository = PostgresPrivacyJobRepository(first_database)
    retention_job = await first_repository.enqueue(
        tenant_id=tenant_retention,
        kind=PrivacyJobKind.RETENTION,
        request_key=f"retention:{retention_call}",
        call_id=retention_call,
        object_references=(object_ref,),
        now=now,
    )
    claimed = await first_repository.claim_next("phase11-first", now=now)
    assert claimed is not None
    assert await store.delete(object_ref) is True
    await first_repository.mark_object_deleted(
        retention_job.job_id,
        worker_id="phase11-first",
        reference=object_ref,
    )
    await first_database.close()

    second_database = AsyncDatabase(database_url=database_url)
    await second_database.open()
    second_repository = PostgresPrivacyJobRepository(second_database)
    worker = PrivacyDeletionWorker(
        repository=second_repository,
        object_store=store,
        worker_id="phase11-second",
    )
    assert await worker.run_once(now=now + timedelta(seconds=61)) is True
    assert (await second_repository.get(retention_job.job_id)).state is (
        PrivacyJobState.SUCCEEDED
    )

    vault = SecretVault(
        kms_backend=LocalDevKMSBackend(master_key=f"phase11-{uuid4()}"),
        repository=PostgresSecretRepository(second_database),
    )
    legacy_repository = PostgresLegacyWebhookRepository(second_database)
    migrator = LegacyWebhookSecretMigrator(
        repository=legacy_repository,
        vault=vault,
        worker_id="phase11-legacy",
    )
    assert await migrator.run_once() is True
    legacy = await legacy_repository.get(target_id)
    assert legacy.state is LegacyWebhookMigrationState.MIGRATED
    assert legacy.secret is None

    erasure_job = await second_repository.enqueue(
        tenant_id=tenant_erasure,
        kind=PrivacyJobKind.TENANT_ERASURE,
        request_key=f"erasure:{tenant_erasure}",
        now=now + timedelta(seconds=62),
    )
    assert await worker.run_once(now=now + timedelta(seconds=62)) is True
    assert (await second_repository.get(erasure_job.job_id)).state is (
        PrivacyJobState.SUCCEEDED
    )
    await second_database.close()

    verify = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with verify.transaction():
            assert (
                await (
                    await verify.execute(
                        "SELECT COUNT(*) FROM call_records WHERE call_id = %s",
                        (retention_call,),
                    )
                ).fetchone()
            )[0] == 0
            credential = await (
                await verify.execute(
                    "SELECT encrypted_blob FROM tenant_credentials "
                    "WHERE tenant_id = %s AND credential_ref = %s",
                    (tenant_retention, f"legacy-webhook-{target_id}"),
                )
            ).fetchone()
            assert credential is not None
            assert raw_fixture not in credential[0]
            replacement = await (
                await verify.execute(
                    "SELECT state, credential_ref FROM post_call_webhook_targets "
                    "WHERE target_id = %s",
                    (target_id,),
                )
            ).fetchone()
            assert replacement == ("pending", f"legacy-webhook-{target_id}")
            tenant = await (
                await verify.execute(
                    "SELECT deleted_at FROM tenants WHERE id = %s",
                    (tenant_erasure,),
                )
            ).fetchone()
            assert tenant is not None and tenant[0] is not None
            assert (
                await (
                    await verify.execute(
                        "SELECT COUNT(*) FROM agents WHERE tenant_id = %s",
                        (tenant_erasure,),
                    )
                ).fetchone()
            )[0] == 0
            assert (
                await (
                    await verify.execute(
                        "SELECT COUNT(*) FROM audit_log WHERE tenant_id = %s",
                        (tenant_erasure,),
                    )
                ).fetchone()
            )[0] == 1

        async with verify.transaction():
            await verify.execute("SET LOCAL ROLE ucve_app")
            await verify.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (str(tenant_other),),
            )
            rows = await (
                await verify.execute("SELECT job_id FROM privacy_deletion_jobs")
            ).fetchall()
            assert rows == []
    finally:
        await verify.close()

    assert await apply_migrations_async(database_url) == []
