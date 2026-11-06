"""OIDC-backed identity, workspace, and membership routes for Studio."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import enforce_tenant_access, require_permission
from control_plane.auth.rbac import RBACManager
from control_plane.studio.dependencies import resolve_identity_context
from control_plane.studio.models import IdentityContext, StudioRole, UserIdentity
from control_plane.studio.repository import (
    IdentityConflictError,
    InvitationConsumedError,
    InvitationEmailMismatchError,
    InvitationExpiredError,
    InvitationNotFoundError,
    LastAdminError,
    MembershipNotFoundError,
    StudioRepository,
    WorkspaceNotFoundError,
)

router = APIRouter(tags=["studio-identity"])
IdentityReader = Annotated[IdentityContext, Depends(resolve_identity_context)]
MemberReader = Annotated[AuthContext, Depends(require_permission("member:read"))]
MemberWriter = Annotated[AuthContext, Depends(require_permission("member:write"))]


class CreateWorkspaceBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class CreateInvitationBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: StudioRole = "tenant_viewer"
    expires_in_hours: int = Field(default=72, ge=1, le=168)


class AcceptInvitationBody(BaseModel):
    token: str = Field(min_length=20, max_length=1024)


class ChangeMemberRoleBody(BaseModel):
    role: StudioRole


def _repository(request: Request) -> StudioRepository:
    repository = getattr(request.app.state, "studio_repository", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="Studio repository unavailable.")
    return repository


async def _user_for_identity(
    request: Request, identity: IdentityContext
) -> UserIdentity:
    try:
        user = await _repository(request).resolve_identity(identity)
    except IdentityConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Identity is inactive.")
    return user


def _oidc_actor(auth: AuthContext) -> UUID:
    if auth.auth_method != "oidc":
        raise HTTPException(status_code=403, detail="OIDC identity required.")
    try:
        return UUID(auth.subject_id)
    except ValueError as exc:  # pragma: no cover - defensive invariant
        raise HTTPException(status_code=403, detail="OIDC identity required.") from exc


def _membership_error(exc: Exception) -> HTTPException:
    if isinstance(
        exc,
        (WorkspaceNotFoundError, MembershipNotFoundError, InvitationNotFoundError),
    ):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, InvitationExpiredError):
        return HTTPException(status_code=410, detail=str(exc))
    if isinstance(exc, (InvitationConsumedError, LastAdminError)):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, (InvitationEmailMismatchError, PermissionError)):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


@router.get("/v1/me")
async def get_current_identity(
    request: Request, identity: IdentityReader
) -> dict[str, Any]:
    user = await _user_for_identity(request, identity)
    memberships = await _repository(request).list_memberships(user.user_id)
    return {
        **user.model_dump(mode="json", exclude={"issuer", "subject"}),
        "memberships": [
            {
                **item.model_dump(mode="json"),
                "capabilities": sorted(RBACManager.permissions_for_role(item.role)),
            }
            for item in memberships
        ],
    }


@router.post("/v1/organizations", status_code=status.HTTP_201_CREATED)
async def create_workspace(
    body: CreateWorkspaceBody, request: Request, identity: IdentityReader
) -> dict[str, Any]:
    user = await _user_for_identity(request, identity)
    try:
        membership = await _repository(request).create_workspace(
            user.user_id, body.name
        )
    except (MembershipNotFoundError, ValueError) as exc:
        raise _membership_error(exc) from exc
    return membership.model_dump(mode="json")


@router.get("/v1/organizations/{tenant_id}/members")
async def list_workspace_members(
    tenant_id: UUID, request: Request, auth: MemberReader
) -> list[dict[str, Any]]:
    enforce_tenant_access(auth, str(tenant_id))
    try:
        members = await _repository(request).list_workspace_members(tenant_id)
    except WorkspaceNotFoundError as exc:
        raise _membership_error(exc) from exc
    return [item.model_dump(mode="json") for item in members]


@router.post(
    "/v1/organizations/{tenant_id}/invitations",
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace_invitation(
    tenant_id: UUID,
    body: CreateInvitationBody,
    request: Request,
    auth: MemberWriter,
) -> dict[str, Any]:
    enforce_tenant_access(auth, str(tenant_id))
    actor_id = _oidc_actor(auth)
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    try:
        invitation = await _repository(request).create_invitation(
            tenant_id,
            email=body.email,
            role=body.role,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(hours=body.expires_in_hours),
            invited_by=actor_id,
        )
    except (PermissionError, ValueError, WorkspaceNotFoundError) as exc:
        raise _membership_error(exc) from exc
    return {**invitation.model_dump(mode="json"), "token": token}


@router.post("/v1/invitations/accept")
async def accept_workspace_invitation(
    body: AcceptInvitationBody, request: Request, identity: IdentityReader
) -> dict[str, Any]:
    user = await _user_for_identity(request, identity)
    token_hash = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    try:
        membership = await _repository(request).accept_invitation(
            token_hash, user.user_id
        )
    except (
        InvitationConsumedError,
        InvitationEmailMismatchError,
        InvitationExpiredError,
        InvitationNotFoundError,
        MembershipNotFoundError,
        ValueError,
    ) as exc:
        raise _membership_error(exc) from exc
    return membership.model_dump(mode="json")


@router.patch("/v1/organizations/{tenant_id}/members/{user_id}")
async def change_workspace_member_role(
    tenant_id: UUID,
    user_id: UUID,
    body: ChangeMemberRoleBody,
    request: Request,
    auth: MemberWriter,
) -> dict[str, Any]:
    enforce_tenant_access(auth, str(tenant_id))
    try:
        membership = await _repository(request).set_member_role(
            tenant_id, user_id, body.role
        )
    except (LastAdminError, MembershipNotFoundError, ValueError) as exc:
        raise _membership_error(exc) from exc
    return membership.model_dump(mode="json")


@router.delete(
    "/v1/organizations/{tenant_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_workspace_member(
    tenant_id: UUID,
    user_id: UUID,
    request: Request,
    auth: MemberWriter,
) -> None:
    enforce_tenant_access(auth, str(tenant_id))
    try:
        await _repository(request).remove_member(tenant_id, user_id)
    except (LastAdminError, MembershipNotFoundError) as exc:
        raise _membership_error(exc) from exc
