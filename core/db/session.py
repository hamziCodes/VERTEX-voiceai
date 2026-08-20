"""UCVE Tenant-Scoped Database Session Factory & Runtime Bridge."""

from __future__ import annotations

from typing import Any

from core.fsm.turn_context import TurnContext


class TenantScopedDBSession:
    """Session context maintaining tenant isolation boundary for database queries."""

    def __init__(self, tenant_id: str) -> None:
        if not tenant_id or not isinstance(tenant_id, str):
            raise PermissionError("Tenant isolation violation: tenant_id is required.")
        self.tenant_id = tenant_id

    def set_app_tenant_id(self, cursor_or_conn: Any = None) -> str:
        """Set app.tenant_id for Postgres RLS (parameterized when connection provided)."""
        if cursor_or_conn is not None:
            # psycopg3: set_config(setting, value, is_local)
            cursor_or_conn.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (self.tenant_id,),
            )
            return "SET_CONFIG"
        # SQL fragment for callers that only need the statement text — still bind via %s
        return "SELECT set_config('app.tenant_id', %s, true)"

    def set_app_tenant_id_params(self) -> tuple[str, tuple[str]]:
        """Return (sql, params) for parameterized set_config."""
        return "SELECT set_config('app.tenant_id', %s, true)", (self.tenant_id,)


def session_context_factory(
    tenant_id: str,
    session_id: str,
    current_language: str = "en",
    degraded_flags: dict[str, Any] | None = None,
) -> TurnContext:
    """Runtime bridge constructing TurnContext populated with isolation keys from DB session."""
    if not tenant_id or not isinstance(tenant_id, str):
        raise PermissionError(
            "Tenant isolation violation: cannot instantiate TurnContext without tenant_id."
        )

    return TurnContext(
        session_id=session_id,
        tenant_id=tenant_id,
        current_language=current_language,
        turn_index=0,
        degraded_flags=degraded_flags or {},
    )
