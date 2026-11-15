"""Internal Wavia platform API (Phase 13J).

Every route requires an explicit platform permission. Responses carry safe
metadata only: no credentials, key material, token hashes or customer content.
"""

from __future__ import annotations

from inspect import isawaitable
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from control_plane.auth.platform import (
    PlatformContext,
    require_platform_permission,
    resolve_platform_context,
    studio_repository,
)
from control_plane.auth.platform_rbac import check_platform_permission
from control_plane.platform.operations import build_operations_snapshot
from control_plane.platform.support_views import (
    agent_projection,
    entitlements_projection,
    knowledge_base_projection,
    onboarding_projection,
    session_projection,
    telephony_projection,
)
from control_plane.studio.models import PlatformRole, SupportScope
from control_plane.studio.repository import (
    DIRECTORY_MAX_LIMIT,
    DIRECTORY_MAX_OFFSET,
    DIRECTORY_MAX_QUERY,
    PLATFORM_AUDIT_MAX_LIMIT,
    REASON_MAX_LENGTH,
    REASON_MIN_LENGTH,
    SUPPORT_LIST_MAX_LIMIT,
    SUPPORT_REFERENCE_MAX_LENGTH,
    LastPlatformAdminError,
    StaffNotFoundError,
    SupportSessionClosedError,
    SupportSessionConflictError,
    SupportSessionNotFoundError,
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
SupportReader = Annotated[
    PlatformContext,
    Depends(require_platform_permission("platform_support_session:read")),
]
SupportWriter = Annotated[
    PlatformContext,
    Depends(require_platform_permission("platform_support_session:write")),
]
OperationsReader = Annotated[
    PlatformContext, Depends(require_platform_permission("platform_operations:read"))
]
AlertsReader = Annotated[
    PlatformContext, Depends(require_platform_permission("platform_alerts:read"))
]
AlertsManager = Annotated[
    PlatformContext, Depends(require_platform_permission("platform_alerts:manage"))
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


class StartSupportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason
    reference: str | None = Field(default=None, max_length=SUPPORT_REFERENCE_MAX_LENGTH)
    scopes: list[SupportScope] = Field(min_length=1, max_length=2)
    duration_minutes: Literal[15, 30, 60]


class EndSupportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason | None = None


def _staff_error(exc: Exception) -> HTTPException:
    if isinstance(
        exc, (StaffNotFoundError, WorkspaceNotFoundError, SupportSessionNotFoundError)
    ):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (LastPlatformAdminError, SupportSessionConflictError)):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, SupportSessionClosedError):
        return HTTPException(status_code=410, detail=str(exc))
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


# ── Phase 13K: read-only support sessions ──────────────────────────────────

SupportErrors = (
    PermissionError,
    SupportSessionClosedError,
    SupportSessionConflictError,
    SupportSessionNotFoundError,
    ValueError,
    WorkspaceNotFoundError,
)


async def _resolve(value: Any) -> Any:
    return await value if isawaitable(value) else value


@router.post(
    "/tenants/{tenant_id}/support-sessions", status_code=status.HTTP_201_CREATED
)
async def start_support_session(
    tenant_id: UUID, body: StartSupportBody, request: Request, context: SupportWriter
) -> dict[str, Any]:
    try:
        session = await studio_repository(request).start_support_session(
            actor_user_id=context.user_id,
            tenant_id=tenant_id,
            reason=body.reason,
            reference=body.reference,
            scopes=tuple(body.scopes),
            duration_minutes=body.duration_minutes,
        )
    except SupportErrors as exc:
        raise _staff_error(exc) from exc
    return session_projection(session)


@router.get("/support-sessions")
async def list_support_sessions(
    request: Request,
    context: SupportReader,
    state: Literal["active", "recent"] = "recent",
    limit: Annotated[int, Query(ge=1, le=SUPPORT_LIST_MAX_LIMIT)] = 50,
) -> list[dict[str, Any]]:
    sessions = await studio_repository(request).list_support_sessions(
        state=state, limit=limit
    )
    return [session_projection(item) for item in sessions]


