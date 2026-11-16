"""Restart-safe privacy deletion job contracts and in-memory test adapter."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4


class PrivacyJobKind(StrEnum):
    RETENTION = "retention"
    TENANT_ERASURE = "tenant_erasure"


class PrivacyJobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    DEAD_LETTER = "dead_letter"
    HELD = "held"


@dataclass(frozen=True, slots=True)
class PrivacyDeletionJob:
    job_id: UUID
    tenant_id: UUID
    kind: PrivacyJobKind
    request_key: str
    call_id: UUID | None = None
    object_references: tuple[str, ...] = ()
    completed_object_references: tuple[str, ...] = ()
    database_deleted: bool = False
    state: PrivacyJobState = PrivacyJobState.QUEUED
    attempt_count: int = 0
    max_attempts: int = 5
    available_at: datetime = datetime.min.replace(tzinfo=UTC)
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    last_error_code: str | None = None
    created_at: datetime = datetime.min.replace(tzinfo=UTC)
    updated_at: datetime = datetime.min.replace(tzinfo=UTC)


class PrivacyJobConflictError(RuntimeError):
    pass


class InMemoryPrivacyJobRepository:
    """Restart-preserving in-memory adapter used by deterministic tests."""

    def __init__(self, *, database_delete_failures: int = 0) -> None:
        self.jobs: dict[UUID, PrivacyDeletionJob] = {}
        self.request_index: dict[tuple[UUID, str], UUID] = {}
        self.holds: set[tuple[UUID, UUID | None]] = set()
        self.database_delete_failures = database_delete_failures
        self.database_deletions: list[tuple[PrivacyJobKind, UUID, UUID | None]] = []

    async def enqueue(
        self,
        *,
        tenant_id: UUID,
        kind: PrivacyJobKind,
        request_key: str,
        call_id: UUID | None = None,
        object_references: tuple[str, ...] = (),
        max_attempts: int = 5,
        now: datetime | None = None,
    ) -> PrivacyDeletionJob:
        if not request_key.strip():
            raise ValueError("request_key is required.")
        if kind is PrivacyJobKind.RETENTION and call_id is None:
            raise ValueError("Retention deletion requires call_id.")
        key = (tenant_id, request_key)
        if key in self.request_index:
            return self.jobs[self.request_index[key]]
        timestamp = now or datetime.now(UTC)
        job = PrivacyDeletionJob(
            job_id=uuid4(),
            tenant_id=tenant_id,
            kind=kind,
            request_key=request_key,
            call_id=call_id,
            object_references=tuple(dict.fromkeys(object_references)),
            max_attempts=max_attempts,
            available_at=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.jobs[job.job_id] = job
        self.request_index[key] = job.job_id
        return job

    async def get(self, job_id: UUID) -> PrivacyDeletionJob:
        return self.jobs[job_id]

    async def claim_next(
        self,
        worker_id: str,
        *,
        now: datetime | None = None,
        lease_seconds: int = 60,
    ) -> PrivacyDeletionJob | None:
        if not worker_id.strip():
            raise ValueError("worker_id is required.")
        timestamp = now or datetime.now(UTC)
        candidates = sorted(self.jobs.values(), key=lambda item: item.created_at)
        for job in candidates:
            ready = (
                job.state in {PrivacyJobState.QUEUED, PrivacyJobState.RETRY_WAIT}
                and job.available_at <= timestamp
            )
            expired_lease = (
                job.state is PrivacyJobState.RUNNING
                and job.lease_expires_at is not None
                and job.lease_expires_at <= timestamp
            )
            if job.attempt_count >= job.max_attempts or not (ready or expired_lease):
                continue
            claimed = replace(
                job,
                state=PrivacyJobState.RUNNING,
                lease_owner=worker_id,
                lease_expires_at=timestamp + timedelta(seconds=max(1, lease_seconds)),
                updated_at=timestamp,
            )
            self.jobs[job.job_id] = claimed
            return claimed
        return None

    def _leased(self, job_id: UUID, worker_id: str) -> PrivacyDeletionJob:
        job = self.jobs[job_id]
        if job.state is not PrivacyJobState.RUNNING or job.lease_owner != worker_id:
            raise PrivacyJobConflictError("Privacy job lease is not owned by worker.")
        return job

    async def is_legal_hold(self, job: PrivacyDeletionJob) -> bool:
        return (job.tenant_id, job.call_id) in self.holds or (
            job.tenant_id,
            None,
        ) in self.holds

    def set_legal_hold(
        self, tenant_id: UUID, call_id: UUID | None, hold: bool = True
    ) -> None:
        key = (tenant_id, call_id)
        if hold:
            self.holds.add(key)
            return
        self.holds.discard(key)
        # Releasing a hold requeues the jobs it parked, as PostgreSQL does.
        for job in list(self.jobs.values()):
            if job.state is not PrivacyJobState.HELD or job.tenant_id != tenant_id:
                continue
            if job.call_id == call_id or (
                job.call_id is None
                and not any(t == tenant_id for t, _ in self.holds)
            ):
                self.jobs[job.job_id] = replace(job, state=PrivacyJobState.QUEUED)

    async def hold(
        self, job_id: UUID, *, worker_id: str, now: datetime | None = None
    ) -> PrivacyDeletionJob:
        """Park a job behind a legal hold without consuming a retry."""
        job = self._leased(job_id, worker_id)
        updated = replace(
            job,
            state=PrivacyJobState.HELD,
            lease_owner=None,
            lease_expires_at=None,
            last_error_code="legal_hold",
            updated_at=now or datetime.now(UTC),
        )
        self.jobs[job_id] = updated
        return updated

    async def mark_object_deleted(
        self, job_id: UUID, *, worker_id: str, reference: str
    ) -> PrivacyDeletionJob:
        job = self._leased(job_id, worker_id)
        completed = tuple(dict.fromkeys((*job.completed_object_references, reference)))
        updated = replace(job, completed_object_references=completed)
        self.jobs[job_id] = updated
        return updated

    async def delete_database_data(
        self, job_id: UUID, *, worker_id: str
    ) -> PrivacyDeletionJob:
        job = self._leased(job_id, worker_id)
        if self.database_delete_failures:
            self.database_delete_failures -= 1
            raise RuntimeError("fixture database deletion failed")
        deletion = (job.kind, job.tenant_id, job.call_id)
        if deletion not in self.database_deletions:
            self.database_deletions.append(deletion)
        updated = replace(job, database_deleted=True)
        self.jobs[job_id] = updated
        return updated

    async def complete(
        self, job_id: UUID, *, worker_id: str, now: datetime | None = None
    ) -> PrivacyDeletionJob:
        job = self._leased(job_id, worker_id)
        if set(job.completed_object_references) != set(job.object_references):
            raise PrivacyJobConflictError(
                "Recording deletion checkpoint is incomplete."
            )
        if not job.database_deleted:
            raise PrivacyJobConflictError("Database deletion checkpoint is incomplete.")
        timestamp = now or datetime.now(UTC)
        updated = replace(
            job,
            state=PrivacyJobState.SUCCEEDED,
            lease_owner=None,
            lease_expires_at=None,
            last_error_code=None,
            updated_at=timestamp,
        )
        self.jobs[job_id] = updated
        return updated

    async def fail(
        self,
        job_id: UUID,
        *,
        worker_id: str,
        error_code: str,
        retryable: bool = True,
        now: datetime | None = None,
    ) -> PrivacyDeletionJob:
        job = self._leased(job_id, worker_id)
        timestamp = now or datetime.now(UTC)
        attempt = job.attempt_count + 1
        will_retry = retryable and attempt < job.max_attempts
        updated = replace(
            job,
            state=(
                PrivacyJobState.RETRY_WAIT
                if will_retry
                else PrivacyJobState.DEAD_LETTER
            ),
            attempt_count=attempt,
            available_at=(
                timestamp + timedelta(seconds=min(300, 2 ** (attempt - 1)))
                if will_retry
                else timestamp
            ),
            lease_owner=None,
            lease_expires_at=None,
            last_error_code=error_code[:64],
            updated_at=timestamp,
        )
        self.jobs[job_id] = updated
        return updated
