"""UCVE Compliance Architecture & Classification Package."""

from __future__ import annotations

from core.compliance import classification, erasure, legal_hold, redaction, redaction_policy, retention, tenant_profile, tiers
from core.compliance.classification import (
    ArtifactType,
    DataClass,
    DataClassificationRegistry,
    SubprocessorRegistry,
)
from core.compliance.erasure import ErasureOrchestrator
from core.compliance.legal_hold import LegalHoldManager
from core.compliance.redaction import RedactionService
from core.compliance.redaction_policy import RedactionPolicy
from core.compliance.retention import RetentionScheduler
from core.compliance.tenant_profile import TenantComplianceProfileLoader
from core.compliance.tiers import CompliancePolicy, ComplianceTier, policy_for

__all__ = [
    "classification",
    "tiers",
    "tenant_profile",
    "redaction",
    "redaction_policy",
    "retention",
    "erasure",
    "legal_hold",
    "DataClass",
    "ArtifactType",
    "ComplianceTier",
    "CompliancePolicy",
    "DataClassificationRegistry",
    "SubprocessorRegistry",
    "TenantComplianceProfileLoader",
    "policy_for",
    "RedactionService",
    "RedactionPolicy",
    "RetentionScheduler",
    "ErasureOrchestrator",
    "LegalHoldManager",
]

