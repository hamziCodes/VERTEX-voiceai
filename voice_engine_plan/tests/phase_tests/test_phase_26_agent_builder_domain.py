"""Phase 26: Self-Serve Agent Builder Domain Model."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_26_self_serve_agent_builder_domain_model.md"
)


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_autosave_and_config_pin_documented() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "autosave" in text.lower()
    assert "pin" in text.lower()
    assert "[LATER]" in text
    assert "None — fully deterministic" in text
