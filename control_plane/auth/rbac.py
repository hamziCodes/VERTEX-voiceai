"""UCVE Role-Based Access Control (RBAC) Permission Matrix."""

from __future__ import annotations


class RBACManager:
    """Permission matrix for platform, tenant, and compliance roles."""

    _matrix: dict[str, set[str]] = {
        "platform_admin": {"*"},
        "tenant_admin": {
            "agent:read",
            "agent:write",
            "session:mint",
            "session:read",
            "usage:read",
            "secret:rotate",
            "audit:read",
            "member:read",
            "member:write",
            "onboarding:read",
            "onboarding:write",
            "entitlement:read",
            "knowledge:read",
            "knowledge:write",
            "extraction:read",
            "extraction:write",
            "alert:read",
            "alert:write",
            "telephony:read",
            "telephony:write",
            "conversation:read",
            "api_key:read",
            "api_key:write",
            "provider_credential:read",
            "provider_credential:write",
        },
        "tenant_editor": {
            "agent:read",
            "agent:write",
            "session:mint",
            "session:read",
            "usage:read",
            "audit:read",
            "member:read",
            "onboarding:read",
            "onboarding:write",
            "entitlement:read",
            "knowledge:read",
            "knowledge:write",
            "extraction:read",
            "extraction:write",
            "alert:read",
            "alert:write",
            "telephony:read",
            "conversation:read",
        },
        "tenant_developer": {
            "agent:read",
            "session:mint",
            "session:read",
            "usage:read",
            "entitlement:read",
            "telephony:read",
            "api_key:read",
            "api_key:write",
            "provider_credential:read",
        },
        "tenant_viewer": {
            "agent:read",
            "session:read",
            "usage:read",
            "onboarding:read",
            "entitlement:read",
            "knowledge:read",
            "extraction:read",
            "alert:read",
            "conversation:read",
        },
        "compliance_admin": {
            "audit:read",
            "erasure:execute",
            "legal_hold:manage",
            "compliance:write",
            "entitlement:read",
            "conversation:read",
        },
    }

    @classmethod
    def roles(cls) -> frozenset[str]:
        return frozenset(cls._matrix)

    @classmethod
    def permissions_for_role(cls, role: str) -> frozenset[str]:
        """Return an immutable permission snapshot for a normalized role."""

        return frozenset(cls._matrix.get(role.lower(), set()))

    @classmethod
    def check_permission(cls, role: str, resource: str, action: str) -> bool:
        """Return True if role possesses permission for action on resource."""
        perm = f"{resource}:{action}"
        role_perms = cls.permissions_for_role(role)

        if "*" in role_perms or perm in role_perms or f"{resource}:*" in role_perms:
            return True

        return False
