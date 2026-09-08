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
    system_prompt: str = "You are Vertex Voice AI, a helpful, natural, concise voice assistant. Respond directly and concisely in 1-2 short conversational sentences."
    provider_chain: dict[str, Any] = field(default_factory=dict)
    llm_model: str = "openai/gpt-oss-120b"
    tts_voice_id: str = "default"
    initial_greeting: str | None = None
    # Demo / dashboard provider selection (defaults preserve prior behavior).
    stt_provider: str = "gladia"
    llm_provider: str = "groq"
    tts_provider: str = "uplift"

