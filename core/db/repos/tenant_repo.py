"""UCVE Tenant Repository Layer."""

from __future__ import annotations

from typing import Any

from core.db.models import Agent, Tenant, TenantComplianceProfile


class TenantRepository:
    """Repository managing tenants and enforcing isolation boundaries."""

    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}
        self._compliance_profiles: dict[str, TenantComplianceProfile] = {}
        self._agents: dict[str, Agent] = {}

    async def create_tenant(self, tenant: Tenant) -> Tenant:
        """Persist new tenant entity."""
        self._tenants[tenant.id] = tenant
        return tenant

    async def get_tenant(self, tenant_id: str) -> Tenant | None:
        """Retrieve tenant by ID."""
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")
        return self._tenants.get(tenant_id)

    async def save_agent(self, agent: Agent) -> Agent:
        """Internal agent store for repo unit tests."""
        self._agents[agent.id] = agent
        return agent

    async def get_agent_for_tenant(self, tenant_id: str, agent_id: str) -> Agent | None:
        """Retrieve agent for tenant, enforcing cross-tenant isolation boundaries."""
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")

        agent = self._agents.get(agent_id)
        if not agent:
            return None

        if agent.tenant_id != tenant_id:
            raise PermissionError(
                f"Cross-tenant access blocked: tenant '{tenant_id}' requested agent '{agent_id}' owned by tenant '{agent.tenant_id}'."
            )

        return agent

    async def delete_tenant(self, tenant_id: str) -> bool:
        """Cascade delete tenant and all owned entities."""
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")

        if tenant_id in self._tenants:
            del self._tenants[tenant_id]
            # Cascade delete agents
            agents_to_del = [aid for aid, a in self._agents.items() if a.tenant_id == tenant_id]
            for aid in agents_to_del:
                del self._agents[aid]
            return True
        return False
