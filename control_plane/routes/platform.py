"""Internal Wavia platform API (Phase 13J).

Every route requires an explicit platform permission. Responses carry safe
metadata only: no credentials, key material, token hashes or customer content.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from control_plane.auth.platform import (
    PlatformContext,
    studio_repository,
    require_platform_permission,
    resolve_platform_context,
)
from control_plane.studio.models import PlatformRole
from control_plane.studio.repository import (
    DIRECTORY_MAX_LIMIT,
    DIRECTORY_MAX_OFFSET,
    DIRECTORY_MAX_QUERY,
    PLATFORM_AUDIT_MAX_LIMIT,
    REASON_MAX_LENGTH,
    REASON_MIN_LENGTH,
    LastPlatformAdminError,
    StaffNotFoundError,
    WorkspaceNotFoundError,
)

router = APIRouter(prefix="/v1/platform", tags=["platform"])

StaffContext = Annotated[PlatformContext, Depends(resolve_platform_context)]
TenantReader = Annotated[
    PlatformContext, Depends(require_platform_permission("platform_tenant:read"))
]
StaffReader = Annotated[
    PlatformContext, Depends(require_platform_permission("platform_staff:read"))
]
StaffWriter = Annotated[
    PlatformContext, Depends(require_platform_permission("platform_staff:write"))
]
AuditReader = Annotated[
    PlatformContext, Depends(require_platform_permission("platform_audit:read"))
]

Reason = Annotated[
    str, Field(min_length=REASON_MIN_LENGTH, max_length=REASON_MAX_LENGTH)
]


class GrantStaffBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    role: PlatformRole
    reason: Reason


class RevokeStaffBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


def _staff_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (StaffNotFoundError, WorkspaceNotFoundError)):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, LastPlatformAdminError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail="Permission denied.")
    return HTTPException(status_code=422, detail=str(exc))


@router.get("/me")
async def get_platform_identity(context: StaffContext) -> dict[str, Any]:
    return {
        "user_id": str(context.user_id),
        "email": context.email,
        "role": context.role,
        "capabilities": sorted(context.capabilities),
    }


@router.get("/tenants")
async def list_platform_tenants(
    request: Request,
    context: TenantReader,
    q: Annotated[str | None, Query(max_length=DIRECTORY_MAX_QUERY)] = None,
    limit: Annotated[int, Query(ge=1, le=DIRECTORY_MAX_LIMIT)] = 25,
    offset: Annotated[int, Query(ge=0, le=DIRECTORY_MAX_OFFSET)] = 0,
) -> dict[str, Any]:
    try:
        page = await studio_repository(request).list_tenant_directory(
            query=q, limit=limit, offset=offset
        )
    except ValueError as exc:
        raise _staff_error(exc) from exc
    return page.model_dump(mode="json")


@router.get("/tenants/{tenant_id}")
async def get_platform_tenant(
    tenant_id: UUID, request: Request, context: TenantReader
) -> dict[str, Any]:
    try:
        summary = await studio_repository(request).view_tenant_summary(
            tenant_id, actor_user_id=context.user_id
        )
    except (PermissionError, WorkspaceNotFoundError) as exc:
        raise _staff_error(exc) from exc
    return summary.model_dump(mode="json")


@router.get("/staff")
async def list_platform_staff(
    request: Request, context: StaffReader
) -> list[dict[str, Any]]:
    staff = await studio_repository(request).list_platform_staff()
    return [member.model_dump(mode="json") for member in staff]


@router.put("/staff")
async def grant_platform_staff(
    body: GrantStaffBody, request: Request, context: StaffWriter
) -> dict[str, Any]:
    try:
        member = await studio_repository(request).grant_platform_role(
            actor_user_id=context.user_id,
            email=body.email,
            role=body.role,
            reason=body.reason,
        )
    except (
        LastPlatformAdminError,
        PermissionError,
        StaffNotFoundError,
        ValueError,
    ) as exc:
        raise _staff_error(exc) from exc
    return member.model_dump(mode="json")


@router.post("/staff/{user_id}/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_platform_staff(
    user_id: UUID, body: RevokeStaffBody, request: Request, context: StaffWriter
) -> None:
    try:
        await studio_repository(request).revoke_platform_role(
            actor_user_id=context.user_id, user_id=user_id, reason=body.reason
        )
    except (
        LastPlatformAdminError,
        PermissionError,
        StaffNotFoundError,
        ValueError,
    ) as exc:
        raise _staff_error(exc) from exc


@router.get("/audit")
async def list_platform_audit(
    request: Request,
    context: AuditReader,
    limit: Annotated[int, Query(ge=1, le=PLATFORM_AUDIT_MAX_LIMIT)] = 50,
) -> list[dict[str, Any]]:
    events = await studio_repository(request).list_platform_audit(limit=limit)
    return [event.model_dump(mode="json") for event in events]
