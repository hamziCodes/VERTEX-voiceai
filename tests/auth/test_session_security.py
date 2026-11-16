from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

import jwt
import pytest
from fastapi.testclient import TestClient

from control_plane.auth.hmac_mint import expected_signature
from control_plane.auth.jwt import (
    JWTConfigurationError,
    issue_session_jwt,
    verify_session_jwt,
)
from control_plane.auth.rate_limit import RateLimiter
from control_plane.routes.session import MintContext, handle_session_refresh
from core.db.models import Session
from core.redis.nonce_store import NonceStore, ReplayStoreUnavailableError
from core.redis.token_store import SessionTokenStore
from core.runtime.env import BootConfigurationError, require_production_secrets


def test_session_jwt_has_strict_identity_and_routing_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    token = issue_session_jwt("tenant-a", "session-a", "agent-a")
    payload = verify_session_jwt(token)

    assert payload["sub"] == "session-a"
    assert payload["tenant_id"] == "tenant-a"
    assert payload["agent_id"] == "agent-a"
    assert payload["action"] == "roomJoin"
    assert payload["token_type"] == "session_access"
    assert payload["iss"] == "wavia-control-plane"
    assert payload["aud"] == "wavia-worker"
    assert isinstance(payload["jti"], str) and payload["jti"]


def test_session_jwt_rejects_wrong_issuer_and_audience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    now = int(datetime.now(UTC).timestamp())
    secret = "ucve-jwt-secret-test-only-32bytes!"
    base = {
        "sub": "session-a",
        "tenant_id": "tenant-a",
        "agent_id": "agent-a",
        "action": "roomJoin",
        "token_type": "session_access",
        "jti": "jti-a",
        "iat": now,
        "exp": now + 60,
    }
    wrong_issuer = jwt.encode(
        {**base, "iss": "attacker", "aud": "wavia-worker"},
        secret,
        algorithm="HS256",
    )
    wrong_audience = jwt.encode(
        {**base, "iss": "wavia-control-plane", "aud": "other"},
        secret,
        algorithm="HS256",
    )
    with pytest.raises(ValueError, match="Invalid session token"):
        verify_session_jwt(wrong_issuer)
    with pytest.raises(ValueError, match="Invalid session token"):
        verify_session_jwt(wrong_audience)


def test_staging_rejects_default_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "staging")
    monkeypatch.delenv("UCVE_JWT_SECRET", raising=False)
    with pytest.raises(JWTConfigurationError):
        issue_session_jwt("tenant-a", "session-a", "agent-a")


@pytest.mark.asyncio
async def test_nonce_consumption_is_atomic_under_concurrency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    store = NonceStore(redis_url=None)
    results = await asyncio.gather(
        *(store.consume_once("tenant-a", "nonce-a", ttl_sec=60) for _ in range(20))
    )
    assert results.count(True) == 1
    assert results.count(False) == 19


@pytest.mark.asyncio
async def test_nonce_redis_claim_uses_set_nx_with_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")

    class FakeRedis:
        call: tuple[str, str, int, bool] | None = None

        async def set(self, key: str, value: str, *, ex: int, nx: bool = False) -> bool:
            self.call = (key, value, ex, nx)
            return True

    redis = FakeRedis()
    store = NonceStore(redis_client=redis)
    assert await store.consume_once("tenant-a", "nonce-a", ttl_sec=45) is True
    assert redis.call == ("ucve:nonce:tenant-a:nonce-a", "1", 45, True)


@pytest.mark.asyncio
async def test_nonce_store_fails_closed_without_redis_in_staging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "staging")
    monkeypatch.delenv("REDIS_URL", raising=False)
    store = NonceStore(redis_url=None)
    with pytest.raises(ReplayStoreUnavailableError):
        await store.consume_once("tenant-a", "nonce-a", ttl_sec=60)


