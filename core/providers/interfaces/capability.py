"""UCVE Provider Capability Status & Tracking Models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProviderCapabilityStatus(str, Enum):
    """Health & capability status of an AI provider."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DISABLED = "disabled"


@dataclass
class ProviderCapabilityEntry:
    """Capability status entry for provider registry tracking."""

    provider_id: str
    category: str
    status: ProviderCapabilityStatus = ProviderCapabilityStatus.HEALTHY
    latency_ms: float = 0.0
    error_rate: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
