"""Provider execution-mode guard shared by production adapters."""

from __future__ import annotations

import os

from core.providers.exceptions import ConfigurationError

_PRODUCTION_ENVS = frozenset({"production", "prod", "staging"})


def provider_runtime_status() -> dict[str, str]:
    """Describe provider/STT behavior without exposing credential state."""
    explicit_mock = os.environ.get("RUN_MOCK_PROVIDERS") == "1"
    environment = os.environ.get("UCVE_ENV", "").strip().lower()
    live_mode = not explicit_mock and (
        os.environ.get("RUN_LIVE_PROVIDERS") == "1"
        or environment in _PRODUCTION_ENVS
    )
    if live_mode:
        return {"provider_mode": "live", "stt_transcript_mode": "live"}
    mock_text = (os.environ.get("UCVE_STT_MOCK_TEXT") or "").strip()
    return {
        "provider_mode": "mock",
        "stt_transcript_mode": "fixed_mock" if mock_text else "disabled",
    }


def should_use_mock_provider(*, provider_id: str, api_key: str) -> bool:
    """Return explicit mock mode, or require credentials when live mode applies."""
    if os.environ.get("RUN_MOCK_PROVIDERS") == "1":
        return True

    environment = os.environ.get("UCVE_ENV", "").strip().lower()
    live_mode = (
        os.environ.get("RUN_LIVE_PROVIDERS") == "1" or environment in _PRODUCTION_ENVS
    )
    if live_mode and not api_key:
        raise ConfigurationError(
            f"{provider_id} credential is required in production/live provider mode"
        )
    return not live_mode


def provider_is_locally_ready(*, api_key: str) -> bool:
    """Report local route readiness without making a billable network request."""

    if provider_runtime_status()["provider_mode"] == "mock":
        return True
    return bool(api_key.strip())