@router.get("/support-sessions/{session_id}")
async def get_support_session(
    session_id: UUID, request: Request, context: SupportReader
) -> dict[str, Any]:
    try:
        session = await studio_repository(request).get_support_session(session_id)
    except SupportErrors as exc:
        raise _staff_error(exc) from exc
    return session_projection(session)


@router.post("/support-sessions/{session_id}/end")
async def end_support_session(
    session_id: UUID, body: EndSupportBody, request: Request, context: SupportWriter
) -> dict[str, Any]:
    try:
        session = await studio_repository(request).end_support_session(
            actor_user_id=context.user_id,
            session_id=session_id,
            reason=body.reason,
            may_end_any=check_platform_permission(
                context.role, "platform_support_session:manage"
            ),
        )
    except SupportErrors as exc:
        raise _staff_error(exc) from exc
    return session_projection(session)


async def _authorize_read(
    request: Request, context: PlatformContext, session_id: UUID, scope: SupportScope
) -> Any:
    try:
        return await studio_repository(request).authorize_support_read(
            actor_user_id=context.user_id, session_id=session_id, scope=scope
        )
    except SupportErrors as exc:
        raise _staff_error(exc) from exc


@router.get("/support-sessions/{session_id}/configuration")
async def read_support_configuration(
    session_id: UUID, request: Request, context: SupportReader
) -> dict[str, Any]:
    from control_plane.routes.agents import get_agent_repo
    from core.db.repos.knowledge_repo import get_default_knowledge_repository

    session = await _authorize_read(request, context, session_id, "configuration")
    agents = await _resolve(get_agent_repo().list_agents(session.tenant_id))
    bases = await _resolve(
        get_default_knowledge_repository().list_knowledge_bases(session.tenant_id)
    )
    return {
        "session": session_projection(session),
        "agents": [agent_projection(agent) for agent in agents],
        "knowledge_bases": [knowledge_base_projection(base) for base in bases],
    }


@router.get("/support-sessions/{session_id}/readiness")
async def read_support_readiness(
    session_id: UUID, request: Request, context: SupportReader
) -> dict[str, Any]:
    session = await _authorize_read(request, context, session_id, "readiness")
    repository = studio_repository(request)
    try:
        onboarding = await repository.get_onboarding(session.tenant_id)
    except WorkspaceNotFoundError:
        onboarding = None
    try:
        entitlements = await repository.get_entitlements(session.tenant_id)
    except WorkspaceNotFoundError:
        entitlements = None
    telephony_repository = getattr(
        request.app.state, "telephony_settings_repository", None
    )
    telephony = (
        await telephony_repository.get(session.tenant_id)
        if telephony_repository is not None
        else None
    )
    return {
        "session": session_projection(session),
        "onboarding": onboarding_projection(onboarding),
        "entitlements": entitlements_projection(entitlements),
        "telephony": telephony_projection(telephony),
    }


@router.get("/alerts")
async def list_platform_alerts(
    request: Request,
    context: AlertsReader,
    alert_status: Annotated[
        Literal["open", "resolved"] | None, Query(alias="status")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    service = request.app.state.alert_service
    alerts = await service.repository.list_alerts(status=alert_status, limit=limit)
    return {"alerts": [alert.to_public() for alert in alerts]}


@router.post("/alerts/{alert_id}/resolve")
async def resolve_platform_alert(
    alert_id: UUID, request: Request, context: AlertsManager
) -> dict[str, Any]:
    service = request.app.state.alert_service
    resolved = await service.repository.resolve_by_id(
        alert_id, resolved_by=f"staff:{context.user_id}"
    )
    if resolved is None:
        raise HTTPException(status_code=404, detail="Open alert not found.")
    return resolved.to_public()


@router.get("/operations")
async def read_platform_operations(
    request: Request, context: OperationsReader
) -> dict[str, Any]:
    return await build_operations_snapshot(
        request.app.state, studio_repository(request)
    )
