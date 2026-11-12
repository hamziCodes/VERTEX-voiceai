"""Phase 13: AuthN/AuthZ."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import time

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def auth_module():
    import os

    os.environ.setdefault("UCVE_ENV", "test")
    from control_plane import auth  # type: ignore

    return auth



def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_13_authn_authz_for_dashboard_api_and_sdk.md"
    )
    assert plan.is_file()


def test_hmac_signature_matches_habiba_format(auth_module) -> None:
    expected = auth_module.expected_signature(
        secret="test-secret",
        tenant_id="t1",
        ts="123",
        nonce="n1",
        agent_id="a1",
    )
    assert len(expected) == 64


@pytest.mark.asyncio
async def test_replay_nonce_rejected(auth_module) -> None:
    store = auth_module.NonceStore()
    await store.mark_used("tenant", "nonce-1", ttl_sec=60)
    assert await store.is_used("tenant", "nonce-1") is True


def test_expired_timestamp_rejected(auth_module) -> None:
    secret = "my-secret"
    old_ts = str(int(time.time()) - 120)  # 2 minutes ago
    sig = auth_module.expected_signature(secret, "t1", old_ts, "n1", "a1")
    is_valid = auth_module.verify_mint_signature(
        secret, "t1", old_ts, "n1", "a1", sig, max_age_sec=60
    )
    assert is_valid is False


def test_session_mint_success_and_jwt_generation(auth_module, monkeypatch) -> None:
    import asyncio
    import time

    from control_plane.routes.session import MintContext, handle_session_mint
    from core.db.models import Agent, Tenant

    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_ALLOW_UNSAFE_SESSION_OVERRIDES", "1")

    async def _run() -> None:
        ctx = MintContext()
        await ctx.tenant_repo.create_tenant(Tenant(id="t-tenant-1", name="T1"))
        await ctx.tenant_repo.save_agent(
            Agent(id="agent-007", tenant_id="t-tenant-1", name="007")
        )
        secret = "dev-mint-secret"
        ts = str(int(time.time()))
        nonce = "nonce_mint_123"
        sig = auth_module.expected_signature(secret, "t-tenant-1", ts, nonce, "agent-007")

        status_code, body = await handle_session_mint(
            "t-tenant-1", ts, nonce, "agent-007", sig, secret=secret, ctx=ctx
        )
        assert status_code == 200
        assert "token" in body
        assert body["status"] == "success"
        assert "ws_url" in body

        payload = auth_module.verify_session_jwt(body["token"])
        assert payload["tenant_id"] == "t-tenant-1"
        assert payload["action"] == "roomJoin"

    asyncio.run(_run())


def test_rbac_matrix_enforcement(auth_module) -> None:
    RBACManager = auth_module.RBACManager

    # Viewer cannot write agents
    assert RBACManager.check_permission("tenant_viewer", "agent", "write") is False
    # Editor can write agents
    assert RBACManager.check_permission("tenant_editor", "agent", "write") is True
    # Tenant admin can write agents
    assert RBACManager.check_permission("tenant_admin", "agent", "write") is True
    # Phase 13J: platform staff roles hold no tenant permission (no wildcard)
    assert RBACManager.check_permission("platform_admin", "agent", "write") is False


def test_rate_limiter_exceeded_429(auth_module) -> None:
    limiter = auth_module.RateLimiter(limit_per_min=2)
    assert limiter.is_allowed("tenant-rate-1") is True
    assert limiter.is_allowed("tenant-rate-1") is True
    assert limiter.is_allowed("tenant-rate-1") is False  # 3rd request blocked


def test_api_key_generation_and_scope_verification(auth_module) -> None:
    mgr = auth_module.APIKeyManager()
    raw_key, key_id = mgr.generate_api_key("t1", "SDK Key", scopes=["session:mint", "agent:read"])

    # Valid key with required scope
    rec = mgr.verify_api_key(raw_key, required_scope="session:mint")
    assert rec["tenant_id"] == "t1"

    # Missing scope fails
    with pytest.raises(PermissionError):
        mgr.verify_api_key(raw_key, required_scope="agent:write")

