"""Tenant view of operational alerts that concern the tenant (quota limits).

The earlier ``POST /v1/alerts/config/{tenant_id}`` endpoint echoed its input
and stored nothing; it was removed in Phase 14. Platform alert delivery is
configured through ``WAVIA_ALERT_WEBHOOK_URL``/``WAVIA_ALERT_WEBHOOK_SECRET``.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import enforce_tenant_access, require_permission

router = APIRouter(prefix="/alerts", tags=["alerts"])
AlertReader = Annotated[AuthContext, Depends(require_permission("alert:read"))]


@router.get("/{tenant_id}")
async def list_tenant_alerts(
    tenant_id: UUID,
    request: Request,
    auth: AlertReader,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    """Alerts raised for this tenant, newest first."""
    enforce_tenant_access(auth, str(tenant_id))
    service = request.app.state.alert_service
    alerts = await service.repository.list_tenant_alerts(tenant_id, limit=limit)
    return {"alerts": [alert.to_public() for alert in alerts]}
