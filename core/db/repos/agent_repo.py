"""UCVE Agent Repository Layer with Provider Config Validation."""

from __future__ import annotations

from typing import Any

from core.db.models import Agent
from core.providers.config_schema import AgentProviderConfig


class AgentRepository:
    """Repository managing agents and validating provider chain configurations."""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    async def save_agent(
        self, tenant_id: str, agent: Agent, tenant_allow_testing: bool = False
    ) -> Agent:
        """Save/update agent entity, enforcing tenant boundary and validating provider chains."""
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")

        if agent.tenant_id != tenant_id:
            raise PermissionError("Agent tenant_id mismatch with query context.")

        # Validate agent_provider_config JSONB via AgentProviderConfig
        if agent.agent_provider_config:
            provider_cfg = AgentProviderConfig.model_validate(agent.agent_provider_config)
            provider_cfg.validate_chains(tenant_allow_testing=tenant_allow_testing)

        self._agents[agent.id] = agent
        return agent

    async def get_agent(self, tenant_id: str, agent_id: str) -> Agent | None:
        """Retrieve agent by ID scoped to tenant."""
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")

        agent = self._agents.get(agent_id)
        if not agent:
            return None

        if agent.tenant_id != tenant_id:
            raise PermissionError(f"Cross-tenant access blocked for tenant '{tenant_id}'.")

        return agent

    async def list_agents(self, tenant_id: str) -> list[Agent]:
        """List all agents owned by tenant."""
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")

        return [a for a in self._agents.values() if a.tenant_id == tenant_id]
