"""Phase 33: End-to-End Validation Harness and Test Matrix."""

from __future__ import annotations

from pathlib import Path
import pytest

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
    assert TEST_MATRIX.is_file(), "TEST_MATRIX.md missing"
    text = TEST_MATRIX.read_text(encoding="utf-8")
    for phase in range(36):
        token = f"| {phase:02d} " if phase < 10 else f"| {phase} "
        alt = f"Phase {phase:02d}" if phase < 10 else f"Phase {phase}"
        assert token in text or alt in text or f"| {phase} " in text, f"TEST_MATRIX missing phase {phase}"


def test_matrix_links_to_phase_tests_paths() -> None:
    text = TEST_MATRIX.read_text(encoding="utf-8")
    assert "voice_engine_plan/tests/phase_tests/" in text


def test_e2e_harness_importable() -> None:
    from tests.e2e.harness import E2EHarness, HarnessConfig
    harness = E2EHarness(HarnessConfig(scenario="sovereign_conversation"))
    assert harness is not None


def test_each_e2e_scenario_file_exists() -> None:
    scenarios_dir = REPO_ROOT / "tests" / "e2e" / "scenarios"
    expected_scenarios = [
        "test_sovereign_conversation.py",
        "test_barge_in_e2e.py",
        "test_failover_e2e.py",
        "test_telephony_inbound_e2e.py",
        "test_post_call_e2e.py",
    ]
    for scenario in expected_scenarios:
        assert (scenarios_dir / scenario).is_file(), f"Missing scenario file {scenario}"


def test_inherited_patterns_cites_habiba_and_multilingual() -> None:
    doc = (REPO_ROOT / "docs" / "testing" / "INHERITED_PATTERNS.md").read_text(encoding="utf-8")
    assert "habiba" in doc.lower()
    assert "multilingual" in doc.lower()


def test_synthetic_audio_fixtures_present() -> None:
    audio_dir = REPO_ROOT / "tests" / "e2e" / "fixtures" / "audio"
    assert audio_dir.is_dir()
    assert (audio_dir / "en_sample.pcm").is_file()
    assert (audio_dir / "ur_sample.pcm").is_file()


def test_e2e_nightly_workflow_stub_exists() -> None:
    workflow = REPO_ROOT / ".github" / "workflows" / "e2e-nightly.yml"
    assert workflow.is_file()


@pytest.mark.asyncio
async def test_harness_smoke_mock_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.delenv("RUN_LIVE_PROVIDERS", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    from tests.e2e.harness import E2EHarness, HarnessConfig

    harness = E2EHarness(HarnessConfig(scenario="sovereign_conversation"))
    result = await harness.run_scenario_async("sovereign_conversation")
    assert result.passed is True

