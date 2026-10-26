"""Durable post-call job and intelligence-result contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PostCallJobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    DEAD_LETTER = "dead_letter"


class PostCallJob(BaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    call_id: UUID
    job_type: str = "intelligence"
    state: PostCallJobState = PostCallJobState.QUEUED
    payload: dict[str, Any] = Field(default_factory=dict)
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1, le=10)
    available_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PostCallIntelligenceResult(BaseModel):
    result_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    call_id: UUID
    extraction: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    verification_issue_codes: tuple[str, ...] = ()
    provider_snapshot: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
