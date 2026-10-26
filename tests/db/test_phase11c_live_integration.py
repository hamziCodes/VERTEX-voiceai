from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DB_TESTS") != "1",
    reason="RUN_LIVE_DB_TESTS!=1 - disposable PostgreSQL only",
)


@pytest.fixture(scope="module")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.mark.asyncio
async def test_disposable_webhook_restart_attempt_idempotency_and_rls() -> None:
    import psycopg

    from control_plane.auth.context import AuthContext
    from core.db.async_pg import AsyncDatabase
    from infra.db.migrate import apply_migrations_async
    from post_call.webhook.dispatcher import WebhookDispatcher
    from post_call.webhook.models import WebhookDeliveryState
    from post_call.webhook.policy import WebhookEndpointPolicy
    from post_call.webhook.repository import PostgresWebhookRepository
    from post_call.webhook.service import WebhookDeliveryWorker, WebhookTargetManager

    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must name a disposable database"
    await apply_migrations_async(database_url)
    tenant_a, tenant_b, agent_id = uuid4(), uuid4(), uuid4()
    call_id, session_id, result_id, review_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    now = datetime.now(UTC)
    connection = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with connection.transaction():
            await connection.execute(
                "INSERT INTO tenants (id, name) VALUES (%s, %s), (%s, %s)",
                (tenant_a, "phase11c-a", tenant_b, "phase11c-b"),
            )
            await connection.execute(
                "INSERT INTO agents (id, tenant_id, name) VALUES (%s, %s, %s)",
                (agent_id, tenant_a, "phase11c-agent"),
            )
            await connection.execute(
                "INSERT INTO call_records "
                "(call_id, tenant_id, agent_id, session_id, started_at, ended_at, "
                "transport_type, compliance_tier, recording_state, policy_snapshot, "
                "provider_snapshot, intelligence_config_snapshot) VALUES "
                "(%s, %s, %s, %s, %s, %s, 'websocket', 'standard', "
                "'not_requested', '{}'::jsonb, '{}'::jsonb, '{}'::jsonb)",
                (
                    call_id,
                    tenant_a,
                    agent_id,
                    session_id,
                    now,
                    now,
                ),
            )
            await connection.execute(
                "INSERT INTO post_call_intelligence_results "
                "(result_id, tenant_id, call_id, extraction_jsonb) "
                "VALUES (%s, %s, %s, %s::jsonb)",
                (result_id, tenant_a, call_id, '{"fields": {}}'),
            )
            await connection.execute(
                "INSERT INTO post_call_review_requests "
                "(review_id, tenant_id, call_id, result_id, reasons_jsonb, state, "
                "decided_by, decided_at) VALUES "
                "(%s, %s, %s, %s, '[\"external_action_policy\"]'::jsonb, "
                "'approved', 'operator-1', %s)",
                (review_id, tenant_a, call_id, result_id, now),
            )
    finally:
        await connection.close()

    auth = AuthContext(
        subject_id="operator-1",
        tenant_id=str(tenant_a),
        roles=("tenant_admin",),
        scopes=frozenset({"webhook:write"}),
        auth_method="oidc",
    )
    first_database = AsyncDatabase(database_url=database_url, min_size=1, max_size=1)
    await first_database.open()
    try:
        repo = PostgresWebhookRepository(first_database)
        target = await WebhookTargetManager(
            repository=repo,
            endpoint_policy=WebhookEndpointPolicy(
                resolver=lambda _host: ("93.184.216.34",)
            ),
        ).create_and_approve(
            tenant_id=tenant_a,
            name="Phase 11C CRM",
            url="https://crm.example.test/events",
            credential_ref="phase11c-signing",
            auth=auth,
        )
        delivery = await repo.enqueue_delivery(
            tenant_id=tenant_a,
            target_id=target.target_id,
            call_id=call_id,
            result_id=result_id,
            review_id=review_id,
            event_type="post_call.intelligence.completed",
        )
    finally:
        await first_database.close()

    restarted = AsyncDatabase(database_url=database_url, min_size=1, max_size=1)
    await restarted.open()
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(202, request=request)
        )
    )
    try:
        repo = PostgresWebhookRepository(restarted)

        async def resolve_secret(_tenant_id: str, credential_ref: str) -> str:
            assert credential_ref == "phase11c-signing"
            return "test-signing-secret"

        worker = WebhookDeliveryWorker(
            repository=repo,
            dispatcher=WebhookDispatcher(
                secret_resolver=resolve_secret,
                client=client,
                endpoint_policy=WebhookEndpointPolicy(
                    resolver=lambda _host: ("93.184.216.34",)
                ),
            ),
            worker_id="phase11c-worker",
        )
        assert await worker.run_once() is True
        stored = await repo.get_delivery(tenant_a, delivery.delivery_id)
        attempts = await repo.list_attempts(tenant_a, delivery.delivery_id)
        assert stored.state is WebhookDeliveryState.SUCCEEDED
        assert len(attempts) == 1
        assert attempts[0].status_code == 202
        assert attempts[0].response_body is None
        duplicate = await repo.enqueue_delivery(
            tenant_id=tenant_a,
            target_id=target.target_id,
            call_id=call_id,
            result_id=result_id,
            review_id=review_id,
            event_type="post_call.intelligence.completed",
        )
        assert duplicate.delivery_id == delivery.delivery_id
        assert await worker.run_once() is False
    finally:
        await client.aclose()
        await restarted.close()

    rls = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with rls.transaction():
            await rls.execute("SET LOCAL ROLE ucve_app")
            await rls.execute(
                "SELECT set_config('app.tenant_id', %s, true)", (str(tenant_b),)
            )
            for table in (
                "post_call_webhook_targets",
                "webhook_deliveries",
                "webhook_delivery_attempts",
            ):
                rows = await (await rls.execute(f"SELECT * FROM {table}")).fetchall()
                assert rows == []
    finally:
        await rls.close()

    assert await apply_migrations_async(database_url) == []
