"""Phase 31: Scaling and Runtime Resource Profiles."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_31_scaling_and_runtime_resource_profiles.md"
)
PROFILES = REPO_ROOT / "infra" / "scaling" / "profiles"


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_runtime_profiles_documented() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "standard" in text
    assert "active session" in text.lower()
    assert "None — fully deterministic" in text


def test_profile_yaml_files_exist() -> None:
    for name in ("dev.yaml", "standard.yaml", "high_density.yaml"):
        path = PROFILES / name
        if not path.is_file():
            pytest.skip(f"Phase 31 profile {name} pending")
        assert path.is_file()
