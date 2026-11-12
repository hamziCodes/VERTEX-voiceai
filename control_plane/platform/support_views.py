"""Allowlisted, read-only tenant projections for support sessions (Phase 13K).

Every field returned here is named explicitly. Prompts, greetings, tool and MCP
definitions, telephony trunk details, credentials, transcripts and recordings are
never copied, so a new sensitive field on a source model cannot leak by default.
"""

from __future__ import annotations

from typing import Any

from control_plane.agents.models.agent_config import AgentConfig
from control_plane.studio.models import (
    OnboardingProfile,
    SupportSession,
    TenantEntitlements,
)

PROVIDER_STAGES = ("stt", "llm", "tts", "s2s")


def session_projection(session: SupportSession) -> dict[str, Any]:
    return session.model_dump(mode="json")


def agent_projection(agent: AgentConfig) -> dict[str, Any]:
    return {
        "agent_id": str(agent.agent_id),
        "name": agent.name,
        "description": agent.description,
        "languages": list(agent.languages),
        "version": agent.version,
        "draft_revision": agent.draft_revision,
        "is_published": agent.is_published,
        "published_at": agent.published_at.isoformat() if agent.published_at else None,
        "provider_route_counts": {
            stage: len(getattr(agent.providers, stage)) for stage in PROVIDER_STAGES
        },
        "knowledge_base_count": len(agent.knowledge_bases),
        "tool_count": len(agent.tools),
        "mcp_server_count": len(agent.mcp_servers),
        "telephony_configured": bool(agent.telephony),
        "compliance_tier": str(agent.compliance.get("tier", "standard")),
    }


def knowledge_base_projection(record: Any) -> dict[str, Any]:
    status = getattr(record, "status", "draft")
    updated_at = getattr(record, "updated_at", None)
    return {
        "knowledge_base_id": str(record.knowledge_base_id),
        "name": record.name,
        "status": getattr(status, "value", status),
        "source_count": int(getattr(record, "source_count", 0)),
        "ready_source_count": int(getattr(record, "ready_source_count", 0)),
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


def onboarding_projection(profile: OnboardingProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "completed_steps": list(profile.completed_steps),
        "use_case": profile.use_case,
        "languages": list(profile.languages),
        "timezone": profile.timezone,
    }


def entitlements_projection(
    entitlements: TenantEntitlements | None,
) -> dict[str, Any] | None:
    if entitlements is None:
        return None
    return entitlements.model_dump(mode="json", exclude={"tenant_id", "updated_at"})


def telephony_projection(state: dict[str, Any] | None) -> dict[str, Any]:
    state = state or {}
    return {
        "trunk_configured": bool(state.get("trunk_configured", False)),
        "telephony_entitled": bool(state.get("telephony_entitled", False)),
        # No carrier probe exists; never report a health we did not measure.
        "carrier_health": "not_measured",
    }
