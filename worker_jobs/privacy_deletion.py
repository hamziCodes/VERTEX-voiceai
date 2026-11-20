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
            # A hold is not a failure: park the job (no retry consumed, no dead
            # letter). Releasing the hold requeues it.
            await self.repository.hold(job.job_id, worker_id=self.worker_id, now=now)
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

        swept = 0
        sweep = getattr(self.object_store, "delete_tenant_objects", None)
        if job.kind.value == "tenant_erasure" and callable(sweep):
            # Recordings not listed on the job (or written after it) still sit
            # under the tenant's prefix; erase them all.
            try:
                swept = await sweep(job.tenant_id)
            except Exception:
                await self._fail(job.job_id, "object_prefix_sweep_failed", now)
                return True
        record = getattr(self.repository, "record_event", None)
        if callable(record):
            await record(
                job,
                "objects_deleted",
                counts={"listed": len(job.object_references), "swept": swept},
            )

        if await self.repository.is_legal_hold(job):
            await self.repository.hold(job.job_id, worker_id=self.worker_id, now=now)
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
