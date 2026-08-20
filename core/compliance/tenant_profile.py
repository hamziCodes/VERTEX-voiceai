"""UCVE Tenant Compliance Profile Loader."""

from __future__ import annotations

from typing import Any

from core.compliance.tiers import CompliancePolicy, ComplianceTier, policy_for


def _tighten_bool(base: bool, override: Any) -> bool:
    """Overrides may only tighten (False wins); never loosen a True requirement."""
    if override is None:
        return base
    if base and override is False:
        return True
    if not base and override is True:
        return True
    return bool(override) if override is not None else base


class TenantComplianceProfileLoader:
    """Loads and constructs effective compliance policy for tenant with JSONB overrides."""

    @staticmethod
    def load_effective_policy(
        tier: ComplianceTier | str,
        hipaa_baa_acknowledged_at: Any = None,
        policy_overrides: dict[str, Any] | None = None,
    ) -> CompliancePolicy:
        """Construct effective CompliancePolicy; overrides may only tighten policy."""
        base_policy = policy_for(tier)
        overrides = policy_overrides or {}
        has_signed_baa = hipaa_baa_acknowledged_at is not None

        allow_cloud_llm = base_policy.allow_cloud_llm
        if base_policy.tier == ComplianceTier.HIPAA and has_signed_baa:
            allow_cloud_llm = True
        if "allow_cloud_llm" in overrides and overrides["allow_cloud_llm"] is False:
            allow_cloud_llm = False
        # HIPAA without BAA: force closed regardless of overrides (including allow_cloud_llm=True)
        if base_policy.tier == ComplianceTier.HIPAA and not has_signed_baa:
            allow_cloud_llm = False

        allow_cloud_stt = base_policy.allow_cloud_stt
        if "allow_cloud_stt" in overrides and overrides["allow_cloud_stt"] is False:
            allow_cloud_stt = False

        require_baa = _tighten_bool(base_policy.require_baa, overrides.get("require_baa"))
        encryption_required = _tighten_bool(
            base_policy.encryption_required, overrides.get("encryption_required")
        )
        lawful_basis_required = _tighten_bool(
            base_policy.lawful_basis_required, overrides.get("lawful_basis_required")
        )

        min_retention_days = max(
            base_policy.min_retention_days,
            int(overrides.get("min_retention_days", base_policy.min_retention_days)),
        )
        max_retention_days = min(
            base_policy.max_retention_days,
            int(overrides.get("max_retention_days", base_policy.max_retention_days)),
        )

        return CompliancePolicy(
            tier=base_policy.tier,
            allow_cloud_llm=allow_cloud_llm,
            allow_cloud_stt=allow_cloud_stt,
            require_baa=require_baa,
            min_retention_days=min_retention_days,
            max_retention_days=max_retention_days,
            encryption_required=encryption_required,
            lawful_basis_required=lawful_basis_required,
        )


def assert_cloud_llm_allowed(policy: CompliancePolicy) -> None:
    """Raise if cloud LLM is blocked by compliance policy."""
    if not policy.allow_cloud_llm:
        raise PermissionError(
            f"Cloud LLM blocked for compliance tier '{policy.tier.value}' "
            "(missing BAA or policy denial)."
        )


def assert_lawful_basis(policy: CompliancePolicy, session_metadata: dict[str, Any] | None) -> None:
    """GDPR: reject when lawful basis required but missing on session metadata."""
    if not policy.lawful_basis_required:
        return
    meta = session_metadata or {}
    if not meta.get("lawful_basis"):
        raise PermissionError("lawful_basis required on session metadata for gdpr_strict.")
