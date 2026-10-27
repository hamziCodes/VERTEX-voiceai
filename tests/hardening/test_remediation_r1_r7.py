"""Remediation gates R1–R7."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import httpx
import pytest

from core.db.repos.telephony_repo import (
    InMemoryTelephonyRepository,
    TelephonyAdmissionError,
)
from core.errors.alert_router import AlertRouter
from core.errors.codes import UCVEErrorCode
from core.errors.parse_uuid import parse_uuid
from core.errors.structured import StructuredError
from core.providers.failover import FailoverRouter
from core.types.resampler import Resampler
from post_call.webhook.dispatcher import WebhookDispatcher
from post_call.webhook.models import (
    TenantWebhookTarget,
    WebhookDelivery,
    WebhookTargetState,
)
from post_call.webhook.policy import WebhookEndpointPolicy
from telephony_gateway.resolver.sip_participant_resolver import SIPParticipantResolver
from telephony_gateway.telnyx.signature import verify_telnyx_signature
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig


@pytest.fixture
def test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("RUN_LIVE_PROVIDERS", raising=False)


def test_parse_uuid_rejects_malformed_tenant() -> None:
    bad = "0" * 35
    with pytest.raises(Exception):
        parse_uuid(bad, "tenant_id")


@pytest.mark.asyncio
async def test_malformed_tenant_id_no_rag_write(test_env: None) -> None:
    orch = PipelineOrchestrator()
    config = PipelineSessionConfig(
        session_id=str(uuid.uuid4()),
        tenant_id="x" * 35,
        agent_id=str(uuid.uuid4()),
    )
    with pytest.raises(Exception):
        await orch.run_turn(config, "hello")


def test_failover_opens_after_failures() -> None:
    router = FailoverRouter(priority=["primary", "secondary"])
    calls: list[str] = []

    async def _fail(_pid: str) -> bool:
        calls.append(_pid)
        raise RuntimeError("fail")

    async def _run() -> None:
        with pytest.raises(Exception):
            await router.call_with_failover("llm", "en", _fail)
        assert calls[0] == "primary"
        assert "secondary" in calls

    asyncio.run(_run())


def test_resampler_vectorized_boundary() -> None:
    r = Resampler(48000, 16000)
    pcm = (1000).to_bytes(2, "little", signed=True) * 480
    out1 = r.process(pcm)
    out2 = r.process(pcm)
    assert len(out1) > 0
    assert len(out1) == len(out2)


@pytest.mark.asyncio
async def test_webhook_failure_returns_durable_retry_decision(test_env: None) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, request=request)

    async def resolve_secret(_tenant_id: str, _credential_ref: str) -> str:
        return "test-secret"

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tenant_id, call_id = uuid.uuid4(), uuid.uuid4()
    target = TenantWebhookTarget(
        tenant_id=tenant_id,
        name="CRM",
        url="https://example.com/hook",
        credential_ref="crm-signing",
        state=WebhookTargetState.ACTIVE,
        reviewed_by="operator-1",
        reviewed_at=datetime.now(UTC),
        approved_addresses=("93.184.216.34",),
    )
    delivery = WebhookDelivery(
        tenant_id=tenant_id,
        target_id=target.target_id,
        call_id=call_id,
        result_id=uuid.uuid4(),
        review_id=uuid.uuid4(),
        event_type="post_call.intelligence.completed",
        idempotency_key="a" * 64,
        payload={"call_id": str(call_id)},
    )
    dispatcher = WebhookDispatcher(
        secret_resolver=resolve_secret,
        client=client,
        endpoint_policy=WebhookEndpointPolicy(
            resolver=lambda _host: ("93.184.216.34",)
        ),
    )

    result = await dispatcher.send_once(target, delivery)

    assert result.retryable is True
    assert result.error_code == "remote_unavailable"
    assert calls == 1
    await client.aclose()


def test_telnyx_signature_fail_closed() -> None:
    assert verify_telnyx_signature(b"{}", None, "123", hmac_secret="sec") is False


@pytest.mark.asyncio
async def test_did_binding_no_silent_default() -> None:
    resolver = SIPParticipantResolver(InMemoryTelephonyRepository())
    with pytest.raises(TelephonyAdmissionError, match="did_not_found"):
        await resolver.resolve("+15551234567")


@pytest.mark.asyncio
async def test_alert_router_webhook_dispatch(test_env: None) -> None:
    router = AlertRouter()
    err = StructuredError(
        code=UCVEErrorCode.LATENCY_SLO_BREACH, message="slow", severity="error"
    )
    ok = await router.route_alert(uuid.uuid4(), err)
    assert ok
    assert router.routed_alerts[-1].get("log_dispatched") is True


def test_unauth_quick_mint_blocked(
    test_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.delenv("UCVE_DEMO_MODE", raising=False)
    from control_plane.app import app

    with TestClient(app) as client:
        resp = client.post("/mint", json={})
        assert resp.status_code == 401
