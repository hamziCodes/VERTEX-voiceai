"""Phase 13: AuthN/AuthZ."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def auth_module():
    try:
        from control_plane.auth import hmac_mint  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 13 implementation pending: {exc}")
    return hmac_mint


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
    if not os.getenv("REDIS_URL"):
        pytest.skip("REDIS_URL not set")
    store = auth_module.NonceStore()
    await store.mark_used("tenant", "nonce-1", ttl_sec=60)
    assert await store.is_used("tenant", "nonce-1") is True
