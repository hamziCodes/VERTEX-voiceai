from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from control_plane.studio.repository import InMemoryStudioRepository


class TokenClaimsProvider:
    _claims = {
        "owner-token": {
            "sub": "owner",
            "iss": "https://identity.test",
            "email": "owner@example.com",
        },
        "member-token": {
            "sub": "member",
            "iss": "https://identity.test",
            "email": "member@example.com",
        },
    }

    def authenticate_token(self, token: str) -> dict[str, object]:
        return dict(self._claims[token])


@pytest.fixture
def studio_api(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "test-mint-secret-value")
    monkeypatch.setenv("UCVE_JWT_SECRET", "test-jwt-secret-value-32-bytes-ok")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "test-metrics-value")
    from control_plane.app import app

    with TestClient(app) as client:
        app.state.oidc_provider = TokenClaimsProvider()
        app.state.studio_repository = InMemoryStudioRepository()
        yield client, app
    for name in (
        "oidc_provider",
        "studio_repository",
        "post_call_repository",
        "post_call_job_repository",
        "telephony_settings_repository",
        "outbound_call_service",
        "secret_vault",
    ):
        if hasattr(app.state, name):
            delattr(app.state, name)
