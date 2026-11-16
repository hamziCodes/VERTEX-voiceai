from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from control_plane.auth.jwt import issue_session_jwt
from worker_raw import main as worker_main
from worker_raw.main import (
    ProviderModeConstraintError,
    _enforce_provider_mode_constraint,
)


def test_worker_rejects_signed_mode_mismatch_before_session_start() -> None:
    with pytest.raises(ProviderModeConstraintError, match="provider mode"):
        _enforce_provider_mode_constraint(
            {"provider_mode_constraint": "mock"},
            {"provider_mode": "live", "stt_transcript_mode": "live"},
        )


def test_worker_rejects_signed_mock_transcript_mismatch() -> None:
    with pytest.raises(ProviderModeConstraintError, match="transcript mode"):
        _enforce_provider_mode_constraint(
            {
                "provider_mode_constraint": "mock",
                "stt_transcript_mode_constraint": "fixed_mock",
            },
            {"provider_mode": "mock", "stt_transcript_mode": "disabled"},
        )


def test_worker_accepts_matching_signed_mode_constraints() -> None:
    _enforce_provider_mode_constraint(
        {
            "provider_mode_constraint": "mock",
            "stt_transcript_mode_constraint": "fixed_mock",
        },
        {"provider_mode": "mock", "stt_transcript_mode": "fixed_mock"},
    )


def test_websocket_rejects_mode_mismatch_before_claiming_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setattr(
        worker_main,
        "provider_runtime_status",
        lambda: {"provider_mode": "live", "stt_transcript_mode": "live"},
    )
    token = issue_session_jwt(
        "tenant-a",
        "session-a",
        "agent-a",
        provider_mode_constraint="mock",
    )

    class ClaimSpy:
        calls = 0

        async def claim_connection(self, *_args: object) -> bool:
            self.calls += 1
            return True

    store = ClaimSpy()
    with TestClient(worker_main.app) as client:
        worker_main.app.state.token_store = store
        with pytest.raises(WebSocketDisconnect) as caught:
            with client.websocket_connect(f"/ws/audio?token={token}"):
                pass

    assert caught.value.code == 4403
    assert store.calls == 0


def test_session_store_outage_closes_with_retryable_1013_not_auth_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression (Phase 15 Redis-restart drill): a store outage was reported
    to the client as 4401 'invalid token'."""
    from core.redis.nonce_store import ReplayStoreUnavailableError

    monkeypatch.setenv("UCVE_ENV", "test")
    token = issue_session_jwt("tenant-a", "session-a", "agent-a")

    class DownStore:
        async def claim_connection(self, *_args: object) -> bool:
            raise ReplayStoreUnavailableError("down")

    with TestClient(worker_main.app) as client:
        worker_main.app.state.token_store = DownStore()
        with pytest.raises(WebSocketDisconnect) as caught:
            with client.websocket_connect(f"/ws/audio?token={token}") as ws:
                ws.receive_text()

    assert caught.value.code == 1013


def test_database_outage_while_loading_the_session_is_retryable_1013(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression (Phase 15 network drill): a dead pooled connection while
    loading the pinned plan was reported as 4401 'invalid session'."""
    from psycopg_pool import PoolTimeout

    monkeypatch.setenv("UCVE_ENV", "test")
    token = issue_session_jwt("tenant-a", "session-a", "agent-a")

    class Claims:
        async def claim_connection(self, *_args: object) -> bool:
            return True

    async def database_down(*_args: object, **_kwargs: object) -> None:
        raise PoolTimeout("couldn't get a connection")

    monkeypatch.setattr(worker_main, "_load_session_config", database_down)
    with TestClient(worker_main.app) as client:
        worker_main.app.state.token_store = Claims()
        with pytest.raises(WebSocketDisconnect) as caught:
            with client.websocket_connect(f"/ws/audio?token={token}") as ws:
                ws.receive_text()

    assert caught.value.code == 1013


@pytest.mark.parametrize(
    ("error_name", "reason"),
    [
        ("AdmissionStoreUnavailableError", "session admission unavailable"),
        ("CapacityExceededError", "cluster at capacity"),
    ],
)
def test_admission_failure_is_a_retryable_1013_not_a_normal_close(
    monkeypatch: pytest.MonkeyPatch, error_name: str, reason: str
) -> None:
    """Regression (Phase 15 Redis-restart drill): an unavailable admission
    store ended the socket with 1000 'session ended', like a finished call."""
    import core.runtime.admission as admission

    monkeypatch.setenv("UCVE_ENV", "test")
    token = issue_session_jwt("tenant-a", "session-a", "agent-a")
    error = getattr(admission, error_name)

    class Claims:
        async def claim_connection(self, *_args: object) -> bool:
            return True

    async def loaded_config(*_args: object, **_kwargs: object) -> object:
        class Config:
            session_id = "session-a"
            tenant_id = "tenant-a"

        return Config()

    async def refuse(*_args: object, **_kwargs: object) -> None:
        raise error("refused")

    monkeypatch.setattr(worker_main, "_load_session_config", loaded_config)
    monkeypatch.setattr(worker_main.session_admission, "acquire", refuse)
    with TestClient(worker_main.app) as client:
        worker_main.app.state.token_store = Claims()
        with pytest.raises(WebSocketDisconnect) as caught:
            with client.websocket_connect(f"/ws/audio?token={token}") as ws:
                ws.receive_text()

    assert caught.value.code == 1013
    assert caught.value.reason == reason
