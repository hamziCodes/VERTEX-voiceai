"""Phase 14 proof: legal hold, retention and tenant erasure on durable stores.

PostgreSQL (disposable) plus an S3-compatible object store (Adobe S3Mock
standing in for S3 in the chosen AWS hosting target; real S3 is unverified). Run through
``scripts/ops/run_privacy_proof.sh``; skipped unless both are configured.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DB_TESTS") != "1"
    or not os.environ.get("WAVIA_TEST_S3_ENDPOINT"),
    reason="needs disposable PostgreSQL and S3-compatible storage",
)

BUCKET = "wavia-privacy-proof"
REGION = "me-central-1"


@pytest.fixture(scope="module")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


async def _drain(worker, repository, job_id, *, rounds: int = 6):
    for _ in range(rounds):
        await worker.run_once(now=datetime.now(UTC) + timedelta(hours=1))
        job = await repository.get(job_id)
        if job.state.value in {"succeeded", "dead_letter", "held"}:
            return job
    return await repository.get(job_id)


@pytest.mark.asyncio
async def test_phase14_hold_retention_and_erasure_end_to_end() -> None:
    import boto3
    import psycopg
    from psycopg import errors

    from core.compliance.privacy_jobs import PrivacyJobConflictError
    from core.db.async_pg import AsyncDatabase
    from core.db.repos.privacy_repo import PostgresPrivacyJobRepository
    from core.storage.post_call_objects import S3PostCallObjectStore
    from infra.db.migrate import apply_migrations_async
    from worker_jobs.privacy_deletion import PrivacyDeletionWorker

    database_url = os.environ["DATABASE_URL"]
    endpoint = os.environ["WAVIA_TEST_S3_ENDPOINT"]
    await apply_migrations_async(database_url)
    s3 = boto3.client("s3", endpoint_url=endpoint, region_name=REGION)
    s3.create_bucket(
        Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION}
    )
    store = S3PostCallObjectStore(BUCKET, region=REGION, endpoint_url=endpoint)

    database = AsyncDatabase(database_url=database_url, min_size=1, max_size=4)
    await database.open()
    fx = await psycopg.AsyncConnection.connect(database_url, autocommit=True)
    repository = PostgresPrivacyJobRepository(database)
    worker = PrivacyDeletionWorker(
        repository=repository, object_store=store, worker_id="proof-worker"
    )

    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    agent_a, agent_b = uuid.uuid4(), uuid.uuid4()
    only_a_user, shared_user = uuid.uuid4(), uuid.uuid4()
    calls = {name: uuid.uuid4() for name in ("a1", "a2", "a3", "b1")}
    now = datetime.now(UTC)

    def keys(prefix: str) -> list[str]:
        page = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
        return [item["Key"] for item in page.get("Contents", [])]

    try:
        await fx.execute(
            "INSERT INTO tenants (id, name) VALUES (%s, 'Proof A'), (%s, 'Proof B')",
            (tenant_a, tenant_b),
        )
        await fx.execute(
            "INSERT INTO agents (id, tenant_id, name) VALUES "
            "(%s, %s, 'a'), (%s, %s, 'b')",
            (agent_a, tenant_a, agent_b, tenant_b),
        )
        await fx.execute(
            "INSERT INTO users (id, email) VALUES (%s, %s), (%s, %s)",
            (
                only_a_user,
                f"{only_a_user}@proof.test",
                shared_user,
                f"{shared_user}@proof.test",
            ),
        )
        await fx.execute(
            "INSERT INTO memberships (user_id, tenant_id, role) VALUES "
            "(%s, %s, 'tenant_admin'), (%s, %s, 'tenant_viewer'), "
            "(%s, %s, 'tenant_admin')",
            (only_a_user, tenant_a, shared_user, tenant_a, shared_user, tenant_b),
        )
        refs = {}
        for name, call in calls.items():
            tenant = tenant_b if name == "b1" else tenant_a
            agent = agent_b if name == "b1" else agent_a
            refs[name] = await store.put(tenant, uuid.uuid4(), b"RIFF-proof-audio")
            await fx.execute(
                "INSERT INTO call_records (call_id, tenant_id, agent_id, session_id, "
                "started_at, ended_at, finalized_at, purge_after, legal_hold, "
                "recording_s3_uri, recording_state, recording_checksum, "
                "recording_channel_count, recording_duration_seconds, "
                "recording_storage_region, dual_channel) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s, 'available', %s, 1, 1.5, "
                "%s, FALSE)",
                (
                    call,
                    tenant,
                    agent,
                    uuid.uuid4(),
                    now - timedelta(minutes=5),
                    now - timedelta(minutes=4),
                    now - timedelta(minutes=4),
                    now + timedelta(days=30),
                    refs[name],
                    "a" * 64,
                    REGION,
                ),
            )
        stray = await store.put(tenant_a, uuid.uuid4(), b"unlisted-object")
        assert len(keys(f"post-call/{tenant_a}/")) == 4

        # 1. Conversation deletion: object first, then the row; full event trail.
        job = await repository.request_call_deletion(
            tenant_a, calls["a1"], actor="oidc:u"
        )
        done = await _drain(worker, repository, job.job_id)
        assert done.state.value == "succeeded"
        assert refs["a1"].split(f"{BUCKET}/", 1)[1] not in keys("post-call/")
        gone = await (
            await fx.execute(
                "SELECT count(*) FROM call_records WHERE call_id = %s", (calls["a1"],)
            )
        ).fetchone()
        assert gone == (0,)
        assert [e["event"] for e in await repository.events(job.job_id)] == [
            "requested",
            "objects_deleted",
            "database_deleted",
            "completed",
        ]

        # 2. A hold applied after the request parks the job; release resumes it.
        job = await repository.request_call_deletion(
            tenant_a, calls["a3"], actor="oidc:u"
        )
        assert await repository.set_legal_hold(
            tenant_a, calls["a3"], hold=True, actor="oidc:c"
        )
        parked = await _drain(worker, repository, job.job_id)
        assert parked.state.value == "held" and parked.attempt_count == 0
        assert refs["a3"].split(f"{BUCKET}/", 1)[1] in keys("post-call/")
        with pytest.raises(PrivacyJobConflictError):
            await repository.request_call_deletion(
                tenant_a, calls["a3"], actor="oidc:u"
            )
        assert await repository.set_legal_hold(
            tenant_a, calls["a3"], hold=False, actor="oidc:c"
        )
        assert (await _drain(worker, repository, job.job_id)).state.value == "succeeded"
        trail = [e["event"] for e in await repository.events(job.job_id)]
        assert (
            trail[:3] == ["requested", "held", "released"] and trail[-1] == "completed"
        )

        # 3. Workspace erasure waits for every hold, then removes everything.
        await repository.set_legal_hold(
            tenant_a, calls["a2"], hold=True, actor="oidc:c"
        )
        erasure = await repository.request_tenant_erasure(tenant_a, actor="oidc:u")
        assert (await _drain(worker, repository, erasure.job_id)).state.value == "held"
        await repository.set_legal_hold(
            tenant_a, calls["a2"], hold=False, actor="oidc:c"
        )
        finished = await _drain(worker, repository, erasure.job_id)
        assert finished.state.value == "succeeded"

        assert keys(f"post-call/{tenant_a}/") == []  # listed and stray objects gone
        assert stray  # (swept by prefix, not by reference)
        assert len(keys(f"post-call/{tenant_b}/")) == 1  # bystander untouched

        tables = await (
            await fx.execute(
                "SELECT c.table_name FROM information_schema.columns c "
                "JOIN information_schema.tables t USING (table_schema, table_name) "
                "WHERE c.table_schema = 'public' AND c.column_name = 'tenant_id' "
                "AND t.table_type = 'BASE TABLE'"
            )
        ).fetchall()
        kept = {
            "privacy_deletion_jobs",
            "privacy_deletion_events",
            "platform_audit_events",
            "platform_support_sessions",
            "audit_log",
        }
        leftovers = {}
        for (table,) in tables:
            if table in kept:
                continue
            count = (
                await (
                    await fx.execute(
                        f'SELECT count(*) FROM "{table}" WHERE tenant_id = %s',  # noqa: S608
                        (tenant_a,),
                    )
                ).fetchone()
            )[0]
            if count:
                leftovers[table] = count
        assert leftovers == {}
        b_rows = await (
            await fx.execute(
                "SELECT count(*) FROM call_records WHERE tenant_id = %s", (tenant_b,)
            )
        ).fetchone()
        assert b_rows == (1,)
        users = await (
            await fx.execute(
                "SELECT id FROM users WHERE id IN (%s, %s)", (only_a_user, shared_user)
            )
        ).fetchall()
        assert users == [(shared_user,)]
        tombstone = await (
            await fx.execute(
                "SELECT name, deleted_at IS NOT NULL FROM tenants WHERE id = %s",
                (tenant_a,),
            )
        ).fetchone()
        assert tombstone[0].startswith("Erased tenant") and tombstone[1] is True
        events = [e["event"] for e in await repository.events(erasure.job_id)]
        assert (
            events[0] == "requested" and "held" in events and events[-1] == "completed"
        )
        database_event = next(
            e
            for e in await repository.events(erasure.job_id)
            if e["event"] == "database_deleted"
        )
        assert (
            database_event["counts"].get("call_records") == 1
        )  # a2 (a1, a3 already gone)

        # 4. The deletion record is append-only.
        with pytest.raises(errors.RaiseException):
            await fx.execute(
                "DELETE FROM privacy_deletion_events WHERE job_id = %s",
                (erasure.job_id,),
            )

        # 5. Storage failure is retried, recorded, then dead-lettered — never "done".
        broken = S3PostCallObjectStore(
            BUCKET, region=REGION, endpoint_url="http://127.0.0.1:9"
        )
        failing = PrivacyDeletionWorker(
            repository=repository, object_store=broken, worker_id="proof-worker-2"
        )
        job_b = await repository.enqueue(
            tenant_id=tenant_b,
            kind=__import__(
                "core.compliance.privacy_jobs", fromlist=["x"]
            ).PrivacyJobKind.RETENTION,
            request_key=f"erasure:call:{calls['b1']}",
            call_id=calls["b1"],
            object_references=(refs["b1"],),
            max_attempts=2,
            actor="oidc:u",
        )
        await _drain(failing, repository, job_b.job_id)
        dead = await repository.get(job_b.job_id)
        assert dead.state.value == "dead_letter"
        assert dead.last_error_code == "object_delete_failed"
        assert [e["event"] for e in await repository.events(job_b.job_id)] == [
            "requested",
            "failed",
            "dead_lettered",
        ]
        assert len(keys(f"post-call/{tenant_b}/")) == 1
    finally:
        await fx.execute(
            "DELETE FROM tenants WHERE id IN (%s, %s)", (tenant_a, tenant_b)
        )
        await fx.execute(
            "DELETE FROM users WHERE id IN (%s, %s)", (only_a_user, shared_user)
        )
        await fx.close()
        await database.close()
