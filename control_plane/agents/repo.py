"""UCVE Agent Builder - Agent Configuration Repository Layer."""

from __future__ import annotations

from datetime import datetime, timezone
import copy
from typing import Any
from uuid import UUID

from control_plane.agents.models.agent_config import AgentConfig
from control_plane.agents.validation.validator import AgentConfigValidator, ValidationResult


class AgentNotFoundError(Exception):
    """Raised when an agent is not found or does not belong to the requesting tenant."""


class DebounceThrottledError(Exception):
    """Raised when an autosave occurs too quickly within the debounce window."""


class AgentConfigRepo:
    """Repository managing agent drafts, debounced autosaves, and immutable published snapshots."""

    def __init__(self, validator: AgentConfigValidator | None = None) -> None:
        self.validator = validator or AgentConfigValidator()
        # In-memory storage structures keyed by (tenant_id, agent_id)
        self._drafts: dict[tuple[UUID, UUID], dict[str, Any]] = {}
        # Versions keyed by (tenant_id, agent_id, version_num)
        self._versions: dict[tuple[UUID, UUID, int], dict[str, Any]] = {}
        # Latest published version tracking keyed by (tenant_id, agent_id)
        self._latest_published_version: dict[tuple[UUID, UUID], int] = {}
        # Timestamp of last autosave keyed by (tenant_id, agent_id)
        self._last_autosave: dict[tuple[UUID, UUID], datetime] = {}

    def create_agent(self, config: AgentConfig) -> AgentConfig:
        """Create a new agent draft under the specified tenant."""
        key = (config.tenant_id, config.agent_id)
        now = datetime.now(timezone.utc)
        record = config.model_dump(mode="json")
        self._drafts[key] = record
        self._last_autosave[key] = now
        return config

    def get_draft(self, tenant_id: UUID, agent_id: UUID) -> AgentConfig:
        """Retrieve the current editable draft for an agent."""
        key = (tenant_id, agent_id)
        record = self._drafts.get(key)
        if not record:
            raise AgentNotFoundError(f"Agent {agent_id} not found for tenant {tenant_id}.")
        return AgentConfig.model_validate(record)

    def list_agents(self, tenant_id: UUID) -> list[AgentConfig]:
        """List all agents belonging to the tenant."""
        results: list[AgentConfig] = []
        for (t_id, _), record in self._drafts.items():
            if t_id == tenant_id:
                results.append(AgentConfig.model_validate(record))
        return results

    def save_draft_autosave(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        patch_data: dict[str, Any],
        *,
        debounce_seconds: float = 30.0,
        force: bool = False,
    ) -> tuple[AgentConfig, bool]:
        """Debounced persist of in-progress edits to the draft.

        Returns (updated_config, did_save). If throttled by debounce, returns (current_config, False).
        """
        key = (tenant_id, agent_id)
        current = self.get_draft(tenant_id, agent_id)
        now = datetime.now(timezone.utc)

        last_time = self._last_autosave.get(key)
        if not force and last_time is not None:
            elapsed = (now - last_time).total_seconds()
            if elapsed < debounce_seconds:
                return current, False

        # Apply patch updates
        dumped = current.model_dump(mode="json")
        dumped.update(patch_data)
        dumped["tenant_id"] = str(tenant_id)
        dumped["agent_id"] = str(agent_id)

        updated = AgentConfig.model_validate(dumped)
        self._drafts[key] = dumped
        self._last_autosave[key] = now
        return updated, True

    def publish(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        published_by: str = "system",
    ) -> tuple[AgentConfig, ValidationResult]:
        """Validate the draft, increment version, and record an immutable snapshot."""
        draft = self.get_draft(tenant_id, agent_id)
        validation_result = self.validator.validate(draft)
        validation_result.raise_if_invalid()

        now = datetime.now(timezone.utc)
        current_v = self._latest_published_version.get((tenant_id, agent_id), 0)
        next_v = current_v + 1

        published_config = draft.model_copy(
            update={
                "version": next_v,
                "is_published": True,
                "published_at": now,
            }
        )

        snapshot = published_config.model_dump(mode="json")
        # Save immutable version row
        self._versions[(tenant_id, agent_id, next_v)] = {
            "version": next_v,
            "snapshot": copy.deepcopy(snapshot),
            "published_by": published_by,
            "published_at": now.isoformat(),
        }
        self._latest_published_version[(tenant_id, agent_id)] = next_v

        # Update draft record version & publish state
        draft_dump = draft.model_dump(mode="json")
        draft_dump["version"] = next_v
        draft_dump["is_published"] = True
        draft_dump["published_at"] = now.isoformat()
        self._drafts[(tenant_id, agent_id)] = draft_dump

        return published_config, validation_result

    def get_published_version(
        self, tenant_id: UUID, agent_id: UUID, version: int | None = None
    ) -> AgentConfig:
        """Retrieve an immutable published config snapshot."""
        if version is None:
            version = self._latest_published_version.get((tenant_id, agent_id))
            if version is None:
                raise AgentNotFoundError(f"Agent {agent_id} has no published versions.")

        entry = self._versions.get((tenant_id, agent_id, version))
        if not entry:
            raise AgentNotFoundError(f"Version {version} of agent {agent_id} not found.")

        return AgentConfig.model_validate(entry["snapshot"])

    def list_versions(self, tenant_id: UUID, agent_id: UUID) -> list[dict[str, Any]]:
        """List all published version metadata for an agent."""
        # Verify agent belongs to tenant
        _ = self.get_draft(tenant_id, agent_id)
        results = []
        for (t_id, a_id, v_num), entry in sorted(self._versions.items(), key=lambda x: x[0][2]):
            if t_id == tenant_id and a_id == agent_id:
                results.append(
                    {
                        "version": v_num,
                        "published_by": entry.get("published_by"),
                        "published_at": entry.get("published_at"),
                    }
                )
        return results


_default_agent_config_repo: AgentConfigRepo | None = None


def get_default_agent_config_repo() -> AgentConfigRepo:
    """Return the process-wide repository shared by publish and session mint."""

    global _default_agent_config_repo
    if _default_agent_config_repo is None:
        repo = AgentConfigRepo()
        tenant_id = UUID("00000000-0000-0000-0000-000000000001")
        agent_id = UUID("00000000-0000-0000-0000-0000000000a1")
        repo.create_agent(
            AgentConfig(
                tenant_id=tenant_id,
                agent_id=agent_id,
                name="Wavia local demo agent",
            )
        )
        repo.publish(tenant_id, agent_id, published_by="system:local-demo-seed")
        _default_agent_config_repo = repo
    return _default_agent_config_repo


def reset_default_agent_config_repo() -> AgentConfigRepo:
    """Reset the shared repository for isolated tests and local process restarts."""

    global _default_agent_config_repo
    _default_agent_config_repo = None
    return get_default_agent_config_repo()
