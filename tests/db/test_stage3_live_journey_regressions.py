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


@pytest.mark.asyncio
async def test_unflagged_result_delivers_and_flagged_waits_on_postgres() -> None:
    """Migration 037 and the rewritten delivery gate on a real database."""
    from datetime import UTC, datetime

    import psycopg

    from control_plane.auth.context import AuthContext
    from core.db.async_pg import AsyncDatabase
    from infra.db.migrate import apply_migrations_async
    from post_call.webhook.fanout import enqueue_for_result
    from post_call.webhook.policy import WebhookEndpointPolicy
    from post_call.webhook.repository import (
        PostgresWebhookRepository,
        WebhookReviewRequiredError,
    )
    from post_call.webhook.service import WebhookTargetManager

    database_url = os.environ["DATABASE_URL"]
    await apply_migrations_async(database_url)
    tenant, agent = uuid4(), uuid4()
    plain_call, flagged_call = uuid4(), uuid4()
    plain_result, flagged_result = uuid4(), uuid4()
    now = datetime.now(UTC)
    connection = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with connection.transaction():
            await connection.execute("INSERT INTO tenants (id, name) VALUES (%s, 'stage3-hooks')", (tenant,))
            await connection.execute("INSERT INTO agents (id, tenant_id, name) VALUES (%s, %s, 'a')", (agent, tenant))
            for call, result in ((plain_call, plain_result), (flagged_call, flagged_result)):
                await connection.execute(
                    "INSERT INTO call_records (call_id, tenant_id, agent_id, session_id, started_at, "
                    "ended_at, transport_type, compliance_tier, recording_state, policy_snapshot, "
                    "provider_snapshot, intelligence_config_snapshot) VALUES (%s, %s, %s, %s, %s, %s, "
                    "'websocket', 'standard', 'not_requested', '{}'::jsonb, '{}'::jsonb, '{}'::jsonb)",
                    (call, tenant, agent, uuid4(), now, now),
                )
                await connection.execute(
                    "INSERT INTO post_call_intelligence_results (result_id, tenant_id, call_id, summary_jsonb) "
                    "VALUES (%s, %s, %s, '{\"executive_summary\": \"x\"}'::jsonb)",
                    (result, tenant, call),
                )
            await connection.execute(
                "INSERT INTO post_call_review_requests (review_id, tenant_id, call_id, result_id, "
                "reasons_jsonb, state) VALUES (%s, %s, %s, %s, '[\"sensitive_field\"]'::jsonb, 'pending')",
                (uuid4(), tenant, flagged_call, flagged_result),
            )
    finally:
        await connection.close()

    auth = AuthContext(
        subject_id="operator-1", tenant_id=str(tenant), roles=("tenant_admin",),
        scopes=frozenset({"webhook:write"}), auth_method="oidc",
    )
    database = AsyncDatabase(database_url=database_url, min_size=1, max_size=2)
    await database.open()
    try:
        repo = PostgresWebhookRepository(database)
        manager = WebhookTargetManager(
            repository=repo, endpoint_policy=WebhookEndpointPolicy(resolver=lambda _h: ("93.184.216.34",))
        )
        first = await manager.create_and_approve(
            tenant_id=tenant, name="CRM", url="https://crm.example.test/h", credential_ref="crm-ref", auth=auth
        )
        second = await manager.create_and_approve(
            tenant_id=tenant, name="Old", url="https://old.example.test/h", credential_ref="old-ref", auth=auth
        )
        await repo.disable_target(tenant_id=tenant, target_id=second.target_id, auth=auth)
        assert [t.state.value for t in await repo.list_targets(tenant)] == ["active", "disabled"]

        assert await enqueue_for_result(repo, tenant_id=tenant, call_id=plain_call, result_id=plain_result) == 1
        assert await enqueue_for_result(repo, tenant_id=tenant, call_id=flagged_call, result_id=flagged_result) == 0
        with pytest.raises(WebhookReviewRequiredError):
            await repo.enqueue_delivery(
                tenant_id=tenant, target_id=first.target_id, call_id=flagged_call,
                result_id=flagged_result, event_type="post_call.intelligence.completed",
            )
        async with database.platform_transaction() as conn:
            rows = await (await conn.execute(
                "SELECT call_id, review_id FROM webhook_deliveries WHERE tenant_id = %s", (tenant,)
            )).fetchall()
        assert rows == [(plain_call, None)]
    finally:
        await database.close()
