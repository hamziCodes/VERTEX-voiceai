from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from core.db.repos.post_call_repo import InMemoryPostCallRepository
from post_call.jobs.models import PostCallJobState
from post_call.jobs.repository import (
    InMemoryPostCallJobRepository,
    JobLeaseConflictError,
)
from post_call.models.disposition import CallDisposition
from post_call.models.policy import PostCallPolicy
from post_call.models.recording import RecordingState


@pytest.mark.asyncio
async def test_finalization_creates_one_restart_safe_outbox_job() -> None:
    call_repo = InMemoryPostCallRepository()
    jobs = InMemoryPostCallJobRepository(call_repo)
    tenant_id, agent_id, session_id = uuid4(), uuid4(), uuid4()
    started_at = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
    intelligence_config = {
        "extraction_schema_id": "clinic-v1",
        "extraction_schema": {"fields": [{"name": "patient_name", "type": "string"}]},
    }
    await call_repo.start_call(
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
        started_at=started_at,
        transport_type="websocket",
        policy=PostCallPolicy(),
        provider_snapshot={},
        intelligence_config_snapshot=intelligence_config,
    )
    call = await call_repo.finalize_call(
        tenant_id=tenant_id,
        session_id=session_id,
        ended_at=started_at + timedelta(seconds=2),
        end_reason="complete",
        disposition=CallDisposition.COMPLETED,
        metrics_snapshot={},
        usage_snapshot={},
        recording_state=RecordingState.NOT_REQUESTED,
    )
    await call_repo.finalize_call(
        tenant_id=tenant_id,
        session_id=session_id,
        ended_at=started_at + timedelta(seconds=3),
        end_reason="duplicate",
        disposition=CallDisposition.UNRESOLVED,
        metrics_snapshot={},
        usage_snapshot={},
        recording_state=RecordingState.NOT_REQUESTED,
    )

    claimed = await jobs.claim_next(
        "worker-a", now=started_at + timedelta(seconds=2), lease_seconds=30
    )

    assert claimed is not None
    assert claimed.call_id == call.call_id
    assert claimed.payload == intelligence_config
    assert claimed.state is PostCallJobState.RUNNING
    assert (
        await jobs.claim_next("worker-b", now=started_at + timedelta(seconds=2)) is None
    )
    assert len(call_repo._post_call_jobs) == 1


@pytest.mark.asyncio
async def test_expired_lease_retries_then_dead_letters_at_bounded_attempts() -> None:
    call_repo = InMemoryPostCallRepository()
    jobs = InMemoryPostCallJobRepository(call_repo)
    now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
    job = await jobs.create_job(
        tenant_id=uuid4(),
        call_id=uuid4(),
        payload={},
        max_attempts=3,
        now=now,
    )
    first = await jobs.claim_next("worker-a", now=now, lease_seconds=5)
    assert first is not None

    reclaimed = await jobs.claim_next(
        "worker-b", now=now + timedelta(seconds=6), lease_seconds=5
    )
    assert reclaimed is not None
    assert reclaimed.job_id == job.job_id
    with pytest.raises(JobLeaseConflictError):
        await jobs.fail_job(
            job.job_id,
            worker_id="worker-a",
            error_code="stale",
            safe_message="stale owner",
            retryable=True,
            now=now + timedelta(seconds=6),
        )

    retry = await jobs.fail_job(
        job.job_id,
        worker_id="worker-b",
        error_code="provider_timeout",
        safe_message="bounded safe detail",
        retryable=True,
        now=now + timedelta(seconds=6),
    )
    assert retry.state is PostCallJobState.RETRY_WAIT
    assert retry.attempt_count == 1
    assert retry.available_at == now + timedelta(seconds=7)

    for attempt in (2, 3):
        claimed = await jobs.claim_next(
            f"worker-{attempt}", now=retry.available_at, lease_seconds=5
        )
        assert claimed is not None
        retry = await jobs.fail_job(
            job.job_id,
            worker_id=f"worker-{attempt}",
            error_code="provider_timeout",
            safe_message="bounded safe detail",
            retryable=True,
            now=retry.available_at,
        )

    assert retry.state is PostCallJobState.DEAD_LETTER
    assert retry.attempt_count == 3
    assert await jobs.claim_next("worker-z", now=retry.available_at) is None
