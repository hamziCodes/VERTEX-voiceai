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
