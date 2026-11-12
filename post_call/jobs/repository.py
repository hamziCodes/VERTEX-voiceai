"""Memory and PostgreSQL repositories for durable post-call jobs."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from core.db.async_pg import AsyncDatabase, get_default_database
from post_call.jobs.models import (
    PostCallIntelligenceResult,
    PostCallJob,
    PostCallJobState,
)
from post_call.review.models import ReviewRequest


class JobNotFoundError(LookupError):
    pass


class JobLeaseConflictError(RuntimeError):
    pass


class JobResultConflictError(RuntimeError):
    pass


class InMemoryPostCallJobRepository:
    """Local job repository sharing state with the in-memory call repository."""

    def __init__(self, call_repository: Any) -> None:
        self._jobs: dict[UUID, PostCallJob] = call_repository._post_call_jobs
        self._results: dict[tuple[UUID, UUID], PostCallIntelligenceResult] = (
            call_repository._post_call_results
        )
        self._reviews: dict[UUID, ReviewRequest] = call_repository._post_call_reviews

    async def create_job(
        self,
        *,
        tenant_id: UUID,
        call_id: UUID,
        payload: dict[str, Any],
        max_attempts: int = 3,
        now: datetime | None = None,
    ) -> PostCallJob:
        for job in self._jobs.values():
            if (
                job.tenant_id == tenant_id
                and job.call_id == call_id
                and job.job_type == "intelligence"
            ):
                return job.model_copy(deep=True)
        timestamp = now or datetime.now(UTC)
        job = PostCallJob(
            tenant_id=tenant_id,
            call_id=call_id,
            payload=dict(payload),
            max_attempts=max_attempts,
            available_at=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._jobs[job.job_id] = job
        return job.model_copy(deep=True)

    async def claim_next(
        self,
        worker_id: str,
        *,
        now: datetime | None = None,
        lease_seconds: int = 60,
    ) -> PostCallJob | None:
        if not worker_id.strip():
            raise ValueError("worker_id is required.")
        timestamp = now or datetime.now(UTC)
        candidates = sorted(self._jobs.values(), key=lambda item: item.created_at)
        for job in candidates:
            ready = (
                job.state
                in {
                    PostCallJobState.QUEUED,
                    PostCallJobState.RETRY_WAIT,
                }
                and job.available_at <= timestamp
            )
            expired = (
                job.state is PostCallJobState.RUNNING
                and job.lease_expires_at is not None
                and job.lease_expires_at <= timestamp
            )
            if not (ready or expired):
                continue
            job.state = PostCallJobState.RUNNING
            job.lease_owner = worker_id
            job.lease_expires_at = timestamp + timedelta(seconds=max(1, lease_seconds))
            job.updated_at = timestamp
            return job.model_copy(deep=True)
        return None

    async def count_jobs_by_state(self) -> dict[str, int]:
        """Aggregate counts only (Phase 13K operations health); no job content."""
        counts = {state.value: 0 for state in PostCallJobState}
        for job in self._jobs.values():
            counts[job.state.value] += 1
        return counts

    def _leased_job(self, job_id: UUID, worker_id: str) -> PostCallJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError("Post-call job not found.")
        if job.state is not PostCallJobState.RUNNING or job.lease_owner != worker_id:
            raise JobLeaseConflictError("Post-call job lease is not owned by worker.")
        return job

    async def fail_job(
        self,
        job_id: UUID,
        *,
        worker_id: str,
        error_code: str,
        safe_message: str,
        retryable: bool,
        now: datetime | None = None,
    ) -> PostCallJob:
        timestamp = now or datetime.now(UTC)
        job = self._leased_job(job_id, worker_id)
        job.attempt_count += 1
        job.last_error_code = error_code[:64]
        job.last_error_message = safe_message[:500]
        job.lease_owner = None
        job.lease_expires_at = None
        job.updated_at = timestamp
        if retryable and job.attempt_count < job.max_attempts:
            delay = min(300, 2 ** (job.attempt_count - 1))
            job.state = PostCallJobState.RETRY_WAIT
            job.available_at = timestamp + timedelta(seconds=delay)
        else:
            job.state = PostCallJobState.DEAD_LETTER
            job.available_at = timestamp
        return job.model_copy(deep=True)

    async def complete_job(
        self,
        job_id: UUID,
        *,
        worker_id: str,
        result: PostCallIntelligenceResult,
        review_reasons: tuple[str, ...] = (),
        now: datetime | None = None,
    ) -> PostCallJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError("Post-call job not found.")
        key = (result.tenant_id, result.call_id)
        existing = self._results.get(key)
        if job.state is PostCallJobState.SUCCEEDED:
            if existing == result:
                return job.model_copy(deep=True)
            raise JobResultConflictError("Completed job result is immutable.")
        job = self._leased_job(job_id, worker_id)
        if result.tenant_id != job.tenant_id or result.call_id != job.call_id:
            raise JobResultConflictError("Result does not belong to leased job.")
        if existing is not None and existing != result:
            raise JobResultConflictError("Call intelligence result already exists.")
        self._results[key] = result.model_copy(deep=True)
        if review_reasons and not any(
            review.tenant_id == result.tenant_id
            and review.result_id == result.result_id
            for review in self._reviews.values()
        ):
            review = ReviewRequest(
                tenant_id=result.tenant_id,
                call_id=result.call_id,
                result_id=result.result_id,
                reasons=tuple(sorted(set(review_reasons))),
            )
            self._reviews[review.review_id] = review
        timestamp = now or datetime.now(UTC)
        job.state = PostCallJobState.SUCCEEDED
        job.lease_owner = None
        job.lease_expires_at = None
        job.updated_at = timestamp
        return job.model_copy(deep=True)

    async def get_result(
        self, tenant_id: UUID, call_id: UUID
    ) -> PostCallIntelligenceResult | None:
        result = self._results.get((tenant_id, call_id))
        return result.model_copy(deep=True) if result is not None else None

    async def get_review_for_result(
        self, tenant_id: UUID, result_id: UUID
    ) -> ReviewRequest | None:
        for review in self._reviews.values():
            if review.tenant_id == tenant_id and review.result_id == result_id:
                return review.model_copy(deep=True)
        return None


class PostgresPostCallJobRepository:
    """PostgreSQL outbox with lease ownership and atomic result/review commit."""

    def __init__(self, database: AsyncDatabase | Any | None = None) -> None:
        self.database = database or get_default_database()

    async def count_jobs_by_state(self) -> dict[str, int]:
        """Aggregate counts across tenants for platform operations health only."""
        counts = {state.value: 0 for state in PostCallJobState}
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT state, COUNT(*) FROM post_call_jobs GROUP BY state"
            )
            for state, count in await cursor.fetchall():
                if state in counts:
                    counts[state] = int(count)
        return counts

    @staticmethod
    def _job_from_row(row: Any) -> PostCallJob:
        return PostCallJob(
            job_id=row[0],
            tenant_id=row[1],
            call_id=row[2],
            job_type=row[3],
            state=PostCallJobState(row[4]),
            payload=row[5] or {},
            attempt_count=row[6],
            max_attempts=row[7],
            available_at=row[8],
            lease_owner=row[9],
            lease_expires_at=row[10],
            last_error_code=row[11],
            last_error_message=row[12],
            created_at=row[13],
            updated_at=row[14],
        )

    @staticmethod
    def _result_from_row(row: Any) -> PostCallIntelligenceResult:
        return PostCallIntelligenceResult(
            result_id=row[0],
            tenant_id=row[1],
            call_id=row[2],
            extraction=row[3],
            summary=row[4],
            verification_issue_codes=tuple(row[5] or ()),
            provider_snapshot=row[6] or {},
            created_at=row[7],
        )

    @staticmethod
    def _job_select() -> str:
        return (
            "job_id, tenant_id, call_id, job_type, state, payload_jsonb, "
            "attempt_count, max_attempts, available_at, lease_owner, "
            "lease_expires_at, last_error_code, last_error_message, "
            "created_at, updated_at"
        )

    async def create_job(
        self,
        *,
        tenant_id: UUID,
        call_id: UUID,
        payload: dict[str, Any],
        max_attempts: int = 3,
        now: datetime | None = None,
    ) -> PostCallJob:
        timestamp = now or datetime.now(UTC)
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "INSERT INTO post_call_jobs "
                "(tenant_id, call_id, payload_jsonb, max_attempts, available_at, "
                "created_at, updated_at) VALUES "
                "(%s::uuid, %s::uuid, %s::jsonb, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, call_id, job_type) DO UPDATE SET "
                "updated_at = post_call_jobs.updated_at RETURNING "
                + self._job_select(),
                (
                    str(tenant_id),
                    str(call_id),
                    json.dumps(payload),
                    max_attempts,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            row = await cursor.fetchone()
        return self._job_from_row(row)

    async def claim_next(
        self,
        worker_id: str,
        *,
        now: datetime | None = None,
        lease_seconds: int = 60,
    ) -> PostCallJob | None:
        if not worker_id.strip():
            raise ValueError("worker_id is required.")
        timestamp = now or datetime.now(UTC)
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT "
                + self._job_select()
                + " FROM post_call_jobs WHERE attempt_count < max_attempts AND "
                "(((state = 'queued' OR state = 'retry_wait') AND available_at <= %s) "
                "OR (state = 'running' AND lease_expires_at <= %s)) "
                "ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1",
                (timestamp, timestamp),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            lease_expires = timestamp + timedelta(seconds=max(1, lease_seconds))
            claimed = await connection.execute(
                "UPDATE post_call_jobs SET state = 'running', lease_owner = %s, "
                "lease_expires_at = %s, updated_at = %s WHERE job_id = %s::uuid "
                "RETURNING " + self._job_select(),
                (worker_id, lease_expires, timestamp, str(row[0])),
            )
            claimed_row = await claimed.fetchone()
        return self._job_from_row(claimed_row)

    async def fail_job(
        self,
        job_id: UUID,
        *,
        worker_id: str,
        error_code: str,
        safe_message: str,
        retryable: bool,
        now: datetime | None = None,
    ) -> PostCallJob:
        timestamp = now or datetime.now(UTC)
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT "
                + self._job_select()
                + " FROM post_call_jobs WHERE job_id = %s::uuid FOR UPDATE",
                (str(job_id),),
            )
            row = await cursor.fetchone()
            if row is None:
                raise JobNotFoundError("Post-call job not found.")
            job = self._job_from_row(row)
            if (
                job.state is not PostCallJobState.RUNNING
                or job.lease_owner != worker_id
            ):
                raise JobLeaseConflictError(
                    "Post-call job lease is not owned by worker."
                )
            attempt = job.attempt_count + 1
            will_retry = retryable and attempt < job.max_attempts
            state = (
                PostCallJobState.RETRY_WAIT
                if will_retry
                else PostCallJobState.DEAD_LETTER
            )
            available = (
                timestamp + timedelta(seconds=min(300, 2 ** (attempt - 1)))
                if will_retry
                else timestamp
            )
            updated = await connection.execute(
                "UPDATE post_call_jobs SET state = %s, attempt_count = %s, "
                "available_at = %s, lease_owner = NULL, lease_expires_at = NULL, "
                "last_error_code = %s, last_error_message = %s, updated_at = %s "
                "WHERE job_id = %s::uuid RETURNING " + self._job_select(),
                (
                    state.value,
                    attempt,
                    available,
                    error_code[:64],
                    safe_message[:500],
                    timestamp,
                    str(job_id),
                ),
            )
            updated_row = await updated.fetchone()
        return self._job_from_row(updated_row)

    async def complete_job(
        self,
        job_id: UUID,
        *,
        worker_id: str,
        result: PostCallIntelligenceResult,
        review_reasons: tuple[str, ...] = (),
        now: datetime | None = None,
    ) -> PostCallJob:
        timestamp = now or datetime.now(UTC)
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT "
                + self._job_select()
                + " FROM post_call_jobs WHERE job_id = %s::uuid FOR UPDATE",
                (str(job_id),),
            )
            row = await cursor.fetchone()
            if row is None:
                raise JobNotFoundError("Post-call job not found.")
            job = self._job_from_row(row)
            if job.state is PostCallJobState.SUCCEEDED:
                return job
            if (
                job.state is not PostCallJobState.RUNNING
                or job.lease_owner != worker_id
            ):
                raise JobLeaseConflictError(
                    "Post-call job lease is not owned by worker."
                )
            if result.tenant_id != job.tenant_id or result.call_id != job.call_id:
                raise JobResultConflictError("Result does not belong to leased job.")
            await connection.execute(
                "INSERT INTO post_call_intelligence_results "
                "(result_id, tenant_id, call_id, extraction_jsonb, summary_jsonb, "
                "verification_issue_codes, provider_snapshot, created_at) VALUES "
                "(%s::uuid, %s::uuid, %s::uuid, %s::jsonb, %s::jsonb, %s::jsonb, "
                "%s::jsonb, %s) ON CONFLICT (tenant_id, call_id) DO NOTHING",
                (
                    str(result.result_id),
                    str(result.tenant_id),
                    str(result.call_id),
                    json.dumps(result.extraction)
                    if result.extraction is not None
                    else None,
                    json.dumps(result.summary) if result.summary is not None else None,
                    json.dumps(list(result.verification_issue_codes)),
                    json.dumps(result.provider_snapshot),
                    result.created_at,
                ),
            )
            if review_reasons:
                await connection.execute(
                    "INSERT INTO post_call_review_requests "
                    "(review_id, tenant_id, call_id, result_id, reasons_jsonb) "
                    "VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::jsonb) "
                    "ON CONFLICT (tenant_id, result_id) DO NOTHING",
                    (
                        str(uuid4()),
                        str(result.tenant_id),
                        str(result.call_id),
                        str(result.result_id),
                        json.dumps(list(sorted(set(review_reasons)))),
                    ),
                )
            updated = await connection.execute(
                "UPDATE post_call_jobs SET state = 'succeeded', lease_owner = NULL, "
                "lease_expires_at = NULL, last_error_code = NULL, "
                "last_error_message = NULL, updated_at = %s "
                "WHERE job_id = %s::uuid RETURNING " + self._job_select(),
                (timestamp, str(job_id)),
            )
            updated_row = await updated.fetchone()
        return self._job_from_row(updated_row)

    async def get_result(
        self, tenant_id: UUID, call_id: UUID
    ) -> PostCallIntelligenceResult | None:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "SELECT result_id, tenant_id, call_id, extraction_jsonb, "
                "summary_jsonb, verification_issue_codes, provider_snapshot, "
                "created_at FROM post_call_intelligence_results "
                "WHERE tenant_id = %s::uuid AND call_id = %s::uuid",
                (str(tenant_id), str(call_id)),
            )
            row = await cursor.fetchone()
        return self._result_from_row(row) if row is not None else None

    async def get_review_for_result(
        self, tenant_id: UUID, result_id: UUID
    ) -> ReviewRequest | None:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "SELECT review_id, tenant_id, call_id, result_id, reasons_jsonb, "
                "state, decided_by, decision_note, created_at, decided_at "
                "FROM post_call_review_requests WHERE tenant_id = %s::uuid "
                "AND result_id = %s::uuid",
                (str(tenant_id), str(result_id)),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return ReviewRequest(
            review_id=row[0],
            tenant_id=row[1],
            call_id=row[2],
            result_id=row[3],
            reasons=tuple(row[4]),
            state=row[5],
            decided_by=row[6],
            decision_note=row[7],
            created_at=row[8],
            decided_at=row[9],
        )
