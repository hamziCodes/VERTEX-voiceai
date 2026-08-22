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
    transport_type: str = "websocket"  # "websocket" or "sip"
    caller_id: Any | None = None  # CallerIdContext for PSTN/telephony sessions
    provider_chain: dict[str, Any] = field(default_factory=dict)
