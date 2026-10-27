from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from core.compliance.privacy_jobs import (
    InMemoryPrivacyJobRepository,
    PrivacyJobKind,
    PrivacyJobState,
)
from worker_jobs.privacy_deletion import PrivacyDeletionWorker


class _ObjectStore:
    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.failures = 0

    async def delete(self, reference: str) -> bool:
        if self.failures:
            self.failures -= 1
            raise OSError("private backend detail")
        self.deleted.append(reference)
        return True


@pytest.mark.asyncio
async def test_retention_job_retries_without_claiming_partial_success() -> None:
    now = datetime(2026, 10, 27, tzinfo=UTC)
    tenant_id, call_id = uuid4(), uuid4()
    repository = InMemoryPrivacyJobRepository()
    job = await repository.enqueue(
        tenant_id=tenant_id,
        kind=PrivacyJobKind.RETENTION,
        request_key=f"retention:{call_id}",
        call_id=call_id,
        object_references=("post-call+local://local/t/s/a.wav",),
        now=now,
    )
    store = _ObjectStore()
    store.failures = 1
    worker = PrivacyDeletionWorker(
        repository=repository, object_store=store, worker_id="privacy-a"
    )

    assert await worker.run_once(now=now) is True
    failed = await repository.get(job.job_id)
    assert failed.state is PrivacyJobState.RETRY_WAIT
    assert failed.last_error_code == "object_delete_failed"
    assert "private backend detail" not in repr(failed)
    assert repository.database_deletions == []

    restarted = PrivacyDeletionWorker(
        repository=repository, object_store=store, worker_id="privacy-b"
    )
    assert await restarted.run_once(now=now + timedelta(seconds=2)) is True
    completed = await repository.get(job.job_id)
    assert completed.state is PrivacyJobState.SUCCEEDED
    assert store.deleted == ["post-call+local://local/t/s/a.wav"]
    assert repository.database_deletions == [
        (PrivacyJobKind.RETENTION, tenant_id, call_id)
    ]


@pytest.mark.asyncio
async def test_restart_skips_checkpointed_object_after_database_failure() -> None:
    now = datetime(2026, 10, 27, tzinfo=UTC)
    tenant_id = uuid4()
    repository = InMemoryPrivacyJobRepository(database_delete_failures=1)
    job = await repository.enqueue(
        tenant_id=tenant_id,
        kind=PrivacyJobKind.TENANT_ERASURE,
        request_key="erasure:request-1",
        object_references=("post-call+local://local/t/s/a.wav",),
        now=now,
    )
    store = _ObjectStore()

    first = PrivacyDeletionWorker(
        repository=repository, object_store=store, worker_id="privacy-a"
    )
    assert await first.run_once(now=now) is True
    partial = await repository.get(job.job_id)
    assert partial.state is PrivacyJobState.RETRY_WAIT
    assert partial.completed_object_references == job.object_references
    assert store.deleted == list(job.object_references)

    second = PrivacyDeletionWorker(
        repository=repository, object_store=store, worker_id="privacy-b"
    )
    assert await second.run_once(now=now + timedelta(seconds=2)) is True
    assert (await repository.get(job.job_id)).state is PrivacyJobState.SUCCEEDED
    assert store.deleted == list(job.object_references)
    assert repository.database_deletions == [
        (PrivacyJobKind.TENANT_ERASURE, tenant_id, None)
    ]


@pytest.mark.asyncio
async def test_legal_hold_blocks_every_deletion_layer_until_released() -> None:
    now = datetime(2026, 10, 27, tzinfo=UTC)
    tenant_id, call_id = uuid4(), uuid4()
    repository = InMemoryPrivacyJobRepository()
    repository.set_legal_hold(tenant_id, call_id, True)
    job = await repository.enqueue(
        tenant_id=tenant_id,
        kind=PrivacyJobKind.RETENTION,
        request_key=f"retention:{call_id}",
        call_id=call_id,
        object_references=("post-call+local://local/t/s/a.wav",),
        now=now,
    )
    store = _ObjectStore()
    worker = PrivacyDeletionWorker(
        repository=repository, object_store=store, worker_id="privacy-a"
    )

    assert await worker.run_once(now=now) is True
    held = await repository.get(job.job_id)
    assert held.state is PrivacyJobState.RETRY_WAIT
    assert held.last_error_code == "legal_hold"
    assert store.deleted == []
    assert repository.database_deletions == []

    repository.set_legal_hold(tenant_id, call_id, False)
    assert await worker.run_once(now=now + timedelta(seconds=2)) is True
    assert (await repository.get(job.job_id)).state is PrivacyJobState.SUCCEEDED


@pytest.mark.asyncio
async def test_duplicate_request_key_returns_same_job() -> None:
    tenant_id = uuid4()
    repository = InMemoryPrivacyJobRepository()
    first = await repository.enqueue(
        tenant_id=tenant_id,
        kind=PrivacyJobKind.TENANT_ERASURE,
        request_key="erasure:stable-key",
    )
    second = await repository.enqueue(
        tenant_id=tenant_id,
        kind=PrivacyJobKind.TENANT_ERASURE,
        request_key="erasure:stable-key",
    )
    assert second.job_id == first.job_id
