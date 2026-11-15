"""Legacy sweeper over the in-memory ``DeadLetterQueueRepository``.

Not scheduled by the jobs runner: production dead letters live in the durable
``post_call_jobs``/``webhook_deliveries``/``privacy_deletion_jobs`` tables,
which retry with backoff themselves and are observed by ``queue_observer``.
Phase 14 removed the fake success: a retry is only counted when a real
``redispatch`` callback accepted the job. Classified delete-proposed.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from core.errors.dlq import DeadLetterJob, DeadLetterQueueRepository

logger = logging.getLogger(__name__)


class DLQRetrySweeper:
    """Background sweeper retrying failed DLQ jobs and purging expired items."""

    def __init__(
        self,
        repository: DeadLetterQueueRepository | None = None,
        *,
        redispatch: Callable[[DeadLetterJob], Awaitable[bool]] | None = None,
    ) -> None:
        self.repo = repository or DeadLetterQueueRepository()
        self.redispatch = redispatch

    async def run_sweep(self) -> dict[str, int]:
        """Re-dispatch eligible jobs through ``redispatch`` and purge expired ones."""
        pending = self.repo.get_pending_retry()
        retried = 0
        unavailable = 0
        for job in pending:
            if self.redispatch is None:
                unavailable += 1
                continue
            job.attempts += 1
            if await self.redispatch(job):
                retried += 1
        purged = self.repo.purge_expired()
        return {
            "eligible": len(pending),
            "retried": retried,
            "redispatch_unavailable": unavailable,
            "purged": purged,
        }
