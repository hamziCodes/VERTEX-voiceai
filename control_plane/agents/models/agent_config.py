"""UCVE Agent Builder - Root Agent Configuration Domain Model."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from control_plane.agents.models.persona import PersonaConfig
from control_plane.agents.models.provider_config import AgentProvidersConfig


class AgentConfig(BaseModel):
    """Tenant-authored agent configuration root domain model."""

    model_config = ConfigDict(extra="forbid")

    agent_id: UUID = Field(
        default_factory=uuid4, description="Unique agent identifier."
    )
    tenant_id: UUID = Field(description="Owning tenant identifier.")
    name: str = Field(
        min_length=1, max_length=255, description="Human-readable agent title."
    )
    description: str = Field(
        default="", max_length=2000, description="Functional summary of the agent."
    )
    persona: PersonaConfig = Field(
        default_factory=PersonaConfig, description="Vocal and persona configuration."
    )
    languages: list[str] = Field(
        default_factory=lambda: ["en"],
        description="Supported language codes (e.g. ['en', 'ar']).",
    )
    providers: AgentProvidersConfig = Field(
        default_factory=AgentProvidersConfig.create_default,
        description="Priority chains for STT, LLM, TTS, S2S.",
    )
    tools: list[dict[str, Any]] = Field(
        default_factory=list, description="Registered tool definitions."
    )
    mcp_servers: list[dict[str, Any]] = Field(
        default_factory=list, description="External MCP server endpoints."
    )
    knowledge_bases: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Knowledge base and RAG collection references.",
    )
    extraction_schema_id: str | None = Field(
        default=None, description="Optional CRM structured extraction schema ID."
    )
    extraction_schema: dict[str, Any] | None = Field(
        default=None, description="Optional inline structured extraction schema."
    )
    pronunciation_lexicon: list[dict[str, Any]] = Field(
        default_factory=list, description="Phonetic / pronunciation overrides."
    )
    telephony: dict[str, Any] | None = Field(
        default=None, description="Inbound/outbound telephony trunk settings."
    )
    compliance: dict[str, Any] = Field(
        default_factory=lambda: {"tier": "standard", "hipaa_baa_acknowledged": False},
        description="Compliance tier and HIPAA BAA status.",
    )
    session_limits: dict[str, int] = Field(
        default_factory=lambda: {"max_duration_sec": 3600, "max_turns": 500},
        description="Published per-session duration and turn ceilings.",
    )
    draft_revision: int = Field(
        default=1,
        ge=1,
        description="Optimistic concurrency revision for the editable draft.",
    )
    version: int = Field(
        default=1, ge=1, description="Monotonically increasing version number."
    )
    published_at: datetime | None = Field(
        default=None, description="Timestamp of latest publish."
    )
    is_published: bool = Field(
        default=False, description="Whether this version is active and published."
    )

    def model_dump_json_schema(self) -> str:
        """Export JSON Schema for documentation and Studio validation."""
        import json

        return json.dumps(self.model_json_schema(), indent=2)
