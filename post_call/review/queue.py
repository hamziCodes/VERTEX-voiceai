"""Human Review Queue Stub — Enqueues low-confidence extractions for manual review (Phase 27 UI target)."""

from __future__ import annotations

from enum import Enum
from typing import Any
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
    """Queue for holding low-confidence extractions prior to CRM dispatch."""

    def __init__(self, db_pool: Any | None = None) -> None:
        self.db_pool = db_pool
        self._items: dict[UUID, HumanReviewItem] = {}

    def enqueue(
        self,
        call_id: UUID,
        tenant_id: UUID,
        field_path: str,
        extracted_value: str | None,
        confidence: float,
    ) -> HumanReviewItem:
        item = HumanReviewItem(
            call_id=call_id,
            tenant_id=tenant_id,
            field_path=field_path,
            extracted_value=extracted_value,
            confidence=confidence,
            status=ReviewStatus.PENDING,
        )
        self._items[item.issue_id] = item

        if self.db_pool:
            try:
                import asyncio

                async def _save_db() -> None:
                    async with self.db_pool.acquire() as conn:
                        await conn.execute("SET LOCAL app.current_tenant_id = $1", str(tenant_id))
                        await conn.execute(
                            """
                            INSERT INTO human_review_queue (
                                issue_id, call_id, tenant_id, field_path, extracted_value, confidence, status
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                            """,
                            item.issue_id,
                            call_id,
                            tenant_id,
                            field_path,
                            extracted_value,
                            confidence,
                            item.status.value,
                        )

                asyncio.create_task(_save_db())
            except Exception:
                pass
        return item

    def get_pending(self, tenant_id: UUID) -> list[HumanReviewItem]:
        return [
            item
            for item in self._items.values()
            if item.tenant_id == tenant_id and item.status == ReviewStatus.PENDING
        ]
