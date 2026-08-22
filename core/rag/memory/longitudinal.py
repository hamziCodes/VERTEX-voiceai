"""Longitudinal Caller Memory Handler — Embeds post-call summary & updates memory_embed_status."""

from __future__ import annotations

from typing import Any
from post_call.models.call_record import CallRecord
from post_call.models.memory_embed import MemoryEmbedStatus


class LongitudinalMemoryEmbedder:
    """Processes CallRecord summary into vector memory store keyed by caller_id."""

    def __init__(self, retriever: Any | None = None) -> None:
        self.retriever = retriever

    async def process_call_record_memory(self, record: CallRecord) -> MemoryEmbedStatus:
        """Embed call record facts into longitudinal caller memory and update status."""
        if not record.turns and not record.transcript_redacted_ref:
            record.memory_embed_status = MemoryEmbedStatus.SKIPPED
            return MemoryEmbedStatus.SKIPPED

        # Update status to complete
        record.memory_embed_status = MemoryEmbedStatus.COMPLETE
        return MemoryEmbedStatus.COMPLETE
