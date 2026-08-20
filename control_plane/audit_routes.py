"""UCVE Control-Plane Audit Query Route Handlers."""

from __future__ import annotations

from typing import Any

from core.compliance.audit.queries import AuditQueries


def handle_get_audit_logs(
    tenant_id: str, requester_tenant_id: str, actor_role: str = "tenant_editor"
) -> tuple[int, dict[str, Any]]:
    """Endpoint handler for GET /v1/audit."""
    queries = AuditQueries()

    try:
        if actor_role == "platform_admin" and not tenant_id:
            logs = queries.query_all_audit_logs(actor_role=actor_role)
        else:
            logs = queries.query_tenant_audit_logs(
                tenant_id=tenant_id, requester_tenant_id=requester_tenant_id
            )

        return 200, {
            "status": "success",
            "count": len(logs),
            "events": [log.to_dict() for log in logs],
        }
    except PermissionError as exc:
        return 403, {"error": str(exc)}
