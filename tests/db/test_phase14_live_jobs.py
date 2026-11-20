"""Phase 14 disposable PostgreSQL proof: job slot claims and queue observation."""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DB_TESTS") != "1",
    reason="RUN_LIVE_DB_TESTS!=1 - disposable PostgreSQL only",
)


@pytest.fixture(scope="module")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.mark.asyncio
async def test_phase14_job_claims_and_dead_letter_observation() -> None:
    import psycopg

    from core.alerts.models import AlertCode
    from core.alerts.repository import PostgresAlertRepository
    from core.alerts.service import AlertService
    from core.compliance.privacy_jobs import PrivacyJobKind
    from core.db.async_pg import AsyncDatabase
    from core.db.repos.privacy_repo import PostgresPrivacyJobRepository
    from core.observability.metrics import ucve_job_queue_depth
    from infra.db.migrate import apply_migrations_async
    from worker_jobs.catalog import build_job_specs
    from worker_jobs.scheduler import JobsRunner, PostgresSlotClaims

    database_url = os.environ["DATABASE_URL"]
    await apply_migrations_async(database_url)
    database = AsyncDatabase(database_url=database_url, min_size=1, max_size=8)
    await database.open()
    fixture = await psycopg.AsyncConnection.connect(database_url, autocommit=True)
    tenant = uuid.uuid4()
    try:
        await fixture.execute(
            "INSERT INTO tenants (id, name) VALUES (%s, 'Jobs')", (tenant,)
        )

        # 1. Exactly one of five replicas wins a slot; an expired lease is taken over.
        claims = PostgresSlotClaims(database)
        slot = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
        wins = await asyncio.gather(
            *(claims.claim("retention_enqueue", slot, f"r{i}", 60) for i in range(5))
        )
        assert sum(wins) == 1
        assert not await claims.claim("retention_enqueue", slot, "late", 60)
        await fixture.execute(
            "UPDATE scheduled_job_runs "
            "SET lease_expires_at = NOW() - INTERVAL '1 second'"
        )
        assert await claims.claim("retention_enqueue", slot, "takeover", 60)
        await claims.finish(
            "retention_enqueue",
            slot,
            "takeover",
            status="succeeded",
            items=0,
            error_code=None,
        )
        row = await (
            await fixture.execute(
                "SELECT runner_id, status, attempts FROM scheduled_job_runs "
                "WHERE job_name = 'retention_enqueue'"
            )
        ).fetchone()
        assert row == ("takeover", "succeeded", 2)

        # 2. A dead-lettered privacy job is observed and raises one alert.
        privacy = PostgresPrivacyJobRepository(database)
        job = await privacy.enqueue(
            tenant_id=tenant, kind=PrivacyJobKind.TENANT_ERASURE, request_key="erase:1"
        )
        await fixture.execute(
            "UPDATE privacy_deletion_jobs SET state = 'dead_letter' WHERE job_id = %s",
            (job.job_id,),
        )
        alerts = AlertService(PostgresAlertRepository(database))
        runner = JobsRunner(
            build_job_specs(database, runner_id="live-runner", alerts=alerts),
            runner_id="live-runner",
            claims=claims,
            alerts=alerts,
        )
        assert await runner.run_tick("queue_observer") == "succeeded"
        depth = ucve_job_queue_depth.labels(job="privacy_deletion", state="dead_letter")
        assert depth.value == 1
        open_alerts = await alerts.repository.list_alerts(status="open")
        assert [a.code for a in open_alerts] == [AlertCode.JOB_DEAD_LETTER]
        assert open_alerts[0].facts["count"] == 1

        # Same slot again: another replica would skip it.
        assert await runner.run_tick("queue_observer") == "skipped"

        # 3. Retention enqueue runs against the real call_records query.
        assert await runner.run_tick("retention_enqueue") in {"idle", "succeeded"}

        # 4. Clearing the dead letter resolves the alert on the next slot.
        await fixture.execute(
            "DELETE FROM privacy_deletion_jobs WHERE job_id = %s", (job.job_id,)
        )
        await fixture.execute(
            "DELETE FROM scheduled_job_runs WHERE job_name = 'queue_observer'"
        )
        assert await runner.run_tick("queue_observer") == "succeeded"
        assert await alerts.repository.list_alerts(status="open") == []
    finally:
        await fixture.execute("DELETE FROM tenants WHERE id = %s", (tenant,))
        await fixture.execute("DELETE FROM scheduled_job_runs")
        await fixture.execute("DELETE FROM operational_alerts")
        await fixture.close()
        await database.close()
