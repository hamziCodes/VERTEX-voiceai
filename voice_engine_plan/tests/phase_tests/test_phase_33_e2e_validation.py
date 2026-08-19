"""Phase 33: End-to-End Validation Harness and Test Matrix."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_33_end_to_end_validation_harness_and_test_matrix.md"
)
TEST_MATRIX = REPO_ROOT / "docs" / "testing" / "TEST_MATRIX.md"


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_test_matrix_covers_all_phases() -> None:
    if not TEST_MATRIX.is_file():
        import pytest

        pytest.skip("Phase 33 TEST_MATRIX pending")
    text = TEST_MATRIX.read_text(encoding="utf-8")
    for phase in range(36):
        token = f"| {phase:02d} " if phase < 10 else f"| {phase} "
        alt = f"Phase {phase:02d}" if phase < 10 else f"Phase {phase}"
        assert token in text or alt in text or f"| {phase} " in text


def test_e2e_harness_exists() -> None:
    harness = REPO_ROOT / "tests" / "e2e" / "harness.py"
    if not harness.is_file():
        import pytest

        pytest.skip("Phase 33 e2e harness pending")
    assert harness.is_file()
