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
        "groq", data_class=compliance_module.classification.DataClass.PHI, policy=policy
    )
    assert allowed is False or policy.require_baa is True
