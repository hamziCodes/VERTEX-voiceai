"""Async Psycopg tenant and session repositories."""

from __future__ import annotations

import json
from typing import Any

from core.db.async_pg import AsyncDatabase, get_default_database
from core.db.models import Agent, Session, Tenant
from core.db.pg import use_memory_repos


class PostgresTenantRepository:
    def __init__(self, database: AsyncDatabase | Any | None = None) -> None:
        self.database = database or get_default_database()

    async def create_tenant(self, tenant: Tenant) -> Tenant:
        async with self.database.tenant_transaction(tenant.id) as connection:
            await connection.execute(
                """
                INSERT INTO tenants (
                    id, name, key_tier, allow_testing_providers, allowed_origins
                ) VALUES (%s::uuid, %s, %s::key_tier_enum, %s, %s)
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
        return tenant

    async def get_tenant(self, tenant_id: str) -> Tenant | None:
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")
        async with self.database.tenant_transaction(tenant_id) as connection:
            cursor = await connection.execute(
                "SELECT id::text, name, key_tier::text, "
                "allow_testing_providers, allowed_origins "
                "FROM tenants WHERE id = %s::uuid AND deleted_at IS NULL",
                (tenant_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return Tenant(
            id=row[0],
            name=row[1],
            key_tier=row[2],
            allow_testing_providers=row[3],
            allowed_origins=list(row[4] or []),
        )

    async def save_agent(self, agent: Agent) -> Agent:
        async with self.database.tenant_transaction(agent.tenant_id) as connection:
            await connection.execute(
                """
                INSERT INTO agents (
                    id, tenant_id, name, system_prompt, agent_provider_config
                ) VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    system_prompt = EXCLUDED.system_prompt,
                    agent_provider_config = EXCLUDED.agent_provider_config,
                    updated_at = NOW()
                """,
                (
                    agent.id,
                    agent.tenant_id,
                    agent.name,
                    agent.system_prompt,
                    json.dumps(agent.agent_provider_config),
                ),
            )
        return agent

    async def get_agent_for_tenant(self, tenant_id: str, agent_id: str) -> Agent | None:
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")
        async with self.database.tenant_transaction(tenant_id) as connection:
            cursor = await connection.execute(
                "SELECT id::text, tenant_id::text, name, system_prompt, "
                "agent_provider_config FROM agents "
                "WHERE id = %s::uuid AND tenant_id = %s::uuid",
                (agent_id, tenant_id),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return Agent(
            id=row[0],
            tenant_id=row[1],
            name=row[2],
            system_prompt=row[3] or "",
            agent_provider_config=dict(row[4] or {}),
        )


class PostgresSessionRepository:
    def __init__(self, database: AsyncDatabase | Any | None = None) -> None:
        self.database = database or get_default_database()

    async def create_session(self, tenant_id: str, session: Session) -> Session:
        if not tenant_id or session.tenant_id != tenant_id:
            raise PermissionError("Session tenant_id mismatch with query context.")
        async with self.database.tenant_transaction(tenant_id) as connection:
            await connection.execute(
                """
                INSERT INTO sessions (
                    id, tenant_id, agent_id, transport_type, compliance_tier,
                    config_version_id, agent_config_version, runtime_plan_hash,
                    runtime_plan_snapshot, session_language, session_voice_id,
                    pinned_at, degraded_flags
                ) VALUES (
                    %s::uuid, %s::uuid, %s::uuid, %s, %s::compliance_tier_enum,
                    %s::uuid, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb
                )
                """,
                (
                    session.id,
                    session.tenant_id,
                    session.agent_id,
                    session.transport_type,
                    session.compliance_tier,
                    session.config_version_id,
                    session.agent_config_version,
                    session.runtime_plan_hash,
                    json.dumps(session.runtime_plan_snapshot),
                    session.session_language,
                    session.session_voice_id,
                    session.pinned_at,
                    json.dumps(session.degraded_flags),
                ),
            )
        return session

    async def get_session(self, tenant_id: str, session_id: str) -> Session | None:
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")
        async with self.database.tenant_transaction(tenant_id) as connection:
            cursor = await connection.execute(
                """
                SELECT id::text, tenant_id::text, agent_id::text,
                       transport_type, compliance_tier::text,
                       config_version_id::text, agent_config_version,
                       runtime_plan_hash, runtime_plan_snapshot,
                       session_language, session_voice_id, pinned_at,
                       degraded_flags, started_at, ended_at
                FROM sessions
                WHERE id = %s::uuid AND tenant_id = %s::uuid
                """,
                (session_id, tenant_id),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return Session(
            id=row[0],
            tenant_id=row[1],
            agent_id=row[2],
            transport_type=row[3],
            compliance_tier=row[4],
            config_version_id=row[5],
            agent_config_version=row[6],
            runtime_plan_hash=row[7],
            runtime_plan_snapshot=dict(row[8] or {}),
            session_language=row[9],
            session_voice_id=row[10],
            pinned_at=row[11],
            degraded_flags=dict(row[12] or {}),
            started_at=row[13],
            ended_at=row[14],
        )


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
