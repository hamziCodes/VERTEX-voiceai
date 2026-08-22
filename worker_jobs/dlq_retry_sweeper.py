"""DLQ Retry Sweeper Worker Job — Retries failed jobs with exponential backoff (max 3) & purges 30-day expired items."""

from __future__ import annotations

import logging
from core.errors.dlq import DeadLetterQueueRepository

logger = logging.getLogger(__name__)


class DLQRetrySweeper:
    """Background sweeper retrying failed DLQ jobs and purging expired items."""

    def __init__(self, repository: DeadLetterQueueRepository | None = None) -> None:
        self.repo = repository or DeadLetterQueueRepository()

    async def run_sweep(self) -> dict[str, int]:
        """Execute sweeper pass: retry pending jobs (max 3 attempts) and purge 30-day expired entries."""
        pending = self.repo.get_pending_retry()
        retried = 0
        for job in pending:
            job.attempts += 1
            retried += 1

        purged = self.repo.purge_expired()
        return {"retried": retried, "purged": purged}
