"""Tenant Webhook Target Registry Model."""

from __future__ import annotations

from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class TenantWebhookTarget(BaseModel):
    """Tenant configured webhook dispatch target."""

    target_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(...)
    url: str = Field(...)
    secret: str = Field(..., description="Shared HMAC signing secret (required, fails closed if missing)")
    enabled: bool = Field(default=True)
