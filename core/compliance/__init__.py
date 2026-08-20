"""UCVE Compliance Architecture & Classification Package."""

from __future__ import annotations

from core.compliance import classification, tenant_profile, tiers
from core.compliance.classification import (
    ArtifactType,
    DataClass,
    DataClassificationRegistry,
    SubprocessorRegistry,
)
from core.compliance.tenant_profile import TenantComplianceProfileLoader
from core.compliance.tiers import CompliancePolicy, ComplianceTier, policy_for

__all__ = [
    "classification",
    "tiers",
    "tenant_profile",
    "DataClass",
    "ArtifactType",
    "ComplianceTier",
    "CompliancePolicy",
    "DataClassificationRegistry",
    "SubprocessorRegistry",
    "TenantComplianceProfileLoader",
    "policy_for",
]
