"""Memory Embed Status Enum — Longitudinal RAG embedding status stub (Phase 23 dependency)."""

from __future__ import annotations

from enum import Enum


class MemoryEmbedStatus(str, Enum):
    """Status of post-call vector embedding for Phase 23 longitudinal memory."""

    PENDING = "pending"
    SKIPPED = "skipped"
    COMPLETE = "complete"
    FAILED = "failed"
