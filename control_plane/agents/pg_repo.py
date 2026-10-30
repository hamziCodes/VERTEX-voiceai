"""Durable async repository for agent drafts and immutable versions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from control_plane.agents.models.agent_config import AgentConfig
from control_plane.agents.repo import AgentNotFoundError, AgentRevisionConflictError
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
                    draft_data, draft_revision, last_autosaved_at
                ) VALUES (%s::uuid, %s::uuid, %s, %s, 0, %s::jsonb, %s, NOW())
                """,
                (
                    str(config.agent_id),
                    str(config.tenant_id),
                    config.name,
                    config.description,
                    json.dumps(snapshot),
                    config.draft_revision,
                ),
            )
        return config

    async def get_draft(self, tenant_id: UUID, agent_id: UUID) -> AgentConfig:
        async with self.database.tenant_transaction(str(tenant_id)) as conn:
            cursor = await conn.execute(
                "SELECT draft_data, draft_revision FROM agent_configs "
                "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid",
                (str(tenant_id), str(agent_id)),
            )
            row = await cursor.fetchone()
        if row is None:
            raise AgentNotFoundError(
                f"Agent {agent_id} not found for tenant {tenant_id}."
            )
        return AgentConfig.model_validate({**row[0], "draft_revision": int(row[1])})

    async def list_agents(self, tenant_id: UUID) -> list[AgentConfig]:
        async with self.database.tenant_transaction(str(tenant_id)) as conn:
            cursor = await conn.execute(
                "SELECT draft_data, draft_revision FROM agent_configs "
                "WHERE tenant_id = %s::uuid ORDER BY created_at, agent_id",
                (str(tenant_id),),
            )
            rows = await cursor.fetchall()
        return [
            AgentConfig.model_validate({**row[0], "draft_revision": int(row[1])})
            for row in rows
        ]

    async def save_draft_autosave(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        patch_data: dict[str, Any],
        *,
        debounce_seconds: float = 30.0,
        force: bool = False,
        expected_revision: int | None = None,
    ) -> tuple[AgentConfig, bool]:
        async with self.database.tenant_transaction(str(tenant_id)) as conn:
            cursor = await conn.execute(
                "SELECT draft_data, last_autosaved_at, draft_revision "
                "FROM agent_configs "
                "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid FOR UPDATE",
                (str(tenant_id), str(agent_id)),
            )
            row = await cursor.fetchone()
            if row is None:
                raise AgentNotFoundError(
                    f"Agent {agent_id} not found for tenant {tenant_id}."
                )
            current = AgentConfig.model_validate(
                {**row[0], "draft_revision": int(row[2])}
            )
            if expected_revision is not None and row[2] != expected_revision:
                raise AgentRevisionConflictError(
                    f"Draft revision is {row[2]}, not {expected_revision}."
                )
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
            updated_data["draft_revision"] = current.draft_revision + 1
            updated = AgentConfig.model_validate(updated_data)
            if updated.model_dump(exclude={"draft_revision"}) == current.model_dump(
                exclude={"draft_revision"}
            ):
                return current, False
            await conn.execute(
                "UPDATE agent_configs SET name = %s, description = %s, "
                "draft_data = %s::jsonb, last_autosaved_at = %s, "
                "draft_revision = %s, updated_at = %s "
                "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid",
                (
                    updated.name,
                    updated.description,
                    json.dumps(updated.model_dump(mode="json")),
                    now,
                    updated.draft_revision,
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
        expected_revision: int | None = None,
    ) -> tuple[AgentConfig, ValidationResult]:
        async with self.database.tenant_transaction(str(tenant_id)) as conn:
            cursor = await conn.execute(
                "SELECT draft_data, current_version, draft_revision "
                "FROM agent_configs "
                "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid FOR UPDATE",
                (str(tenant_id), str(agent_id)),
            )
            row = await cursor.fetchone()
            if row is None:
                raise AgentNotFoundError(
                    f"Agent {agent_id} not found for tenant {tenant_id}."
                )
            draft = AgentConfig.model_validate(
                {**row[0], "draft_revision": int(row[2])}
            )
            if expected_revision is not None and row[2] != expected_revision:
                raise AgentRevisionConflictError(
                    f"Draft revision is {row[2]}, not {expected_revision}."
                )
            validation = self.validator.validate(draft)
            validation.raise_if_invalid()
            next_version = int(row[1] or 0) + 1
            now = datetime.now(UTC)
            published = draft.model_copy(
                update={
                    "version": next_version,
                    "is_published": True,
                    "published_at": now,
                    "draft_revision": draft.draft_revision + 1,
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
                "draft_data = %s::jsonb, draft_revision = %s, updated_at = %s "
                "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid",
                (
                    next_version,
                    json.dumps(snapshot),
                    published.draft_revision,
                    now,
                    str(tenant_id),
                    str(agent_id),
                ),
            )
        return published, validation

    async def restore_version(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        version: int,
        *,
        expected_revision: int,
    ) -> AgentConfig:
        async with self.database.tenant_transaction(str(tenant_id)) as conn:
            current_cursor = await conn.execute(
                "SELECT draft_data, current_version, draft_revision "
                "FROM agent_configs WHERE tenant_id = %s::uuid "
                "AND agent_id = %s::uuid FOR UPDATE",
                (str(tenant_id), str(agent_id)),
            )
            current_row = await current_cursor.fetchone()
            if current_row is None:
                raise AgentNotFoundError(
                    f"Agent {agent_id} not found for tenant {tenant_id}."
                )
            if int(current_row[2]) != expected_revision:
                raise AgentRevisionConflictError(
                    f"Draft revision is {current_row[2]}, not {expected_revision}."
                )
            snapshot_cursor = await conn.execute(
                "SELECT config_snapshot FROM agent_config_versions "
                "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid "
                "AND version = %s",
                (str(tenant_id), str(agent_id), version),
            )
            snapshot_row = await snapshot_cursor.fetchone()
            if snapshot_row is None:
                raise AgentNotFoundError(
                    f"Version {version} of agent {agent_id} not found."
                )
            current = AgentConfig.model_validate(
                {**current_row[0], "draft_revision": int(current_row[2])}
            )
            snapshot = AgentConfig.model_validate(snapshot_row[0])
            restored = snapshot.model_copy(
                update={
                    "tenant_id": tenant_id,
                    "agent_id": agent_id,
                    "version": current.version,
                    "published_at": None,
                    "is_published": False,
                    "draft_revision": current.draft_revision + 1,
                },
                deep=True,
            )
            now = datetime.now(UTC)
            await conn.execute(
                "UPDATE agent_configs SET name = %s, description = %s, "
                "draft_data = %s::jsonb, draft_revision = %s, "
                "last_autosaved_at = %s, updated_at = %s "
                "WHERE tenant_id = %s::uuid AND agent_id = %s::uuid",
                (
                    restored.name,
                    restored.description,
                    json.dumps(restored.model_dump(mode="json")),
                    restored.draft_revision,
                    now,
                    now,
                    str(tenant_id),
                    str(agent_id),
                ),
            )
        return restored

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
