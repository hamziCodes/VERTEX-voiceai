"""UCVE Audit Event Action Taxonomy."""

from __future__ import annotations

from enum import Enum


class AuditAction(str, Enum):
    """Canonical audit action types for system security and compliance tracking."""

    SESSION_MINT = "session_mint"
    SESSION_MINT_REJECTED = "session_mint_rejected"
    CREDENTIAL_RESOLVE = "credential_resolve"
    CREDENTIAL_ROTATE = "credential_rotate"
    AGENT_CONFIG_PUBLISHED = "agent_config_published"
    TRANSCRIPT_VIEW = "transcript_view"
    RECORDING_ACCESS = "recording_access"
    DATA_EXPORT = "data_export"
    DATA_PURGE = "data_purge"
    DATA_ERASURE = "data_erasure"
    COMPLIANCE_TIER_CHANGE = "compliance_tier_change"
    API_KEY_CREATE = "api_key_create"
    API_KEY_REVOKE = "api_key_revoke"
    PROVIDER_PROMOTE = "provider_promote"
    QUOTA_SLOT_RELEASED_STALE = "quota_slot_released_stale"
    CALL_RECORD_CREATED = "call_record_created"
    CRM_DISPATCH = "crm_dispatch"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    MCP_CONNECT = "mcp_connect"
    TOOL_TIMEOUT_FALLBACK = "tool_timeout_fallback"
