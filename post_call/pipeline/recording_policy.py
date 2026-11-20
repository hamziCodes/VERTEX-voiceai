"""Compliance Tier Recording Policy Resolver."""

from __future__ import annotations

from collections.abc import Mapping


class RecordingPolicy:
    """Resolve explicit tenant recording requirements without tier guesses."""

    @staticmethod
    def is_recording_required(
        compliance_tier: str, tenant_config: Mapping[str, object] | None = None
    ) -> bool:
        """Return the reviewed tenant requirement; compliance names do not imply it."""
        tier = compliance_tier.lower().strip()
        if tier == "gdpr_strict":
            return False
        return bool((tenant_config or {}).get("recording_required", False))

    @staticmethod
    def validate_record(
        compliance_tier: str,
        has_recording: bool,
        tenant_config: Mapping[str, object] | None = None,
    ) -> bool:
        """Validate if record satisfies compliance recording gate."""
        config = tenant_config or {}
        if has_recording and not (
            config.get("recording_enabled", False)
            and config.get("recording_consent_obtained", False)
        ):
            return False
        if (
            RecordingPolicy.is_recording_required(compliance_tier, config)
            and not has_recording
        ):
            return False
        return True
