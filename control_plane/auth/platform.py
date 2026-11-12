"""Platform staff authorization (Phase 13J).

Platform routes never use tenant context. They accept only OIDC identities,
refuse ``X-Tenant-Id`` and ``X-Actor-Role``, and authorize from the durable
platform membership, never from token claims or the legacy boolean flag.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, cast
from uuid import UUID

from fastapi import Header, HTTPException, Request

from control_plane.auth.platform_rbac import (
    PlatformRole,
    check_platform_permission,
    platform_permissions_for_role,
)
from control_plane.studio.dependencies import resolve_identity_context
from control_plane.studio.repository import (
    IdentityConflictError,
    StudioRepository,
    StudioRepositoryError,
)


@dataclass(frozen=True, slots=True)
class PlatformContext:
    user_id: UUID
    email: str | None
    role: PlatformRole

    @property
    def capabilities(self) -> frozenset[str]:
        return platform_permissions_for_role(self.role)


def studio_repository(request: Request) -> StudioRepository:
    repository = getattr(request.app.state, "studio_repository", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="Studio repository unavailable.")
    return cast(StudioRepository, repository)


async def resolve_platform_context(
    request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
    x_actor_role: Annotated[str | None, Header(alias="X-Actor-Role")] = None,
) -> PlatformContext:
    identity = await resolve_identity_context(request, authorization)
    if x_tenant_id is not None or x_actor_role is not None:
        raise HTTPException(
            status_code=400,
            detail="Platform routes do not accept tenant or role context.",
        )
    repository = studio_repository(request)
    try:
        user = await repository.resolve_identity(identity)
        role = await repository.get_platform_role(user.user_id)
    except IdentityConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except StudioRepositoryError as exc:
        raise HTTPException(
            status_code=401, detail="Invalid or unauthorized credential."
        ) from exc
    if not user.is_active or role is None:
        raise HTTPException(status_code=403, detail="Platform staff role is required.")
    context = PlatformContext(user_id=user.user_id, email=user.email, role=role)
    request.state.platform_context = context
    return context


def require_platform_permission(
    permission: str,
) -> Callable[..., Awaitable[PlatformContext]]:
    async def dependency(
        request: Request,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
        x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
        x_actor_role: Annotated[str | None, Header(alias="X-Actor-Role")] = None,
    ) -> PlatformContext:
        context = await resolve_platform_context(
            request, authorization, x_tenant_id, x_actor_role
        )
        if not check_platform_permission(context.role, permission):
            raise HTTPException(status_code=403, detail="Permission denied.")
        return context

    return dependency
