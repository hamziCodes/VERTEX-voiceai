"""H0: production secret fail-closed + health surface smoke."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def clear_prod_secrets(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("UCVE_ENV", "production")
    for key in ("UCVE_JWT_SECRET", "UCVE_MINT_HMAC_SECRET", "UCVE_METRICS_BEARER"):
        monkeypatch.delenv(key, raising=False)
    yield


def test_require_production_secrets_refuses_missing(clear_prod_secrets: None) -> None:
    from core.runtime.env import BootConfigurationError, require_production_secrets

    with pytest.raises(BootConfigurationError):
        require_production_secrets()


def test_require_production_secrets_refuses_known_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.runtime.env import BootConfigurationError, require_production_secrets

    monkeypatch.setenv("UCVE_ENV", "production")
    monkeypatch.setenv("UCVE_JWT_SECRET", "ucve-jwt-secret")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "strong-mint-secret-value-32chars")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "strong-metrics-bearer-value-32")
    with pytest.raises(BootConfigurationError):
        require_production_secrets()


def test_development_allows_missing_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.runtime.env import require_production_secrets

    monkeypatch.setenv("UCVE_ENV", "development")
    for key in ("UCVE_JWT_SECRET", "UCVE_MINT_HMAC_SECRET", "UCVE_METRICS_BEARER"):
        monkeypatch.delenv(key, raising=False)
    require_production_secrets()


def test_control_plane_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "development")
    from control_plane.app import app

    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "control-plane"


def test_worker_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "development")
    from worker_raw.main import app

    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "worker-raw"


def test_hardening_foundation_doc_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    doc = root / "voice_engine_plan" / "implementation_plan" / "HARDENING_FOUNDATION.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "FOUNDATION_READY" in text
    assert "H0" in text
