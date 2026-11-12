"""Phase 13J: explicit platform staff permissions and no wildcard tenant access."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException

from control_plane.auth.api_keys import APIKeyManager
from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import enforce_tenant_access
from control_plane.auth.platform_rbac import (
    PLATFORM_ROLES,
    check_platform_permission,
    platform_permissions_for_role,
)
from control_plane.auth.rbac import RBACManager
from post_call.review.repository import ReviewAuthorizationError, _authorize_decision
from post_call.webhook.repository import WebhookAuthorizationError, _authorize

LAUNCH_TENANT_ROLES = frozenset(
    {
        "tenant_admin",
        "tenant_editor",
        "tenant_developer",
        "tenant_viewer",
        "compliance_admin",
    }
)


def _all_permission_sets() -> list[frozenset[str]]:
    tenant = [RBACManager.permissions_for_role(role) for role in RBACManager.roles()]
    platform = [platform_permissions_for_role(role) for role in PLATFORM_ROLES]
    return tenant + platform


def test_no_role_holds_a_wildcard_grant() -> None:
    for permissions in _all_permission_sets():
        assert "*" not in permissions
        assert not any(permission.endswith(":*") for permission in permissions)


def test_tenant_matrix_contains_only_launch_tenant_roles() -> None:
    assert RBACManager.roles() == LAUNCH_TENANT_ROLES
    assert RBACManager.permissions_for_role("platform_admin") == frozenset()
    assert RBACManager.check_permission("platform_admin", "agent", "write") is False
    assert RBACManager.check_permission("platform_admin", "agent", "read") is False


def test_platform_roles_hold_exactly_the_launch_permissions() -> None:
    from typing import get_args

    from control_plane.studio.models import PlatformRole

    assert PLATFORM_ROLES == ("platform_admin", "platform_support")
    assert get_args(PlatformRole) == PLATFORM_ROLES
    assert platform_permissions_for_role("platform_admin") == frozenset(
        {
            "platform_tenant:read",
            "platform_staff:read",
            "platform_staff:write",
            "platform_audit:read",
            "platform_support_session:read",
            "platform_support_session:write",
            "platform_support_session:manage",
            "platform_operations:read",
        }
    )
    assert platform_permissions_for_role("platform_support") == frozenset(
        {
            "platform_tenant:read",
            "platform_support_session:read",
            "platform_support_session:write",
        }
    )
    assert platform_permissions_for_role("tenant_admin") == frozenset()
    assert platform_permissions_for_role("unknown") == frozenset()


def test_platform_and_tenant_permissions_never_overlap() -> None:
    for role in RBACManager.roles():
        assert not any(
            permission.startswith("platform_")
            for permission in RBACManager.permissions_for_role(role)
        )
    for role in PLATFORM_ROLES:
        assert all(
            permission.startswith("platform_")
            for permission in platform_permissions_for_role(role)
        )


def test_platform_permission_checks_fail_closed() -> None:
    assert check_platform_permission("platform_admin", "platform_staff:write")
    assert check_platform_permission("platform_support", "platform_tenant:read")
    assert not check_platform_permission("platform_support", "platform_staff:write")
    assert not check_platform_permission("platform_support", "platform_audit:read")
    assert not check_platform_permission("platform_admin", "agent:write")
    assert not check_platform_permission("tenant_admin", "platform_tenant:read")
    assert not check_platform_permission("PLATFORM_ADMIN ", "platform_tenant:read")


def test_api_keys_cannot_carry_a_platform_role() -> None:
    manager = APIKeyManager()
    for role in ("platform_admin", "platform_support"):
        with pytest.raises(ValueError, match="Unknown API-key role"):
            manager.generate_api_key(str(uuid4()), "staff key", role=role)


def test_async_api_keys_cannot_carry_a_platform_role() -> None:
    from control_plane.auth.api_keys_async import AsyncAPIKeyManager

    manager = AsyncAPIKeyManager(database=object())
    with pytest.raises(ValueError, match="Unknown API-key role"):
        asyncio.run(
            manager.generate_api_key(str(uuid4()), "staff key", role="platform_admin")
        )


def _context(roles: tuple[str, ...], tenant_id: str, scopes: frozenset[str]):
    return AuthContext(
        subject_id="actor",
        tenant_id=tenant_id,
        roles=roles,
        scopes=scopes,
        auth_method="oidc",
    )


@pytest.mark.parametrize("role", ["platform_admin", "tenant_admin"])
def test_tenant_access_never_crosses_tenants(role: str) -> None:
    context = _context((role,), str(uuid4()), frozenset({"*"}))
    with pytest.raises(HTTPException) as caught:
        enforce_tenant_access(context, str(uuid4()))
    assert caught.value.status_code == 403
    enforce_tenant_access(context, context.tenant_id)


def test_post_call_review_and_webhook_reject_platform_cross_tenant() -> None:
    context = _context(("platform_admin",), str(uuid4()), frozenset())
    other_tenant = uuid4()
    with pytest.raises(ReviewAuthorizationError):
        _authorize_decision(other_tenant, context)
    with pytest.raises(WebhookAuthorizationError):
        _authorize(other_tenant, context)
    same_tenant = _context(("platform_admin",), str(other_tenant), frozenset())
    with pytest.raises(ReviewAuthorizationError):
        _authorize_decision(other_tenant, same_tenant)
    with pytest.raises(WebhookAuthorizationError):
        _authorize(other_tenant, same_tenant)
