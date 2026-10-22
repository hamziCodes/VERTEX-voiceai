"""Control Plane Tenant Alerts Configuration API Router Stub."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import enforce_tenant_access, require_permission

router = APIRouter(prefix="/alerts", tags=["alerts"])
AlertWriter = Annotated[AuthContext, Depends(require_permission("alert:write"))]


@router.post("/config/{tenant_id}")
async def update_alert_config(
    tenant_id: UUID,
    auth: AlertWriter,
    email: str | None = None,
    webhook_url: str | None = None,
) -> dict[str, Any]:
    """Configure tenant alert email and webhook destination."""
    enforce_tenant_access(auth, str(tenant_id))
    return {
        "tenant_id": tenant_id,
        "email": email,
        "webhook_url": webhook_url,
        "status": "updated",
    }
