"""Durable webhook target, delivery, and attempt contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WebhookTargetState(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"


class WebhookDeliveryState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    DEAD_LETTER = "dead_letter"


class WebhookAttemptOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    RETRYABLE_FAILURE = "retryable_failure"
    TERMINAL_FAILURE = "terminal_failure"


class TenantWebhookTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    name: str = Field(min_length=1, max_length=128)
    url: str = Field(min_length=1, max_length=2_048)
    credential_ref: str = Field(
        min_length=1,
        max_length=255,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$",
    )
    state: WebhookTargetState = WebhookTargetState.PENDING
    reviewed_by: str | None = Field(default=None, max_length=255)
    reviewed_at: datetime | None = None
    approved_addresses: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def active_target_has_review_evidence(self) -> TenantWebhookTarget:
        if self.state is WebhookTargetState.ACTIVE and (
            not self.reviewed_by
            or self.reviewed_at is None
            or not self.approved_addresses
        ):
            raise ValueError("Active webhook target requires review evidence.")
        return self


class WebhookDelivery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    delivery_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    target_id: UUID
    call_id: UUID
    result_id: UUID
    # None: the result was not flagged for review, so no approval is needed.
    review_id: UUID | None = None
    event_type: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=64, max_length=64)
    payload: dict[str, Any]
    state: WebhookDeliveryState = WebhookDeliveryState.QUEUED
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1, le=10)
    available_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    lease_owner: str | None = Field(default=None, max_length=128)
    lease_expires_at: datetime | None = None
    last_status_code: int | None = Field(default=None, ge=100, le=599)
    last_error_code: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WebhookDeliveryAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    delivery_id: UUID
    attempt_number: int = Field(ge=1)
    outcome: WebhookAttemptOutcome
    status_code: int | None = Field(default=None, ge=100, le=599)
    error_code: str | None = Field(default=None, max_length=64)
    duration_ms: int = Field(ge=0)
    response_body: None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
