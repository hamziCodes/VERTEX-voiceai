"""Control Plane Tenant Alerts Configuration API Router Stub."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("/config/{tenant_id}")
async def update_alert_config(tenant_id: UUID, email: str | None = None, webhook_url: str | None = None) -> dict[str, Any]:
    """Configure tenant alert email and webhook destination."""
    return {
        "tenant_id": tenant_id,
        "email": email,
        "webhook_url": webhook_url,
        "status": "updated",
    }
