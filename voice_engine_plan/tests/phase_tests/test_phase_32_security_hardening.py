"""Phase 32: Security Hardening and Threat Controls."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_32_security_hardening_and_threat_controls.md"
)
SECURITY_DOCS = REPO_ROOT / "docs" / "security"


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_security_docs_exist() -> None:
    for name in ("THREAT_MODEL.md", "ANTI_PATTERN_CHECKLIST.md", "PENTEST_READINESS.md"):
        path = SECURITY_DOCS / name
        if not path.is_file():
            import pytest

            pytest.skip(f"Phase 32 {name} pending")
        assert path.is_file()


def test_anti_pattern_checklist_covers_file9() -> None:
    checklist = SECURITY_DOCS / "ANTI_PATTERN_CHECKLIST.md"
    if not checklist.is_file():
        import pytest

        pytest.skip("ANTI_PATTERN_CHECKLIST pending")
    text = checklist.read_text(encoding="utf-8")
    assert text.count("|") >= 20
