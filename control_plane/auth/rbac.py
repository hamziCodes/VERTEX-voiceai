"""UCVE Role-Based Access Control (RBAC) Permission Matrix."""

from __future__ import annotations

from typing import Any


class RBACManager:
    """RBAC policy matrix for platform_admin, tenant_admin, tenant_editor, tenant_viewer, and compliance_admin."""

    _matrix: dict[str, set[str]] = {
        "platform_admin": {"*"},
        "tenant_admin": {
            "agent:read", "agent:write", "session:mint", "session:read",
            "usage:read", "secret:rotate", "audit:read", "member:write"
        },
        "tenant_editor": {
            "agent:read", "agent:write", "session:mint", "session:read",
            "usage:read", "audit:read"
        },
        "tenant_viewer": {
            "agent:read", "session:read", "usage:read"
        },
        "compliance_admin": {
            "audit:read", "erasure:execute", "legal_hold:manage", "compliance:write"
        },
    }

    @classmethod
    def check_permission(cls, role: str, resource: str, action: str) -> bool:
        """Return True if role possesses permission for action on resource."""
        perm = f"{resource}:{action}"
        role_perms = cls._matrix.get(role.lower(), set())

        if "*" in role_perms or perm in role_perms or f"{resource}:*" in role_perms:
            return True

        return False
