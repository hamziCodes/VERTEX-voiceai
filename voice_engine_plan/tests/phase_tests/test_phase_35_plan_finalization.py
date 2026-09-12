"""Phase 35: Stage-2 Plan Folder Finalization."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN_DIR = REPO_ROOT / "voice_engine_plan" / "implementation_plan"
VERIFY = REPO_ROOT / "voice_engine_plan" / "scripts" / "verify_plan_integrity.py"


def test_phase_plan_artifact_exists() -> None:
    plan = PLAN_DIR / "phase_35_stage_2_plan_folder_finalization.md"
    assert plan.is_file()


def test_readme_indexes_all_phases() -> None:
    readme = REPO_ROOT / "voice_engine_plan" / "README.md"
    assert readme.is_file()
    text = readme.read_text(encoding="utf-8")
    for phase in range(36):
        assert f"Phase {phase:02d}" in text or f"| {phase:02d} " in text


def test_portability_checklist_complete() -> None:
    checklist = REPO_ROOT / "voice_engine_plan" / "PORTABILITY_CHECKLIST.md"
    assert checklist.is_file()
    content = checklist.read_text(encoding="utf-8")
    assert "- [x]" in content


def test_verify_plan_integrity_passes() -> None:
    assert VERIFY.is_file()
    result = subprocess.run(
        [sys.executable, str(VERIFY)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_execution_tracker_has_36_rows() -> None:
    import re
    tracker = PLAN_DIR / "EXECUTION_TRACKER.md"
    assert tracker.is_file()
    text = tracker.read_text(encoding="utf-8")
    lines = [l for l in text.splitlines() if re.match(r"^\| \d{2} \|", l)]
    assert len(lines) == 36, f"Expected 36 phase data rows in EXECUTION_TRACKER, found {len(lines)}"


def test_test_tracker_matches_existing_test_files() -> None:
    test_tracker = REPO_ROOT / "voice_engine_plan" / "tests" / "phase_tests" / "TEST_TRACKER.md"
    assert test_tracker.is_file()
    text = test_tracker.read_text(encoding="utf-8")
    tests_dir = REPO_ROOT / "voice_engine_plan" / "tests" / "phase_tests"
    for phase in range(36):
        expected_file = f"test_phase_{phase:02d}_"
        matching = [f.name for f in tests_dir.glob(f"test_phase_{phase:02d}_*.py")]
        assert len(matching) == 1, f"Missing test file for phase {phase}"
        assert matching[0] in text, f"TEST_TRACKER missing {matching[0]}"


def test_no_phase_file_missing_section_6_or_7() -> None:
    for phase in range(36):
        matching = list(PLAN_DIR.glob(f"phase_{phase:02d}_*.md"))
        assert len(matching) == 1, f"Missing phase file for phase {phase}"
        content = matching[0].read_text(encoding="utf-8")
        assert "## 6." in content or "Ambiguity Flags" in content, f"Phase {phase} missing Section 6"
        assert "## 7." in content or "Test Spec" in content, f"Phase {phase} missing Section 7"


def test_changelog_plan_has_entry() -> None:
    changelog = REPO_ROOT / "voice_engine_plan" / "CHANGELOG_PLAN.md"
    assert changelog.is_file()
    text = changelog.read_text(encoding="utf-8")
    assert "# Voice Engine Plan" in text

