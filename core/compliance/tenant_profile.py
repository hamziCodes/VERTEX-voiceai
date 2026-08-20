"""UCVE Tenant Compliance Profile Loader."""

from __future__ import annotations

from typing import Any

from core.compliance.tiers import CompliancePolicy, ComplianceTier, policy_for


class TenantComplianceProfileLoader:
    """Loads and constructs effective compliance policy for tenant with JSONB overrides."""

    @staticmethod
    def load_effective_policy(
        tier: ComplianceTier | str,
        hipaa_baa_acknowledged_at: Any = None,
        policy_overrides: dict[str, Any] | None = None,
    ) -> CompliancePolicy:
        """Construct effective CompliancePolicy incorporating tier defaults, BAA status, and tenant overrides."""
        base_policy = policy_for(tier)
        overrides = policy_overrides or {}

        has_signed_baa = hipaa_baa_acknowledged_at is not None

        # Allow cloud LLM for HIPAA if BAA signed
        allow_cloud_llm = overrides.get("allow_cloud_llm", base_policy.allow_cloud_llm)
        if base_policy.tier == ComplianceTier.HIPAA and has_signed_baa:
            allow_cloud_llm = True

        return CompliancePolicy(
            tier=base_policy.tier,
            allow_cloud_llm=allow_cloud_llm,
            allow_cloud_stt=overrides.get("allow_cloud_stt", base_policy.allow_cloud_stt),
            require_baa=overrides.get("require_baa", base_policy.require_baa),
            min_retention_days=overrides.get("min_retention_days", base_policy.min_retention_days),
            max_retention_days=overrides.get("max_retention_days", base_policy.max_retention_days),
            encryption_required=overrides.get("encryption_required", base_policy.encryption_required),
            lawful_basis_required=overrides.get("lawful_basis_required", base_policy.lawful_basis_required),
        )
