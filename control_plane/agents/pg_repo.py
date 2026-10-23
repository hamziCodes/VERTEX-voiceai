"""Durable async repository for agent drafts and immutable versions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from control_plane.agents.models.agent_config import AgentConfig
from control_plane.agents.repo import AgentNotFoundError
from control_plane.agents.validation.validator import (
    AgentConfigValidator,
    ValidationResult,
)
from core.db.async_pg import AsyncDatabase, get_default_database


class PostgresAgentConfigRepo:
    """Persist tenant agent drafts and published snapshots under RLS."""

    def __init__(
        self,
        database: AsyncDatabase | Any | None = None,
        validator: AgentConfigValidator | None = None,
    ) -> None:
        self.database = database or get_default_database()
        self.validator = validator or AgentConfigValidator()

    async def create_agent(self, config: AgentConfig) -> AgentConfig:
        snapshot = config.model_dump(mode="json")
        async with self.database.tenant_transaction(str(config.tenant_id)) as conn:
            await conn.execute(
                """
                INSERT INTO agent_configs (
                    agent_id, tenant_id, name, description, current_version,
                    draft_data, last_autosaved_at
                ) VALUES (%s::uuid, %s::uuid, %s, %s, 0, %s::jsonb, NOW())
                """,
                (
                    str(config.agent_id),
                    str(config.tenant_id),
                    config.name,
                    config.description,
                    json.dumps(snapshot),
                ),
            )
        return config

    async def get_draft(self, tenant_id: UUID, agent_id: UUID) -> AgentConfig:
        async with self.database.tenant_transaction(str(tenant_id)) as conn:
            cursor = await conn.execute(
                "SELECT draft_data FROM agent_configs "
                "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid",
                (str(tenant_id), str(agent_id)),
            )
            row = await cursor.fetchone()
        if row is None:
            raise AgentNotFoundError(
                f"Agent {agent_id} not found for tenant {tenant_id}."
            )
        return AgentConfig.model_validate(row[0])

    async def list_agents(self, tenant_id: UUID) -> list[AgentConfig]:
        async with self.database.tenant_transaction(str(tenant_id)) as conn:
            cursor = await conn.execute(
                "SELECT draft_data FROM agent_configs "
                "WHERE tenant_id = %s::uuid ORDER BY created_at, agent_id",
                (str(tenant_id),),
            )
            rows = await cursor.fetchall()
        return [AgentConfig.model_validate(row[0]) for row in rows]

    async def save_draft_autosave(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        patch_data: dict[str, Any],
        *,
        debounce_seconds: float = 30.0,
        force: bool = False,
    ) -> tuple[AgentConfig, bool]:
        async with self.database.tenant_transaction(str(tenant_id)) as conn:
            cursor = await conn.execute(
                "SELECT draft_data, last_autosaved_at FROM agent_configs "
                "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid FOR UPDATE",
                (str(tenant_id), str(agent_id)),
            )
            row = await cursor.fetchone()
            if row is None:
                raise AgentNotFoundError(
                    f"Agent {agent_id} not found for tenant {tenant_id}."
                )
            current = AgentConfig.model_validate(row[0])
            now = datetime.now(UTC)
            if (
                not force
                and row[1] is not None
                and (now - row[1]).total_seconds() < debounce_seconds
            ):
                return current, False
            updated_data = current.model_dump(mode="json")
            updated_data.update(patch_data)
            updated_data["tenant_id"] = str(tenant_id)
            updated_data["agent_id"] = str(agent_id)
            updated = AgentConfig.model_validate(updated_data)
            await conn.execute(
                "UPDATE agent_configs SET name = %s, description = %s, "
                "draft_data = %s::jsonb, last_autosaved_at = %s, "
                "updated_at = %s WHERE tenant_id = %s::uuid AND agent_id = %s::uuid",
                (
                    updated.name,
                    updated.description,
                    json.dumps(updated.model_dump(mode="json")),
                    now,
                    now,
                    str(tenant_id),
                    str(agent_id),
                ),
            )
        return updated, True

    async def publish(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        published_by: str = "system",
    ) -> tuple[AgentConfig, ValidationResult]:
        async with self.database.tenant_transaction(str(tenant_id)) as conn:
            cursor = await conn.execute(
                "SELECT draft_data, current_version FROM agent_configs "
                "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid FOR UPDATE",
                (str(tenant_id), str(agent_id)),
            )
            row = await cursor.fetchone()
            if row is None:
                raise AgentNotFoundError(
                    f"Agent {agent_id} not found for tenant {tenant_id}."
                )
            draft = AgentConfig.model_validate(row[0])
            validation = self.validator.validate(draft)
            validation.raise_if_invalid()
            next_version = int(row[1] or 0) + 1
            now = datetime.now(UTC)
            published = draft.model_copy(
                update={
                    "version": next_version,
                    "is_published": True,
                    "published_at": now,
                }
            )
            snapshot = published.model_dump(mode="json")
            await conn.execute(
                "INSERT INTO agent_config_versions ("
                "agent_id, tenant_id, version, config_snapshot, "
                "published_by, published_at"
                ") VALUES (%s::uuid, %s::uuid, %s, %s::jsonb, %s, %s)",
                (
                    str(agent_id),
                    str(tenant_id),
                    next_version,
                    json.dumps(snapshot),
                    published_by,
                    now,
                ),
            )
            await conn.execute(
                "UPDATE agent_configs SET current_version = %s, "
                "draft_data = %s::jsonb, updated_at = %s "
                "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid",
                (
                    next_version,
                    json.dumps(snapshot),
                    now,
                    str(tenant_id),
                    str(agent_id),
                ),
            )
        return published, validation

    async def get_published_version(
        self, tenant_id: UUID, agent_id: UUID, version: int | None = None
    ) -> AgentConfig:
        async with self.database.tenant_transaction(str(tenant_id)) as conn:
            if version is None:
                cursor = await conn.execute(
                    "SELECT config_snapshot FROM agent_config_versions "
                    "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid "
                    "ORDER BY version DESC LIMIT 1",
                    (str(tenant_id), str(agent_id)),
                )
            else:
                cursor = await conn.execute(
                    "SELECT config_snapshot FROM agent_config_versions "
                    "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid "
                    "AND version = %s",
                    (str(tenant_id), str(agent_id), version),
                )
            row = await cursor.fetchone()
        if row is None:
            raise AgentNotFoundError(
                f"Published agent {agent_id} was not found for tenant {tenant_id}."
            )
        return AgentConfig.model_validate(row[0])

    async def list_versions(
        self, tenant_id: UUID, agent_id: UUID
    ) -> list[dict[str, Any]]:
        async with self.database.tenant_transaction(str(tenant_id)) as conn:
            cursor = await conn.execute(
                "SELECT version, published_by, published_at "
                "FROM agent_config_versions "
                "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid "
                "ORDER BY version",
                (str(tenant_id), str(agent_id)),
            )
            rows = await cursor.fetchall()
        if not rows:
            raise AgentNotFoundError(
                f"Agent {agent_id} not found for tenant {tenant_id}."
            )
        return [
            {
                "version": row[0],
                "published_by": row[1],
                "published_at": row[2].isoformat() if row[2] else None,
            }
            for row in rows
        ]

    async def pin_session(
        self,
        session_id: UUID,
        tenant_id: UUID,
        agent_id: UUID,
        version: int | None = None,
    ) -> AgentConfig:
        config = await self.get_published_version(tenant_id, agent_id, version)
        snapshot = config.model_dump(mode="json")
        async with self.database.tenant_transaction(str(tenant_id)) as conn:
            cursor = await conn.execute(
                "SELECT version_id FROM agent_config_versions "
                "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid "
                "AND version = %s",
                (str(tenant_id), str(agent_id), config.version),
            )
            row = await cursor.fetchone()
            if row is None:
                raise AgentNotFoundError(
                    f"Version {config.version} of agent {agent_id} not found."
                )
            await conn.execute(
                "INSERT INTO session_config_pins ("
                "session_id, agent_id, tenant_id, version_id, version, "
                "pinned_config_snapshot) VALUES ("
                "%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s::jsonb) "
                "ON CONFLICT (session_id) DO NOTHING",
                (
                    str(session_id),
                    str(agent_id),
                    str(tenant_id),
                    str(row[0]),
                    config.version,
                    json.dumps(snapshot),
                ),
            )
        return config
