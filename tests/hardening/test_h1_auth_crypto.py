"""H1: JWT forge rejection, nonce replay, IDOR, prod secret refusal."""

from __future__ import annotations

import base64
import json
import time

import jwt
import pytest

from control_plane.auth.jwt import issue_session_jwt, verify_session_jwt
from control_plane.routes.session import MintContext, handle_session_mint
from core.db.models import Agent, Tenant
from core.runtime.env import BootConfigurationError, require_production_secrets
from core.secrets.kms.local_dev import LocalDevKMSBackend


@pytest.fixture
def test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_ALLOW_UNSAFE_SESSION_OVERRIDES", "1")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("UCVE_WS_PUBLIC_URL", "ws://localhost:8081/ws/audio")


def test_forged_jwt_rejected(test_env: None) -> None:
    token = issue_session_jwt("t1", "s1", "a1")
    parts = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
    payload["tenant_id"] = "attacker"
    forged_payload = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    )
    forged = f"{parts[0]}.{forged_payload}.{parts[2]}"
    with pytest.raises(ValueError):
        verify_session_jwt(forged)


def test_jwt_wrong_secret_rejected(test_env: None) -> None:
    token = issue_session_jwt("t1", "s1", "a1", secret="correct-secret-value-32chars")
    with pytest.raises(ValueError):
        verify_session_jwt(token, secret="wrong-secret-value-32characters")


def test_jwt_requires_room_join_action(test_env: None) -> None:
    now = int(time.time())
    bad = jwt.encode(
        {
            "sub": "s1",
            "tenant_id": "t1",
            "agent_id": "a1",
            "action": "roomAdmin",
            "iat": now,
            "exp": now + 120,
        },
        "ucve-jwt-secret-test-only-32bytes!",
        algorithm="HS256",
    )
    with pytest.raises(ValueError, match="roomJoin"):
        verify_session_jwt(bad, secret="ucve-jwt-secret-test-only-32bytes!")


@pytest.mark.asyncio
async def test_nonce_replay_rejected(test_env: None) -> None:
    from control_plane.auth.hmac_mint import expected_signature

    ctx = MintContext()
    await ctx.tenant_repo.create_tenant(Tenant(id="t-replay", name="Replay"))
    await ctx.tenant_repo.save_agent(
        Agent(id="agent-1", tenant_id="t-replay", name="A")
    )
    secret = "mint-secret"
    ts = str(int(time.time()))
    nonce = "unique-nonce-1"
    sig = expected_signature(secret, "t-replay", ts, nonce, "agent-1")

    status1, body1 = await handle_session_mint(
        "t-replay", ts, nonce, "agent-1", sig, secret=secret, ctx=ctx
    )
    assert status1 == 200
    assert "token" in body1

    status2, body2 = await handle_session_mint(
        "t-replay", ts, nonce, "agent-1", sig, secret=secret, ctx=ctx
    )
    assert status2 == 401
    assert "replay" in body2["error"].lower()


@pytest.mark.asyncio
async def test_cross_tenant_agent_mint_403(test_env: None) -> None:
    from control_plane.auth.hmac_mint import expected_signature

    ctx = MintContext()
    await ctx.tenant_repo.create_tenant(Tenant(id="tenant-a", name="A"))
    await ctx.tenant_repo.create_tenant(Tenant(id="tenant-b", name="B"))
    await ctx.tenant_repo.save_agent(
        Agent(id="agent-b", tenant_id="tenant-b", name="OwnedByB")
    )
    secret = "mint-secret"
    ts = str(int(time.time()))
    nonce = "idor-nonce"
    sig = expected_signature(secret, "tenant-a", ts, nonce, "agent-b")

    status, body = await handle_session_mint(
        "tenant-a", ts, nonce, "agent-b", sig, secret=secret, ctx=ctx
    )
    assert status == 403
    assert "agent" in body["error"].lower()


def test_default_secrets_refuse_boot_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "production")
    monkeypatch.setenv("UCVE_JWT_SECRET", "ucve-jwt-secret")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "strong-enough-mint-secret-value")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "strong-enough-metrics-bearer-val")
    with pytest.raises(BootConfigurationError):
        require_production_secrets()


def test_local_dev_kms_refuses_default_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "production")
    monkeypatch.delenv("UCVE_MASTER_KEY", raising=False)
    with pytest.raises(RuntimeError):
        LocalDevKMSBackend()


def test_oidc_stub_disabled_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    from control_plane.auth.oidc_hook import OIDCNotConfigured, OIDCProviderStub

    monkeypatch.setenv("UCVE_ENV", "production")
    with pytest.raises(OIDCNotConfigured):
        OIDCProviderStub().authenticate_token("any")
