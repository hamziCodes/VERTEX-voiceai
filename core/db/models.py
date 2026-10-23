"""UCVE Multi-Tenant Data Models & Record Entities."""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
from typing import Any, Literal

KeyTier = Literal["platform", "byok"]
ComplianceTier = Literal["standard", "hipaa", "gdpr_strict"]


@dataclass
class Tenant:
    """Tenant isolation entity."""

    id: str
    name: str
    key_tier: KeyTier = "platform"
    allow_testing_providers: bool = False
    allowed_origins: list[str] = field(default_factory=list)
    created_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


@dataclass
class TenantComplianceProfile:
    """Tenant compliance & HIPAA/GDPR data policy profile."""

    tenant_id: str
    compliance_tier: ComplianceTier = "standard"
    hipaa_baa_acknowledged_at: datetime.datetime | None = None
    data_retention_days: int = 30
    created_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


@dataclass
class Agent:
    """Voice agent entity owned by tenant."""

    id: str
    tenant_id: str
    name: str
    system_prompt: str = ""
    agent_provider_config: dict[str, Any] = field(default_factory=dict)
    created_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


@dataclass
class Session:
    """Voice session record entity."""

    id: str
    tenant_id: str
    agent_id: str
    transport_type: str = "websocket"
    compliance_tier: ComplianceTier = "standard"
    config_version_id: str | None = None
    agent_config_version: int | None = None
    runtime_plan_hash: str | None = None
    runtime_plan_snapshot: dict[str, Any] = field(default_factory=dict)
    session_language: str | None = None
    session_voice_id: str | None = None
    pinned_at: datetime.datetime | None = None
    degraded_flags: dict[str, Any] = field(default_factory=dict)
    started_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    ended_at: datetime.datetime | None = None


@dataclass
class SessionTranscript:
    """Session queryable transcript JSONB record (dual-column persist)."""

    id: str
    session_id: str
    tenant_id: str
    turns: list[dict[str, Any]] = field(default_factory=list)
    transcript_raw_encrypted: str | None = None
    transcript_redacted: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


@dataclass
class SessionRecording:
    """Session raw audio recording S3 pointer entity."""

    id: str
    session_id: str
    tenant_id: str
    s3_uri: str
    checksum_sha256: str
    file_size_bytes: int = 0
    duration_seconds: float = 0.0
    created_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


@dataclass
class UsageEvent:
    """Append-only metering event entity."""

    id: str
    tenant_id: str
    usage_kind: str
    quantity: float
    event_key: str | None = None
    session_id: str | None = None
    unit: str = "units"
    provider_id: str | None = None
    provider_request_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    recorded_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


@dataclass
class QuotaState:
    """Tenant concurrency & monthly quota state entity."""

    tenant_id: str
    max_concurrent_sessions: int = 10
    monthly_seconds_limit: float = 36000.0
    monthly_seconds_used: float = 0.0
    updated_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
