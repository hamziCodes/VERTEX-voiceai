"""Platform-managed credential lookup boundary."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PlatformCredential:
    """Platform credential plus non-secret rotation identity."""

    secret: str = field(repr=False, compare=False)
    version: str = "environment"


class PlatformSecretProvider(Protocol):
    """Boundary used by the vault to retrieve platform-owned credentials."""

    def resolve(
        self, provider_id: str, credential_type: str
    ) -> PlatformCredential | None: ...


class EnvironmentPlatformSecretProvider:
    """Read platform credentials from process configuration at the boundary."""

    def resolve(
        self, provider_id: str, credential_type: str
    ) -> PlatformCredential | None:
        if credential_type != "api_key":
            return None
        normalized = provider_id.strip().upper()
        value = os.getenv(f"PLATFORM_{normalized}_API_KEY")
        if value is None or not value.strip():
            return None
        return PlatformCredential(secret=value.strip())
