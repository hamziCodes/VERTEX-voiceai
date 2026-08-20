"""UCVE Control-Plane Auth & Permission Middleware Helpers."""

from __future__ import annotations

from typing import Any

from control_plane.auth.rbac import RBACManager


def enforce_rbac(role: str, resource: str, action: str) -> None:
    """Enforce RBAC permissions, raising PermissionError if access is denied."""
    if not RBACManager.check_permission(role, resource, action):
        raise PermissionError(
            f"Role '{role}' is not authorized to perform action '{action}' on resource '{resource}'."
        )
