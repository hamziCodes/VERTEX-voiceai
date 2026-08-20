"""UCVE Compliance Tiers & Policy Engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ComplianceTier(str, Enum):
    """Supported compliance tiers."""

    STANDARD = "standard"
    HIPAA = "hipaa"
    GDPR_STRICT = "gdpr_strict"
    PCI_DSS = "pci_dss"  # Reserved — out of scope for v1


@dataclass
class CompliancePolicy:
    """Policy rules governing data storage, transmission, and vendor subprocessors."""

    tier: ComplianceTier
    allow_cloud_llm: bool = True
    allow_cloud_stt: bool = True
    require_baa: bool = False
    min_retention_days: int = 1
    max_retention_days: int = 90
    encryption_required: bool = True
    lawful_basis_required: bool = False


_tier_policies: dict[ComplianceTier, CompliancePolicy] = {
    ComplianceTier.STANDARD: CompliancePolicy(
        tier=ComplianceTier.STANDARD,
        allow_cloud_llm=True,
        allow_cloud_stt=True,
        require_baa=False,
        min_retention_days=1,
        max_retention_days=90,
        encryption_required=True,
    ),
    ComplianceTier.HIPAA: CompliancePolicy(
        tier=ComplianceTier.HIPAA,
        allow_cloud_llm=False,  # Blocked unless BAA acknowledged
        allow_cloud_stt=True,
        require_baa=True,
        min_retention_days=30,
        max_retention_days=2555,  # 7 years HIPAA requirement
        encryption_required=True,
    ),
    ComplianceTier.GDPR_STRICT: CompliancePolicy(
        tier=ComplianceTier.GDPR_STRICT,
        allow_cloud_llm=True,
        allow_cloud_stt=True,
        require_baa=False,
        min_retention_days=1,
        max_retention_days=30,
        encryption_required=True,
        lawful_basis_required=True,
    ),
}


def policy_for(tier: ComplianceTier | str) -> CompliancePolicy:
    """Retrieve compliance policy rules for given tier."""
    if isinstance(tier, str):
        tier = ComplianceTier(tier.lower())
    return _tier_policies.get(tier, _tier_policies[ComplianceTier.STANDARD])
