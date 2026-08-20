"""UCVE Audit Query Engine with RBAC Scope Enforcement."""

from __future__ import annotations

from core.compliance.audit.models import AuditEvent


class AuditQueries:
    """Read-only audit query engine enforcing tenant boundary and platform_admin cross-tenant access."""

    def __init__(self, logs: list[AuditEvent] | None = None) -> None:
        self._logs = logs or []

    def query_tenant_audit_logs(
        self, tenant_id: str, requester_tenant_id: str
    ) -> list[AuditEvent]:
        """Query audit logs scoped to single tenant."""
        if not requester_tenant_id or tenant_id != requester_tenant_id:
            raise PermissionError(
                f"Cross-tenant audit read blocked: tenant '{requester_tenant_id}' cannot query logs of tenant '{tenant_id}'."
            )

        return [log for log in self._logs if log.tenant_id == tenant_id]

    def query_all_audit_logs(self, actor_role: str) -> list[AuditEvent]:
        """Query cross-tenant audit logs (requires platform_admin role)."""
        if actor_role != "platform_admin":
            raise PermissionError(
                f"Cross-tenant full audit query requires 'platform_admin' role (got '{actor_role}')."
            )

        return list(self._logs)
