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
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


class _ExtractionProvider:
    provider_id = "fixture"
    model_id = "extract-v1"

    async def extract_json(self, **_: object) -> object:
        return {
            "fields": {
                "patient_name": {
                    "value": "Ayesha",
                    "confidence": 0.98,
                    "evidence": [{"turn_id": 0, "quote": "name is Ayesha"}],
                }
            }
        }


class _SummaryProvider:
    provider_id = "fixture"
    model_id = "summary-v1"

    async def summarize_json(self, **_: object) -> object:
        return {
            "executive_summary": "Ayesha requested support.",
            "key_takeaways": ["Support requested"],
            "sentiment_trajectory": ["neutral"],
            "evidence": [{"turn_id": 0, "quote": "requested support"}],
        }


@pytest.mark.asyncio
async def test_disposable_post_call_job_restart_result_review_and_rls() -> None:
    import psycopg

    from control_plane.auth.context import AuthContext
    from core.db.async_pg import AsyncDatabase
    from core.db.repos.post_call_repo import PostgresPostCallRepository
    from infra.db.migrate import apply_migrations_async
    from post_call.extraction.service import ExtractionService
    from post_call.jobs.models import PostCallJobState
    from post_call.jobs.repository import PostgresPostCallJobRepository
    from post_call.models.diarized_turn import DiarizedTurn
    from post_call.models.disposition import CallDisposition
    from post_call.models.policy import PostCallPolicy
    from post_call.models.recording import RecordingState
    from post_call.review.models import ReviewDecision, ReviewState
    from post_call.review.repository import PostgresReviewRepository
    from post_call.summarization.service import SummarizationService
    from post_call.worker import PostCallJobWorker

    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must name a disposable database"
    await apply_migrations_async(database_url)
    tenant_a, tenant_b, agent_id, session_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    connection = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with connection.transaction():
            await connection.execute(
                "INSERT INTO tenants (id, name) VALUES (%s, %s), (%s, %s)",
                (tenant_a, "phase11b-a", tenant_b, "phase11b-b"),
            )
            await connection.execute(
                "INSERT INTO agents (id, tenant_id, name) VALUES (%s, %s, %s)",
                (agent_id, tenant_a, "phase11b-agent"),
            )
    finally:
        await connection.close()

    started_at = datetime.now(UTC) - timedelta(seconds=3)
    first_database = AsyncDatabase(database_url=database_url, min_size=1, max_size=1)
    await first_database.open()
    try:
        calls = PostgresPostCallRepository(first_database)
        await calls.start_call(
            tenant_id=tenant_a,
            agent_id=agent_id,
            session_id=session_id,
            started_at=started_at,
            transport_type="websocket",
            policy=PostCallPolicy(),
            provider_snapshot={},
            intelligence_config_snapshot={
                "extraction_schema": {
                    "fields": [
                        {
                            "name": "patient_name",
                            "required": True,
                            "sensitive": True,
                        }
                    ]
                }
            },
        )
        await calls.append_turn(
            tenant_id=tenant_a,
            session_id=session_id,
            ordinal=0,
            turn=DiarizedTurn(
                speaker="user",
                text="My name is Ayesha and I requested support.",
                start_ms=0,
                end_ms=800,
            ),
        )
        call = await calls.finalize_call(
            tenant_id=tenant_a,
            session_id=session_id,
            ended_at=started_at + timedelta(seconds=2),
            end_reason="complete",
            disposition=CallDisposition.COMPLETED,
            metrics_snapshot={},
            usage_snapshot={},
            recording_state=RecordingState.NOT_REQUESTED,
        )
    finally:
        await first_database.close()

    restarted = AsyncDatabase(database_url=database_url, min_size=1, max_size=1)
    await restarted.open()
    try:
        calls = PostgresPostCallRepository(restarted)
        jobs = PostgresPostCallJobRepository(restarted)
        worker = PostCallJobWorker(
            call_repository=calls,
            job_repository=jobs,
            extraction_service=ExtractionService(provider=_ExtractionProvider()),
            summarization_service=SummarizationService(provider=_SummaryProvider()),
            worker_id="worker-a",
        )
        worker_row = None
        for _ in range(10):
            assert await worker.run_once() is True
            async with restarted.platform_transaction() as db:
                worker_row = await (
                    await db.execute(
                        "SELECT state, last_error_code, last_error_message "
                        "FROM post_call_jobs WHERE call_id = %s::uuid",
                        (str(call.call_id),),
                    )
                ).fetchone()
            if worker_row[0] == "succeeded":
                break
        assert worker_row == ("succeeded", None, None)
        result = await jobs.get_result(tenant_a, call.call_id)
        assert result is not None
        review = await jobs.get_review_for_result(tenant_a, result.result_id)
        assert review is not None
        assert review.state is ReviewState.PENDING
        assert review.reasons == ("sensitive_field:patient_name",)

        approved = await PostgresReviewRepository(restarted).decide(
            tenant_id=tenant_a,
            review_id=review.review_id,
            decision=ReviewDecision.APPROVE,
            auth=AuthContext(
                subject_id="reviewer-1",
                tenant_id=str(tenant_a),
                roles=("tenant_admin",),
                scopes=frozenset({"extraction:write"}),
                auth_method="oidc",
            ),
            note="Evidence checked.",
        )
        assert approved.state is ReviewState.APPROVED
        assert await worker.run_once() is False

        async with restarted.platform_transaction() as db:
            row = await (
                await db.execute(
                    "SELECT state FROM post_call_jobs WHERE call_id = %s::uuid",
                    (str(call.call_id),),
                )
            ).fetchone()
            assert PostCallJobState(row[0]) is PostCallJobState.SUCCEEDED
    finally:
        await restarted.close()

    rls = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with rls.transaction():
            await rls.execute("SET LOCAL ROLE ucve_app")
            await rls.execute(
                "SELECT set_config('app.tenant_id', %s, true)", (str(tenant_b),)
            )
            for table in (
                "post_call_jobs",
                "post_call_intelligence_results",
                "post_call_review_requests",
            ):
                assert (
                    await (await rls.execute(f"SELECT * FROM {table}")).fetchall() == []
                )
    finally:
        await rls.close()

    assert await apply_migrations_async(database_url) == []
