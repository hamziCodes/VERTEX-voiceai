"""Dead Letter Queue (DLQ) Repository — 30-day TTL retention & max 3 attempt backoff."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

from core.errors.codes import UCVEErrorCode


class DeadLetterJob(BaseModel):
    """Dead letter queue item model with 30-day expiration TTL."""

    job_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(...)
    job_type: str = Field(..., description="e.g. post_call_dispatch")
    payload_ref: str = Field(..., description="Opaque reference string or call_id")
    error_code: UCVEErrorCode = Field(...)
    attempts: int = Field(default=1)
    max_attempts: int = Field(default=3)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30)  # 30-day TTL retention
    )


class DeadLetterQueueRepository:
    """In-memory & PostgreSQL dead-letter queue repository."""

    def __init__(self, db_pool: Any | None = None) -> None:
        self.db_pool = db_pool
        self._jobs: dict[UUID, DeadLetterJob] = {}

    def enqueue(self, tenant_id: UUID, job_type: str, payload_ref: str, error_code: UCVEErrorCode) -> DeadLetterJob:
        """Enqueue failed job into DLQ."""
        job = DeadLetterJob(
            tenant_id=tenant_id,
            job_type=job_type,
            payload_ref=payload_ref,
            error_code=error_code,
        )
        self._jobs[job.job_id] = job

        if self.db_pool:
            try:
                import asyncio

                async def _save_db() -> None:
                    async with self.db_pool.acquire() as conn:
                        await conn.execute("SET LOCAL app.current_tenant_id = $1", str(tenant_id))
                        await conn.execute(
                            """
                            INSERT INTO dead_letter_queue (
                                job_id, tenant_id, job_type, payload_ref, error_code, attempts, max_attempts, expires_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            """,
                            job.job_id,
                            tenant_id,
                            job_type,
                            payload_ref,
                            error_code.value,
                            job.attempts,
                            job.max_attempts,
                            job.expires_at,
                        )

                asyncio.create_task(_save_db())
            except Exception:
                pass
        return job

    def get_pending_retry(self) -> list[DeadLetterJob]:
        """Return jobs with attempts < max_attempts and not expired."""
        now = datetime.now(timezone.utc)
        return [j for j in self._jobs.values() if j.attempts < j.max_attempts and j.expires_at > now]

    def purge_expired(self) -> int:
        """Purge jobs past 30-day expiration TTL."""
        now = datetime.now(timezone.utc)
        expired_ids = [j.job_id for j in self._jobs.values() if j.expires_at <= now]
        for jid in expired_ids:
            del self._jobs[jid]
        return len(expired_ids)
