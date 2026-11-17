"""One authorization rule for routes and repositories (Stage 3 regression)."""

from __future__ import annotations

import pytest

from control_plane.auth.context import AuthContext
from control_plane.auth.rbac import actor_has_permission


def _ctx(role: str, method: str, *scopes: str) -> AuthContext:
    return AuthContext(
        subject_id="actor",
        tenant_id="00000000-0000-4000-8000-000000000001",
        roles=(role,),
        scopes=frozenset(scopes),
        auth_method=method,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("context", "permission", "allowed"),
    [
        # Signed-in members carry no scopes: the role decides.
        (_ctx("tenant_admin", "oidc"), "webhook:write", True),
        (_ctx("tenant_developer", "oidc"), "webhook:write", True),
        (_ctx("tenant_editor", "oidc"), "extraction:write", True),
        (_ctx("tenant_viewer", "oidc"), "extraction:write", False),
        (_ctx("tenant_editor", "oidc"), "webhook:write", False),
        # API keys need both the role and the scope.
        (_ctx("tenant_admin", "api_key", "webhook:write"), "webhook:write", True),
        (_ctx("tenant_admin", "api_key", "*"), "webhook:write", True),
        (_ctx("tenant_admin", "api_key", "webhook:read"), "webhook:write", False),
        (_ctx("tenant_viewer", "api_key", "*"), "extraction:write", False),
    ],
)
def test_actor_has_permission(
    context: AuthContext, permission: str, allowed: bool
) -> None:
    assert actor_has_permission(context, permission) is allowed
