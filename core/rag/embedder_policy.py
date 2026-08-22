"""Tier-Aware Embedder Policy — Enforces local embedders for HIPAA / GDPR strict tiers."""

from __future__ import annotations


class EmbedderPolicy:
    """Enforces embedding model selection per compliance tier."""

    @staticmethod
    def is_cloud_embedder_allowed(compliance_tier: str, tenant_opt_in: bool = False) -> bool:
        """Return True if cloud embedding API is permitted."""
        tier = compliance_tier.lower().strip()
        if tier in ("hipaa", "gdpr_strict"):
            # Cloud embedder blocked for HIPAA/GDPR_STRICT (PHI protection)
            return False
        return tenant_opt_in

    @staticmethod
    def get_embedder_type(compliance_tier: str, tenant_opt_in: bool = False) -> str:
        """Return 'local' or 'cloud' embedder target."""
        if EmbedderPolicy.is_cloud_embedder_allowed(compliance_tier, tenant_opt_in):
            return "cloud"
        return "local"
