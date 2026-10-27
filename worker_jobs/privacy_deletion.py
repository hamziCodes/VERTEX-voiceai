"""One-attempt worker for restart-safe retention and tenant erasure."""

from __future__ import annotations

from datetime import datetime
from typing import Any


class PrivacyDeletionWorker:
    def __init__(self, *, repository: Any, object_store: Any, worker_id: str) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id is required.")
        self.repository = repository
        self.object_store = object_store
        self.worker_id = worker_id

    async def _fail(self, job_id: Any, code: str, now: datetime | None) -> None:
        await self.repository.fail(
            job_id,
            worker_id=self.worker_id,
            error_code=code,
            retryable=True,
            now=now,
        )

    async def run_once(self, *, now: datetime | None = None) -> bool:
        job = await self.repository.claim_next(self.worker_id, now=now)
        if job is None:
            return False
        if await self.repository.is_legal_hold(job):
            await self._fail(job.job_id, "legal_hold", now)
            return True

        completed = set(job.completed_object_references)
        for reference in job.object_references:
            if reference in completed:
                continue
            try:
                deleted = await self.object_store.delete(reference)
            except Exception:
                await self._fail(job.job_id, "object_delete_failed", now)
                return True
            if deleted is False:
                await self._fail(job.job_id, "object_delete_failed", now)
                return True
            job = await self.repository.mark_object_deleted(
                job.job_id,
                worker_id=self.worker_id,
                reference=reference,
            )

        if await self.repository.is_legal_hold(job):
            await self._fail(job.job_id, "legal_hold_applied_during_delete", now)
            return True
        try:
            job = await self.repository.delete_database_data(
                job.job_id, worker_id=self.worker_id
            )
        except Exception:
            await self._fail(job.job_id, "database_delete_failed", now)
            return True
        await self.repository.complete(job.job_id, worker_id=self.worker_id, now=now)
        return True
