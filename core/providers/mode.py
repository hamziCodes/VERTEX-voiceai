"""Provider execution-mode guard shared by production adapters."""

from __future__ import annotations

import os

from core.providers.exceptions import ConfigurationError

_PRODUCTION_ENVS = frozenset({"production", "prod", "staging"})


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
