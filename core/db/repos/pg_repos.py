"""Postgres-backed tenant/session repository operations (H3)."""

from __future__ import annotations

import json
from typing import Any

from core.db.models import Agent, Session, Tenant
from core.db.pg import connect, use_memory_repos
from core.db.session import TenantScopedDBSession


class PostgresTenantRepository:
    """psycopg tenant/agent access under RLS session var."""

    def __init__(self, conn: Any | None = None) -> None:
        self._conn = conn

    def _connection(self) -> Any:
        return self._conn if self._conn is not None else connect()

    async def create_tenant(self, tenant: Tenant) -> Tenant:
        conn = self._connection()
        own = self._conn is None
        try:
            conn.execute(
                """
                INSERT INTO tenants (id, name, key_tier, allow_testing_providers, allowed_origins)
                VALUES (%s::uuid, %s, %s::key_tier_enum, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    tenant.id,
                    tenant.name,
                    tenant.key_tier,
                    tenant.allow_testing_providers,
                    tenant.allowed_origins,
                ),
            )
            if own:
                conn.commit()
        finally:
            if own:
                conn.close()
        return tenant

    async def get_tenant(self, tenant_id: str) -> Tenant | None:
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")
        conn = self._connection()
        own = self._conn is None
        try:
            TenantScopedDBSession(tenant_id).set_app_tenant_id(conn)
            row = conn.execute(
                "SELECT id::text, name, key_tier::text, allow_testing_providers, allowed_origins "
                "FROM tenants WHERE id = %s::uuid AND deleted_at IS NULL",
                (tenant_id,),
            ).fetchone()
            if not row:
                return None
            return Tenant(
                id=row[0],
                name=row[1],
                key_tier=row[2],
                allow_testing_providers=row[3],
                allowed_origins=list(row[4] or []),
            )
        finally:
            if own:
                conn.close()

    async def save_agent(self, agent: Agent) -> Agent:
        conn = self._connection()
        own = self._conn is None
        try:
            TenantScopedDBSession(agent.tenant_id).set_app_tenant_id(conn)
            conn.execute(
                """
                INSERT INTO agents (id, tenant_id, name, system_prompt, agent_provider_config)
                VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """,
                (
                    agent.id,
                    agent.tenant_id,
                    agent.name,
                    agent.system_prompt,
                    json.dumps(agent.agent_provider_config),
                ),
            )
            if own:
                conn.commit()
        finally:
            if own:
                conn.close()
        return agent

    async def get_agent_for_tenant(self, tenant_id: str, agent_id: str) -> Agent | None:
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")
        conn = self._connection()
        own = self._conn is None
        try:
            TenantScopedDBSession(tenant_id).set_app_tenant_id(conn)
            row = conn.execute(
                "SELECT id::text, tenant_id::text, name, system_prompt, agent_provider_config "
                "FROM agents WHERE id = %s::uuid AND tenant_id = %s::uuid",
                (agent_id, tenant_id),
            ).fetchone()
            if not row:
                # Distinguish cross-tenant vs missing
                other = conn.execute(
                    "SELECT tenant_id::text FROM agents WHERE id = %s::uuid",
                    (agent_id,),
                ).fetchone()
                if other and other[0] != tenant_id:
                    raise PermissionError(
                        f"Cross-tenant access blocked: tenant '{tenant_id}' requested agent '{agent_id}'."
                    )
                return None
            return Agent(
                id=row[0],
                tenant_id=row[1],
                name=row[2],
                system_prompt=row[3] or "",
                agent_provider_config=dict(row[4] or {}),
            )
        finally:
            if own:
                conn.close()


class PostgresSessionRepository:
    def __init__(self, conn: Any | None = None) -> None:
        self._conn = conn

    def _connection(self) -> Any:
        return self._conn if self._conn is not None else connect()

    async def create_session(self, tenant_id: str, session: Session) -> Session:
        if not tenant_id or session.tenant_id != tenant_id:
            raise PermissionError("Session tenant_id mismatch with query context.")
        conn = self._connection()
        own = self._conn is None
        try:
            TenantScopedDBSession(tenant_id).set_app_tenant_id(conn)
            conn.execute(
                """
                INSERT INTO sessions (
                    id, tenant_id, agent_id, transport_type, compliance_tier, degraded_flags
                ) VALUES (
                    %s::uuid, %s::uuid, %s::uuid, %s, %s::compliance_tier_enum, %s::jsonb
                )
                """,
                (
                    session.id,
                    session.tenant_id,
                    session.agent_id,
                    session.transport_type,
                    session.compliance_tier,
                    json.dumps(session.degraded_flags),
                ),
            )
            if own:
                conn.commit()
        finally:
            if own:
                conn.close()
        return session

    async def get_session(self, tenant_id: str, session_id: str) -> Session | None:
        conn = self._connection()
        own = self._conn is None
        try:
            TenantScopedDBSession(tenant_id).set_app_tenant_id(conn)
            row = conn.execute(
                "SELECT id::text, tenant_id::text, agent_id::text, transport_type, "
                "compliance_tier::text, degraded_flags FROM sessions "
                "WHERE id = %s::uuid AND tenant_id = %s::uuid",
                (session_id, tenant_id),
            ).fetchone()
            if not row:
                return None
            return Session(
                id=row[0],
                tenant_id=row[1],
                agent_id=row[2],
                transport_type=row[3],
                compliance_tier=row[4],
                degraded_flags=dict(row[5] or {}),
            )
        finally:
            if own:
                conn.close()


def build_tenant_repository() -> Any:
    if use_memory_repos():
        from core.db.repos.tenant_repo import TenantRepository

        return TenantRepository()
    return PostgresTenantRepository()


def build_session_repository() -> Any:
    if use_memory_repos():
        from core.db.repos.session_repo import SessionRepository

        return SessionRepository()
    return PostgresSessionRepository()
