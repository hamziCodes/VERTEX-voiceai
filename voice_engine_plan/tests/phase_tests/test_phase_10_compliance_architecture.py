"""Phase 10: Compliance Architecture and Data Classification."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def compliance_module():
    try:
        from core import compliance  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 10 implementation pending: {exc}")
    return compliance


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_10_compliance_architecture_and_data_classification_model.md"
    )
    assert plan.is_file()


def test_every_artifact_type_classified(compliance_module) -> None:
    registry = compliance_module.classification.DataClassificationRegistry.load_defaults()
    for artifact in compliance_module.classification.ArtifactType:
        assert registry.has_artifact(artifact)


def test_hipaa_blocks_non_baa_subprocessor(compliance_module) -> None:
    tiers = compliance_module.tiers
    policy = tiers.policy_for(tiers.ComplianceTier.HIPAA)
    allowed = compliance_module.classification.SubprocessorRegistry.is_allowed(
        "groq", data_class=compliance_module.classification.DataClass.PHI, policy=policy, has_signed_baa=False
    )
    assert allowed is False


def test_unknown_field_defaults_to_pii(compliance_module) -> None:
    registry = compliance_module.classification.DataClassificationRegistry.load_defaults()
    dclass = registry.classify(compliance_module.classification.ArtifactType.PROVIDER_PAYLOAD, field_path="unknown_custom_field")
    assert dclass in (compliance_module.classification.DataClass.PII, compliance_module.classification.DataClass.PHI)


def test_tenant_override_merges_correctly(compliance_module) -> None:
    loader = compliance_module.tenant_profile.TenantComplianceProfileLoader
    policy = loader.load_effective_policy(
        tier=compliance_module.tiers.ComplianceTier.STANDARD,
        policy_overrides={"max_retention_days": 14},
    )
    assert policy.max_retention_days == 14
    assert policy.allow_cloud_llm is True


def test_hipaa_cloud_llm_gate_with_baa_timestamp(compliance_module) -> None:
    import datetime
    loader = compliance_module.tenant_profile.TenantComplianceProfileLoader

    # Without BAA timestamp -> cloud LLM blocked
    policy_no_baa = loader.load_effective_policy(
        tier=compliance_module.tiers.ComplianceTier.HIPAA,
        hipaa_baa_acknowledged_at=None,
    )
    assert policy_no_baa.allow_cloud_llm is False

    # With BAA timestamp -> cloud LLM allowed
    policy_baa = loader.load_effective_policy(
        tier=compliance_module.tiers.ComplianceTier.HIPAA,
        hipaa_baa_acknowledged_at=datetime.datetime.now(datetime.timezone.utc),
    )
    assert policy_baa.allow_cloud_llm is True

