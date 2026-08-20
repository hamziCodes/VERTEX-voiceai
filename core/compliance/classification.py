"""UCVE Data Classification & Subprocessor Compliance Registry."""

from __future__ import annotations

from enum import Enum
from typing import Any

from core.compliance.tiers import CompliancePolicy, ComplianceTier


class DataClass(str, Enum):
    """Sensitivity classification levels for system data."""

    PUBLIC = "public"
    INTERNAL = "internal"
    PII = "pii"
    PHI = "phi"
    CREDENTIALS = "credentials"
    AUDIT = "audit"


class ArtifactType(str, Enum):
    """UCVE system artifact types."""

    RAW_AUDIO = "raw_audio"
    TRANSCRIPT_TURN = "transcript_turn"
    RECORDING_OBJECT = "recording_object"
    LLM_PROMPT = "llm_prompt"
    LLM_RESPONSE = "llm_response"
    EXTRACTION_OUTPUT = "extraction_output"
    USAGE_EVENT = "usage_event"
    AUDIT_LOG = "audit_log"
    PROVIDER_PAYLOAD = "provider_payload"


class DataClassificationRegistry:
    """Registry mapping artifact types and field paths to sensitivity data classes."""

    def __init__(self) -> None:
        self._mappings: dict[tuple[ArtifactType, str], DataClass] = {}
        self._artifact_types: set[ArtifactType] = set()

    @classmethod
    def load_defaults(cls) -> DataClassificationRegistry:
        """Load default data classification mappings covering all ArtifactTypes."""
        reg = cls()
        defaults: dict[ArtifactType, DataClass] = {
            ArtifactType.RAW_AUDIO: DataClass.PHI,
            ArtifactType.TRANSCRIPT_TURN: DataClass.PHI,
            ArtifactType.RECORDING_OBJECT: DataClass.PHI,
            ArtifactType.LLM_PROMPT: DataClass.PHI,
            ArtifactType.LLM_RESPONSE: DataClass.PHI,
            ArtifactType.EXTRACTION_OUTPUT: DataClass.PII,
            ArtifactType.USAGE_EVENT: DataClass.INTERNAL,
            ArtifactType.AUDIT_LOG: DataClass.AUDIT,
            ArtifactType.PROVIDER_PAYLOAD: DataClass.PII,
        }
        for artifact, dclass in defaults.items():
            reg.register(artifact, "default", dclass)
        return reg

    def register(self, artifact: ArtifactType, field_path: str, data_class: DataClass) -> None:
        self._mappings[(artifact, field_path)] = data_class
        self._artifact_types.add(artifact)

    def has_artifact(self, artifact: ArtifactType) -> bool:
        """Return True if registry contains classification mapping for artifact type."""
        return artifact in self._artifact_types

    def classify(self, artifact: ArtifactType, field_path: str = "default") -> DataClass:
        """Classify artifact field path into DataClass, defaulting to PII/PHI if unknown."""
        key = (artifact, field_path)
        if key in self._mappings:
            return self._mappings[key]
        default_key = (artifact, "default")
        if default_key in self._mappings:
            return self._mappings[default_key]
        return DataClass.PII  # Fail-safe default


class SubprocessorRegistry:
    """Subprocessor vendor registry governing third-party data processing eligibility."""

    _subprocessors: dict[str, dict[str, Any]] = {
        "gladia": {"baa_available": True, "data_classes": [DataClass.PHI, DataClass.PII]},
        "deepgram": {"baa_available": True, "data_classes": [DataClass.PHI, DataClass.PII]},
        "groq": {"baa_available": False, "data_classes": [DataClass.PHI, DataClass.PII]},
        "uplift": {"baa_available": False, "data_classes": [DataClass.PHI, DataClass.PII]},
        "cartesia": {"baa_available": True, "data_classes": [DataClass.PHI, DataClass.PII]},
        "vllm_sovereign": {"baa_available": True, "data_classes": [DataClass.PHI, DataClass.PII]},
    }

    @classmethod
    def is_allowed(
        cls,
        vendor_name: str,
        data_class: DataClass,
        policy: CompliancePolicy,
        has_signed_baa: bool = False,
    ) -> bool:
        """Return True if transmitting data_class to vendor is allowed under compliance policy."""
        vendor_id = vendor_name.lower()
        subprocessor = cls._subprocessors.get(vendor_id)

        # If policy requires BAA for PHI/PII data classes
        if policy.require_baa and data_class in (DataClass.PHI, DataClass.PII):
            if not subprocessor or not subprocessor.get("baa_available", False) or not has_signed_baa:
                return False

        if not policy.allow_cloud_llm and vendor_id == "groq" and data_class == DataClass.PHI:
            return False

        return True
