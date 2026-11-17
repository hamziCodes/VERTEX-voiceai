"""UCVE tenant Role-Based Access Control (RBAC) permission matrix.

Only tenant roles live here. Platform staff roles have their own explicit
matrix in ``control_plane.auth.platform_rbac`` and never grant tenant access.
"""

from __future__ import annotations


class RBACManager:
    """Permission matrix for tenant and compliance roles; no wildcard grants."""

    _matrix: dict[str, set[str]] = {
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
            "webhook:read",
            "webhook:write",
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
            "webhook:read",
            "webhook:write",
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
        """Return True only if the role explicitly holds ``resource:action``."""
        return f"{resource}:{action}" in cls.permissions_for_role(role)
