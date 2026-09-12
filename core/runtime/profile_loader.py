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


def load_profile(name_or_path: str | Path | None = None) -> RuntimeProfile:
    """Load a runtime profile by name (dev, standard, high_density) or file path.

    If name_or_path is None, inspects the UCVE_RUNTIME_PROFILE environment variable,
    defaulting to 'dev'.
    """
    if name_or_path is None:
        name_or_path = os.getenv("UCVE_RUNTIME_PROFILE", "dev").strip()

    if isinstance(name_or_path, str) and not name_or_path.endswith((".yaml", ".yml")):
        profile_path = PROFILES_DIR / f"{name_or_path.lower()}.yaml"
    else:
        profile_path = Path(name_or_path)

    if not profile_path.is_file():
        # Fallback to dev if specified profile not found
        fallback = PROFILES_DIR / "dev.yaml"
        if fallback.is_file():
            profile_path = fallback
        else:
            raise FileNotFoundError(f"Runtime profile not found: {profile_path}")

    with open(profile_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return RuntimeProfile(**data)
