"""UCVE Pipeline Session Configuration Model."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from core.runtime.session_plan import (
    RuntimeProviderRoute,
    RuntimeSessionPlan,
    RuntimeSessionSelection,
)


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
    system_prompt: str = (
        "You are Vertex Voice AI, a helpful, natural, concise voice assistant. "
        "Respond directly and concisely in 1-2 short conversational sentences."
    )
    provider_chain: dict[str, Any] = field(default_factory=dict)
    llm_model: str = "openai/gpt-oss-120b"
    tts_voice_id: str = "default"
    initial_greeting: str | None = None
    # Demo / dashboard provider selection (defaults preserve prior behavior).
    stt_provider: str = "gladia"
    llm_provider: str = "groq"
    tts_provider: str = "uplift"
    plan_authoritative: bool = False
    session_plan_ref: str | None = None
    session_plan_hash: str | None = None
    agent_config_version: int | None = None
    allowed_languages: tuple[str, ...] = ("en",)
    tool_allowlist: tuple[str, ...] = ()
    tool_definitions: tuple[dict[str, Any], ...] = ()
    knowledge_base_ids: tuple[str, ...] = ()
    extraction_schema_id: str | None = None
    extraction_schema: dict[str, Any] | None = None
    telephony_policy: dict[str, Any] | None = None
    max_duration_sec: int = 3600
    max_turns: int = 500
    recording_enabled: bool = False
    recording_consent_obtained: bool = False
    transcript_retention_days: int = 30
    recording_retention_days: int = 7
    storage_region: str = "local"
    requires_review_for_external_actions: bool = True
    allow_unsafe_session_overrides: bool = False

    def runtime_provider_routes(
        self, category: str
    ) -> tuple[RuntimeProviderRoute, ...]:
        """Parse one authenticated category chain without accepting extras."""
        raw_routes = self.provider_chain.get(category)
        if not isinstance(raw_routes, list):
            raise ValueError(f"Published provider chain {category!r} is missing.")
        return tuple(RuntimeProviderRoute.model_validate(route) for route in raw_routes)

    @classmethod
    def from_runtime_plan(
        cls,
        *,
        session_id: str,
        plan: RuntimeSessionPlan,
        selection: RuntimeSessionSelection,
        transport_type: str = "websocket",
        caller_id: Any | None = None,
        allow_unsafe_session_overrides: bool = False,
    ) -> PipelineSessionConfig:
        """Materialize the mutable per-session view of one immutable plan."""

        stt = plan.primary_route("stt", selection.language)
        llm = plan.primary_route("llm", selection.language)
        tts = plan.primary_route("tts", selection.language)
        chains = {
            category: [
                route.model_dump(mode="json")
                for route in plan.provider_chain(category, selection.language).routes
            ]
            for category in ("stt", "llm", "tts")
        }
        tool_definitions = tuple(json.loads(plan.tool_definitions_json))
        extraction_schema = (
            json.loads(plan.extraction_schema_json)
            if plan.extraction_schema_json is not None
            else None
        )
        telephony_policy = (
            json.loads(plan.telephony_policy_json)
            if plan.telephony_policy_json is not None
            else None
        )
        return cls(
            session_id=session_id,
            tenant_id=plan.tenant_id,
            agent_id=plan.agent_id,
            language=selection.language,
            compliance_tier=plan.compliance_tier,
            hipaa_baa_acknowledged=plan.hipaa_baa_acknowledged,
            transport_type=transport_type,
            caller_id=caller_id,
            system_prompt=plan.system_prompt,
            provider_chain=chains,
            llm_model=llm.model or "",
            tts_voice_id=selection.voice_id,
            initial_greeting=plan.initial_greeting,
            stt_provider=stt.provider_id,
            llm_provider=llm.provider_id,
            tts_provider=tts.provider_id,
            plan_authoritative=not plan.unsafe_demo,
            session_plan_ref=plan.plan_id,
            session_plan_hash=plan.plan_hash,
            agent_config_version=plan.agent_version,
            allowed_languages=plan.allowed_languages,
            tool_allowlist=plan.tool_allowlist,
            tool_definitions=tool_definitions,
            knowledge_base_ids=plan.knowledge_base_ids,
            extraction_schema_id=plan.extraction_schema_id,
            extraction_schema=extraction_schema,
            telephony_policy=telephony_policy,
            max_duration_sec=plan.limits.max_duration_sec,
            max_turns=plan.limits.max_turns,
            allow_unsafe_session_overrides=allow_unsafe_session_overrides,
        )
