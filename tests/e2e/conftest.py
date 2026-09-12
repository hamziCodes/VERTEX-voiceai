"""E2E test suite fixtures and lifecycle hooks (Phase 33)."""

from __future__ import annotations

import os
import pytest


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure mock environment variables are set for deterministic E2E tests."""
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_RUNTIME_PROFILE", "dev")
    monkeypatch.delenv("RUN_LIVE_PROVIDERS", raising=False)


@pytest.fixture
def compose_stack_available() -> bool:
    """Optional fixture to detect if local docker compose stack is up."""
    return os.getenv("UCVE_COMPOSE_E2E", "false").lower() == "true"
