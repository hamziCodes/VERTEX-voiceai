"""UCVE Core Multi-Tenant Database Package."""

from __future__ import annotations

from core.db import models, repos
from core.db.models import (
    Agent,
    ComplianceTier,
    KeyTier,
    QuotaState,
    Session,
    SessionRecording,
    SessionTranscript,
    Tenant,
    TenantComplianceProfile,
    UsageEvent,
)
from core.db.session import TenantScopedDBSession, session_context_factory

# Instantiate default repo singletons for convenience / test usage
tenant_repo = repos.TenantRepository()
agent_repo = repos.AgentRepository()
session_repo = repos.SessionRepository()
recording_repo = repos.RecordingRepository()
usage_repo = repos.UsageRepository()

__all__ = [
    "models",
    "repos",
    "Tenant",
    "TenantComplianceProfile",
    "Agent",
    "Session",
    "SessionTranscript",
    "SessionRecording",
    "UsageEvent",
    "QuotaState",
    "KeyTier",
    "ComplianceTier",
    "TenantScopedDBSession",
    "session_context_factory",
    "tenant_repo",
    "agent_repo",
    "session_repo",
    "recording_repo",
    "usage_repo",
]
