"""Human Review Queue Stub — Enqueues low-confidence extractions for manual review (Phase 27 UI target)."""

from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class HumanReviewItem(BaseModel):
    """Low-confidence extraction item queued for human review."""

    issue_id: UUID = Field(default_factory=uuid4)
    call_id: UUID = Field(...)
    tenant_id: UUID = Field(...)
    field_path: str = Field(...)
    extracted_value: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    status: ReviewStatus = Field(default=ReviewStatus.PENDING)


class HumanReviewQueue:
    """Queue stub for holding low-confidence extractions prior to CRM dispatch."""

    def __init__(self) -> None:
        self._items: dict[UUID, HumanReviewItem] = {}

    def enqueue(self, call_id: UUID, tenant_id: UUID, field_path: str, extracted_value: str | None, confidence: float) -> HumanReviewItem:
        item = HumanReviewItem(
            call_id=call_id,
            tenant_id=tenant_id,
            field_path=field_path,
            extracted_value=extracted_value,
            confidence=confidence,
            status=ReviewStatus.PENDING,
        )
        self._items[item.issue_id] = item
        return item

    def get_pending(self, tenant_id: UUID) -> list[HumanReviewItem]:
        return [item for item in self._items.values() if item.tenant_id == tenant_id and item.status == ReviewStatus.PENDING]
