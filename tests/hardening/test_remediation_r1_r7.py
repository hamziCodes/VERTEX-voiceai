"""Remediation gates R1–R7."""

from __future__ import annotations

import asyncio
import time
import uuid

import pytest

from core.errors.alert_router import AlertRouter
from core.errors.codes import UCVEErrorCode
from core.errors.parse_uuid import parse_uuid
from core.errors.structured import StructuredError
from core.providers.failover import FailoverRouter
from core.types.resampler import Resampler
from post_call.webhook.dispatcher import WebhookDispatcher
from post_call.webhook.targets import TenantWebhookTarget
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
async def test_webhook_exponential_backoff(test_env: None) -> None:
    sleeps: list[float] = []

    async def _fake_sleep(sec: float) -> None:
        sleeps.append(sec)

    async def _fail_client(*_a: object, **_k: object) -> bool:
        return False

    disp = WebhookDispatcher(http_client=_fail_client, sleep_fn=_fake_sleep)
    target = TenantWebhookTarget(
        tenant_id=uuid.uuid4(), url="https://example.com/hook", secret="sec"
    )
    ok = await disp.dispatch(target, {"a": 1}, "key-1", max_retries=3)
    assert ok is False
    assert sleeps == [1.0, 2.0]


def test_telnyx_signature_fail_closed() -> None:
    assert verify_telnyx_signature(b"{}", None, "123", hmac_secret="sec") is False


def test_did_binding_no_silent_default() -> None:
    resolver = SIPParticipantResolver()
    with pytest.raises(ValueError):
        resolver.resolve("+15551234567")


@pytest.mark.asyncio
async def test_alert_router_webhook_dispatch(test_env: None) -> None:
    router = AlertRouter()
    err = StructuredError(code=UCVEErrorCode.LATENCY_SLO_BREACH, message="slow", severity="error")
    ok = await router.route_alert(uuid.uuid4(), err)
    assert ok
    assert router.routed_alerts[-1].get("log_dispatched") is True


def test_unauth_quick_mint_blocked(test_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.delenv("UCVE_DEMO_MODE", raising=False)
    from control_plane.app import app

    with TestClient(app) as client:
        resp = client.post("/mint", json={})
        assert resp.status_code == 401
