"""Compliance Tier Recording Policy Resolver."""

from __future__ import annotations


class RecordingPolicy:
    """Enforces recording requirements per compliance tier (HIPAA / GDPR / Standard)."""

    @staticmethod
    def is_recording_required(compliance_tier: str, tenant_config: dict | None = None) -> bool:
        """Return True if recording is mandatory for compliance tier."""
        tier = compliance_tier.lower().strip()
        if tier in ("hipaa", "gdpr_strict"):
            return True

        if tenant_config:
            # Standard tier allows tenant JSONB override
            return tenant_config.get("recording_enabled", True)

        return True

    @staticmethod
    def validate_record(compliance_tier: str, has_recording: bool) -> bool:
        """Validate if record satisfies compliance recording gate."""
        if RecordingPolicy.is_recording_required(compliance_tier) and not has_recording:
            return False
        return True
