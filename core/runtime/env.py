"""UCVE environment contract and fail-closed production secret checks (H0)."""

from __future__ import annotations

import os
from typing import Final

# Values that must never be accepted when UCVE_ENV=production.
try:
    from pathlib import Path
    from dotenv import load_dotenv

    _root_env = Path(__file__).resolve().parent.parent.parent / ".env"
    if _root_env.exists():
        load_dotenv(dotenv_path=str(_root_env), override=False)
except Exception:
    pass
KNOWN_INSECURE_DEFAULTS: Final[frozenset[str]] = frozenset(
    {
        "",
        "change-me",
        "change-me-local-only",
        "ucve-jwt-secret",
        "ucve-mint-hmac-secret",
        "ucve-metrics-bearer",
        "ucve-hmac-salt",
        "ucve-master-key",
        "dev-secret",
        "secret",
        "test",
        "testing",
    }
)

_DEV_ENVS: Final[frozenset[str]] = frozenset({"dev", "development", "test"})


class BootConfigurationError(RuntimeError):
    """Raised when the process must refuse to start."""


def get_ucve_env() -> str:
    """Return normalized UCVE_ENV (default: development)."""
    return (os.environ.get("UCVE_ENV") or "development").strip().lower()


def is_production() -> bool:
    return get_ucve_env() == "production"


def is_test_env() -> bool:
    import sys
    return (
        get_ucve_env() == "test"
        or "PYTEST_CURRENT_TEST" in os.environ
        or "pytest" in sys.modules
    )


def allow_local_dev_kms() -> bool:
    return get_ucve_env() in _DEV_ENVS


def validate_secret_value(name: str, value: str | None) -> str:
    """Return stripped secret or raise if missing/insecure for production."""
    raw = (value or "").strip()
    if is_production():
        if not raw or raw.lower() in KNOWN_INSECURE_DEFAULTS:
            raise BootConfigurationError(
                f"Refusing to start: {name} is missing or equals a known insecure default "
                f"(UCVE_ENV=production)."
            )
    return raw


def require_production_secrets() -> None:
    """
    Fail closed when production crypto/auth material is absent or defaulted.

    Required: UCVE_JWT_SECRET, UCVE_MINT_HMAC_SECRET, UCVE_METRICS_BEARER.
    """
    if not is_production():
        return
    for name in ("UCVE_JWT_SECRET", "UCVE_MINT_HMAC_SECRET", "UCVE_METRICS_BEARER"):
        validate_secret_value(name, os.environ.get(name))
