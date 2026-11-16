"""Stage 3 customer-journey regressions on a disposable PostgreSQL."""

from __future__ import annotations

import asyncio
import os
import sys
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DB_TESTS") != "1",
    reason="RUN_LIVE_DB_TESTS!=1 - disposable PostgreSQL only",
)


@pytest.fixture(scope="module")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    """Psycopg async requires a selector loop on Windows."""
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.mark.asyncio
async def test_unpublished_agent_has_no_versions_not_a_404() -> None:
    """Studio could not open a newly created agent: the Postgres repository
    answered 'agent not found' for an agent that simply had no versions."""
    from control_plane.agents.models.agent_config import AgentConfig
    from control_plane.agents.pg_repo import PostgresAgentConfigRepo
    from control_plane.agents.repo import AgentNotFoundError
    from control_plane.studio.models import IdentityContext
    from control_plane.studio.pg_repository import PostgresStudioRepository
    from core.db.async_pg import AsyncDatabase
    from infra.db.migrate import apply_migrations_async

    database_url = os.environ["DATABASE_URL"]
    await apply_migrations_async(database_url)
    database = AsyncDatabase(database_url=database_url, min_size=1, max_size=2)
    await database.open()
    try:
        studio = PostgresStudioRepository(database)
        owner = await studio.resolve_identity(
            IdentityContext(issuer="https://stage3.test", subject=f"owner-{uuid4()}", email="o@stage3.test")
        )
        workspace = await studio.create_workspace(owner.user_id, "Stage 3 journey")
        agent_id = uuid4()
        async with database.platform_transaction() as connection:
            await connection.execute(
                "INSERT INTO agents (id, tenant_id, name) VALUES (%s, %s, %s)",
                (agent_id, workspace.tenant_id, "Front desk"),
            )
        agents = PostgresAgentConfigRepo(database)
        await agents.create_agent(
            AgentConfig(tenant_id=workspace.tenant_id, agent_id=agent_id, name="Front desk")
        )

        assert await agents.list_versions(workspace.tenant_id, agent_id) == []
        with pytest.raises(AgentNotFoundError):
            await agents.list_versions(workspace.tenant_id, uuid4())
    finally:
        await database.close()
