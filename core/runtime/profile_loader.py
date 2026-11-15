"""Runtime profile loader and configuration model (Phase 31)."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class RuntimeProfileName(str, Enum):
    DEV = "dev"
    STANDARD = "standard"
    HIGH_DENSITY = "high_density"


class RuntimeProfile(BaseModel):
    """Runtime profile parameters defining concurrency and resource boundaries."""

    name: str
    max_sessions_per_worker: int = Field(..., ge=1)
    silero_pool_size: int = Field(..., ge=1)
    asyncio_worker_tasks: int = Field(..., ge=1)
    redis_memory_mb: int = Field(..., ge=64)
    postgres_conn_pool: int = Field(..., ge=1)
    max_provider_streams: int = Field(..., ge=1)
    worker_ram_gb: int = Field(..., ge=1)
    worker_vcpu: int = Field(..., ge=1)


REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = REPO_ROOT / "infra" / "scaling" / "profiles"


class ProfileNotFoundError(FileNotFoundError):
    """Raised when the selected runtime profile does not exist."""


def _resolve_profile_path(name_or_path: str | Path | None) -> Path:
    if name_or_path is None:
        name_or_path = os.getenv("UCVE_RUNTIME_PROFILE", "dev").strip() or "dev"
    if isinstance(name_or_path, str) and not name_or_path.endswith((".yaml", ".yml")):
        return PROFILES_DIR / f"{name_or_path.lower()}.yaml"
    return Path(name_or_path)


def _read_profile(profile_path: Path) -> RuntimeProfile:
    with open(profile_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return RuntimeProfile(**data)


def load_profile_strict(name_or_path: str | Path | None = None) -> RuntimeProfile:
    """Load the selected profile or raise :class:`ProfileNotFoundError`."""
    profile_path = _resolve_profile_path(name_or_path)
    if not profile_path.is_file():
        raise ProfileNotFoundError(f"Runtime profile not found: {profile_path.name}")
    return _read_profile(profile_path)


def load_profile(name_or_path: str | Path | None = None) -> RuntimeProfile:
    """Load a runtime profile by name (dev, standard, high_density) or file path.

    If name_or_path is None, inspects the UCVE_RUNTIME_PROFILE environment variable,
    defaulting to 'dev'. Protected environments (staging/production) refuse an
    unknown profile; development keeps the dev fallback, and readiness reports
    the mismatch either way.
    """
    from core.runtime.env import is_protected_environment

    try:
        return load_profile_strict(name_or_path)
    except ProfileNotFoundError:
        if is_protected_environment():
            raise
        fallback = PROFILES_DIR / "dev.yaml"
        if not fallback.is_file():
            raise
        return _read_profile(fallback)
