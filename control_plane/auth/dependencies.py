"""FastAPI authentication, authorization, and tenant-boundary dependencies."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from inspect import isawaitable
from typing import Annotated

from fastapi import Header, HTTPException, Request

from control_plane.auth.context import AuthContext
from control_plane.auth.rbac import RBACManager
from control_plane.studio.dependencies import resolve_identity_context
from control_plane.studio.repository import (
    MembershipNotFoundError,
    StudioRepositoryError,
)


async def resolve_auth_context(
    request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
    x_actor_role: Annotated[str | None, Header(alias="X-Actor-Role")] = None,
) -> AuthContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        if token.startswith("ucve_live_"):
            verified = request.app.state.api_keys.verify_api_key(token)
            record = await verified if isawaitable(verified) else verified
            context = AuthContext(
                subject_id=str(record["subject_id"]),
                tenant_id=str(record["tenant_id"]),
                roles=(str(record["role"]).lower(),),
                scopes=frozenset(str(scope) for scope in record.get("scopes", ())),
                auth_method="api_key",
                key_id=str(record["key_id"]),
            )
        else:
            if not x_tenant_id:
                raise HTTPException(
                    status_code=400,
                    detail="X-Tenant-Id is required for tenant-scoped access.",
                )
            identity = await resolve_identity_context(request, authorization)
            repository = getattr(request.app.state, "studio_repository", None)
            if repository is None:
                raise RuntimeError("Studio identity repository is unavailable.")
            user = await repository.resolve_identity(identity)
            if not user.is_active:
                raise PermissionError("Identity is inactive.")
            memberships = await repository.list_memberships(user.user_id)
            membership = next(
                (
                    item
                    for item in memberships
                    if str(item.tenant_id) == x_tenant_id
                ),
                None,
            )
            if user.is_platform_admin:
                roles = ("platform_admin",)
            elif membership is not None:
                roles = (membership.role,)
            else:
                raise HTTPException(
                    status_code=403,
                    detail="Workspace membership is required.",
                )
            context = AuthContext(
                subject_id=str(user.user_id),
                tenant_id=x_tenant_id,
                roles=roles,
                scopes=frozenset(),
                auth_method="oidc",
                identity_issuer=identity.issuer,
                external_subject_id=identity.subject,
            )
    except HTTPException:
        raise
    except (
        KeyError,
        MembershipNotFoundError,
        PermissionError,
        RuntimeError,
        StudioRepositoryError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=401, detail="Invalid or unauthorized credential."
        ) from exc

    if x_tenant_id and x_tenant_id != context.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context mismatch.")
    if x_actor_role and x_actor_role.lower() not in context.roles:
        raise HTTPException(status_code=403, detail="Role context mismatch.")
    request.state.auth_context = context
    request.state.tenant_id = context.tenant_id
    return context


def require_permission(permission: str) -> Callable[..., Awaitable[AuthContext]]:
    resource, action = permission.split(":", 1)

    async def dependency(
        request: Request,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
        x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
        x_actor_role: Annotated[str | None, Header(alias="X-Actor-Role")] = None,
    ) -> AuthContext:
        context = await resolve_auth_context(
            request, authorization, x_tenant_id, x_actor_role
        )
        role_allowed = any(
            RBACManager.check_permission(role, resource, action)
            for role in context.roles
        )
        scope_allowed = "*" in context.scopes or permission in context.scopes
        if not role_allowed or (context.auth_method == "api_key" and not scope_allowed):
            raise HTTPException(status_code=403, detail="Permission denied.")
        return context

    return dependency


def enforce_tenant_access(context: AuthContext, requested_tenant: str) -> None:
    if requested_tenant != context.tenant_id and not context.is_platform_admin:
        raise HTTPException(status_code=403, detail="Cross-tenant access forbidden.")
