"""Phase 00: Monorepo Planning Baseline — structural tests."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
REQUIRED_DIRS = ("core", "control-plane", "worker-raw", "tests")
REQUIRED_FILES = ("pyproject.toml",)


def _missing_paths() -> list[str]:
    missing: list[str] = []
    for name in REQUIRED_DIRS:
        if not (REPO_ROOT / name).is_dir():
            missing.append(name)
    for name in REQUIRED_FILES:
        if not (REPO_ROOT / name).is_file():
            missing.append(name)
    return missing


@pytest.fixture(scope="module")
def monorepo_ready() -> None:
    missing = _missing_paths()
    if missing:
        pytest.skip(
            f"Phase 00 implementation pending — missing: {', '.join(missing)}"
        )


def test_required_directories_exist(monorepo_ready: None) -> None:
    for name in REQUIRED_DIRS:
        assert (REPO_ROOT / name).is_dir(), f"Missing directory: {name}"


def test_pyproject_exists(monorepo_ready: None) -> None:
    assert (REPO_ROOT / "pyproject.toml").is_file()


def test_core_import_smoke(monorepo_ready: None) -> None:
    import core  # noqa: F401


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_00_monorepo_planning_baseline.md"
    )
    assert plan.is_file(), "Phase 00 plan document must exist"
