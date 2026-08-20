"""UCVE Pipeline Session Configuration Model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineSessionConfig:
    """Session configuration loaded tenant-scoped for PipelineOrchestrator."""

    session_id: str
    tenant_id: str
    agent_id: str
    language: str = "en"
    compliance_tier: str = "standard"
    hipaa_baa_acknowledged: bool = False
    provider_chain: dict[str, Any] = field(default_factory=dict)
