"""UCVE Audit Query Engine with RBAC Scope Enforcement."""

from __future__ import annotations

from typing import Any

from core.compliance.audit.models import AuditEvent
from core.compliance.audit.writer import shared_audit_logs


class AuditQueries:
    """Read-only audit query engine enforcing tenant boundary and platform_admin cross-tenant access."""

    def __init__(
        self,
        logs: list[AuditEvent] | None = None,
        *,
        database: Any | None = None,
    ) -> None:
        self._logs = logs if logs is not None else shared_audit_logs()
        if database is None:
            from core.db.pg import use_memory_repos

            if not use_memory_repos():
                from core.db.async_pg import get_default_database

                database = get_default_database()
        self._database = database

    async def aquery_tenant_audit_logs(
        self, tenant_id: str, requester_tenant_id: str
    ) -> list[AuditEvent]:
        if not requester_tenant_id or tenant_id != requester_tenant_id:
            raise PermissionError(
                f"Cross-tenant audit read blocked: tenant '{requester_tenant_id}' "
                f"cannot query logs of tenant '{tenant_id}'."
            )
        if self._database is None:
            return self.query_tenant_audit_logs(tenant_id, requester_tenant_id)
        async with self._database.tenant_transaction(tenant_id) as connection:
            cursor = await connection.execute(
                "SELECT id::text, tenant_id::text, actor_id, actor_type, action, "
                "resource_type, resource_id, detail, ip, user_agent, created_at "
                "FROM audit_log WHERE tenant_id = %s::uuid "
                "ORDER BY created_at DESC",
                (tenant_id,),
            )
            rows = await cursor.fetchall()
        return [
            AuditEvent(
                id=row[0],
                tenant_id=row[1],
                actor_id=row[2],
                actor_type=row[3],
                action=row[4],
                resource_type=row[5],
                resource_id=row[6],
                detail=dict(row[7] or {}),
                ip=row[8],
                user_agent=row[9],
                created_at=row[10],
            )
            for row in rows
        ]

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