@pytest.mark.asyncio
async def test_token_connection_and_refresh_are_each_one_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    store = SessionTokenStore(redis_url=None)
    assert await store.claim_connection("tenant-a", "jti-a", 60) is True
    assert await store.claim_connection("tenant-a", "jti-a", 60) is False
    assert await store.consume_refresh("tenant-a", "jti-a", 60) is True
    assert await store.consume_refresh("tenant-a", "jti-a", 60) is False
    assert await store.is_revoked("tenant-a", "jti-a") is True


@pytest.mark.asyncio
async def test_refresh_rotates_once_and_checks_persisted_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    ctx = MintContext()
    await ctx.session_repo.create_session(
        "tenant-a",
        Session(id="session-a", tenant_id="tenant-a", agent_id="agent-a"),
    )
    token = issue_session_jwt(
        "tenant-a",
        "session-a",
        "agent-a",
        provider_mode_constraint="mock",
        stt_transcript_mode_constraint="fixed_mock",
    )

    status, body = await handle_session_refresh(token, ctx=ctx)
    assert status == 200
    refreshed = verify_session_jwt(body["token"])
    assert refreshed["jti"] != verify_session_jwt(token)["jti"]
    assert refreshed["provider_mode_constraint"] == "mock"
    assert refreshed["stt_transcript_mode_constraint"] == "fixed_mock"

    replay_status, replay_body = await handle_session_refresh(token, ctx=ctx)
    assert replay_status == 401
    assert replay_body == {"error": "Invalid or unavailable session token."}


def test_api_key_cannot_mint_for_another_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_DEMO_MODE", "0")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "test-mint-secret-value")
    monkeypatch.setenv("UCVE_JWT_SECRET", "test-jwt-secret-value-32-bytes-ok")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "test-metrics-value")
    from control_plane.app import app

    with TestClient(app) as client:
        raw, _ = app.state.api_keys.generate_api_key(
            "tenant-a",
            "mint-test",
            scopes=["session:mint"],
            role="tenant_editor",
        )
        response = client.post(
            "/mint",
            headers={"Authorization": f"Bearer {raw}"},
            json={"tenant_id": "tenant-b", "agent_id": "agent-b"},
        )
    assert response.status_code == 403


def test_api_key_cannot_use_signed_mint_for_another_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "test-mint-secret-value")
    monkeypatch.setenv("UCVE_JWT_SECRET", "test-jwt-secret-value-32-bytes-ok")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "test-metrics-value")
    from control_plane.app import app

    timestamp = str(int(time.time()))
    nonce = "tenant-bound-nonce"
    signature = expected_signature(
        "test-mint-secret-value", "tenant-b", timestamp, nonce, "agent-b"
    )
    with TestClient(app) as client:
        raw, _ = app.state.api_keys.generate_api_key(
            "tenant-a",
            "signed-mint-test",
            scopes=["session:mint"],
            role="tenant_editor",
        )
        response = client.post(
            "/v1/session",
            headers={
                "Authorization": f"Bearer {raw}",
                "X-Tenant-Id": "tenant-b",
                "X-Timestamp": timestamp,
                "X-Nonce": nonce,
                "X-Agent-Id": "agent-b",
                "X-Signature": signature,
            },
        )
    assert response.status_code == 403


def test_demo_mode_cannot_be_enabled_in_staging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "staging")
    monkeypatch.setenv("UCVE_DEMO_MODE", "1")
    from control_plane.app import _demo_mode

    assert _demo_mode() is False


def test_staging_rejects_shipped_auth_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "staging")
    monkeypatch.setenv("UCVE_JWT_SECRET", "ucve-jwt-secret")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "dev-mint-secret")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "ucve-metrics-bearer")
    with pytest.raises(BootConfigurationError):
        require_production_secrets()


