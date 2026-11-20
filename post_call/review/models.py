"""Human-review request and decision contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ReviewState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class ReviewRequest(BaseModel):
    review_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    call_id: UUID
    result_id: UUID
    reasons: tuple[str, ...]
    state: ReviewState = ReviewState.PENDING
    decided_by: str | None = None
    decision_note: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decided_at: datetime | None = None
