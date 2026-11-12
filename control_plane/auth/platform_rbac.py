"""Explicit Wavia platform staff permissions (Phase 13J).

Platform roles are separate from tenant roles. They never satisfy a tenant
permission, and no role holds a wildcard: every capability is enumerated.
"""

from __future__ import annotations

from typing import Literal

PlatformRole = Literal["platform_admin", "platform_support"]

PLATFORM_ROLES: tuple[PlatformRole, ...] = ("platform_admin", "platform_support")

_PLATFORM_MATRIX: dict[str, frozenset[str]] = {
    "platform_admin": frozenset(
        {
            "platform_tenant:read",
            "platform_staff:read",
            "platform_staff:write",
            "platform_audit:read",
        }
    ),
    "platform_support": frozenset({"platform_tenant:read"}),
}


def platform_permissions_for_role(role: str) -> frozenset[str]:
    """Return the exact permissions for a platform role; unknown roles get none."""

    return _PLATFORM_MATRIX.get(role, frozenset())


def check_platform_permission(role: str, permission: str) -> bool:
    """Return True only when the role explicitly holds the permission."""

    return permission in platform_permissions_for_role(role)