def test_auth_request_size_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "test-mint-secret-value")
    monkeypatch.setenv("UCVE_JWT_SECRET", "test-jwt-secret-value-32-bytes-ok")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "test-metrics-value")
    from control_plane.app import app

    with TestClient(app) as client:
        response = client.post(
            "/v1/session/refresh",
            content=b"x" * 8193,
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 413


def test_auth_rate_limit_ignores_forwarded_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "test-mint-secret-value")
    monkeypatch.setenv("UCVE_JWT_SECRET", "test-jwt-secret-value-32-bytes-ok")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "test-metrics-value")
    from control_plane.app import app

    with TestClient(app) as client:
        original_limiter = app.state.auth_endpoint_limiter
        app.state.auth_endpoint_limiter = RateLimiter(limit_per_min=1)
        try:
            first = client.post(
                "/v1/session/refresh",
                headers={"X-Forwarded-For": "198.51.100.1"},
                json={"token": "invalid"},
            )
            second = client.post(
                "/v1/session/refresh",
                headers={"X-Forwarded-For": "203.0.113.9"},
                json={"token": "invalid"},
            )
        finally:
            app.state.auth_endpoint_limiter = original_limiter
    assert first.status_code == 401
    assert second.status_code == 429


class _BrokenRedis:
    """A configured Redis whose connection just dropped (e.g. a restart)."""

    async def set(self, *_args: object, **_kwargs: object) -> bool:
        raise ConnectionError("Connection closed by server.")

    async def eval(self, *_args: object, **_kwargs: object) -> int:
        raise ConnectionError("Connection closed by server.")

    async def exists(self, *_args: object, **_kwargs: object) -> int:
        raise ConnectionError("Connection closed by server.")


@pytest.mark.asyncio
@pytest.mark.parametrize("environment", ["development", "test", "production"])
async def test_redis_outage_is_unavailable_not_a_replay_or_lost_revocation(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    """Regression (Phase 15 Redis-restart drill): outside protected
    environments a dropped connection reported 'nonce replay' (401) and a
    revocation was silently discarded."""
    monkeypatch.setenv("UCVE_ENV", environment)
    nonces = NonceStore(redis_client=_BrokenRedis())
    tokens = SessionTokenStore(redis_client=_BrokenRedis())

    with pytest.raises(ReplayStoreUnavailableError):
        await nonces.consume_once("tenant-a", "nonce-a", ttl_sec=60)
    with pytest.raises(ReplayStoreUnavailableError):
        await nonces.is_used("tenant-a", "nonce-a")
    with pytest.raises(ReplayStoreUnavailableError):
        await tokens.claim_connection("tenant-a", "jti-a", 60)
    with pytest.raises(ReplayStoreUnavailableError):
        await tokens.consume_refresh("tenant-a", "jti-a", 60)
    with pytest.raises(ReplayStoreUnavailableError):
        await tokens.revoke("tenant-a", "jti-a", 60)
    with pytest.raises(ReplayStoreUnavailableError):
        await tokens.is_revoked("tenant-a", "jti-a")


@pytest.mark.asyncio
async def test_refresh_during_store_outage_is_503_not_invalid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    ctx = MintContext(token_store=SessionTokenStore(redis_client=_BrokenRedis()))
    await ctx.session_repo.create_session(
        "tenant-a",
        Session(id="session-a", tenant_id="tenant-a", agent_id="agent-a"),
    )
    token = issue_session_jwt("tenant-a", "session-a", "agent-a")

    status, body = await handle_session_refresh(token, ctx=ctx)

    assert status == 503
    assert body == {"error": "Session token state is temporarily unavailable."}


def test_redis_clients_check_idle_connections_and_bound_timeouts() -> None:
    """Regression (Phase 15 Redis-restart drill): the first command after a
    Redis restart went out on a dead pooled socket."""
    from core.redis.client import async_redis_from_url, sync_redis_from_url

    for client in (
        async_redis_from_url("redis://127.0.0.1:1/0"),
        sync_redis_from_url("redis://127.0.0.1:1/0"),
    ):
        kwargs = client.connection_pool.connection_kwargs
        assert kwargs["health_check_interval"] == 5
        assert kwargs["socket_timeout"] == 2.0
        assert kwargs["socket_connect_timeout"] == 2.0
