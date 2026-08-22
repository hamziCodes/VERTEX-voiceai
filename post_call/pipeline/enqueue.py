"""PostCallPipeline Enqueue Handler — Asynchronous post-call processing pipeline."""

from __future__ import annotations

import logging
from typing import Any

from post_call.models.call_record import CallRecord
from post_call.pipeline.recording_policy import RecordingPolicy

logger = logging.getLogger(__name__)


class PostCallPipeline:
    """Async pipeline for post-call processing, redaction, and CRM dispatch."""

    def __init__(self, repo: Any | None = None) -> None:
        self.repo = repo
        self.processed_records: list[CallRecord] = []

    async def enqueue(self, record: CallRecord) -> bool:
        """Enqueue and process a CallRecord.

        Fails persist gate if compliance tier requires recording but record has no recording.
        """
        has_rec = record.recording is not None
        if not RecordingPolicy.validate_record(record.compliance_tier, has_rec):
            logger.error("CallRecord failed compliance recording gate for tier '%s'", record.compliance_tier)
            raise ValueError(f"Recording is mandatory for compliance tier '{record.compliance_tier}'")

        if self.repo:
            await self.repo.save(record)

        self.processed_records.append(record)
        return True
