"""Phase 27: Self-Serve Agent Builder UX Flow Spec."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_27_self_serve_agent_builder_ux_flow_spec.md"
)


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_standalone_spa_and_no_outbound_ui() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "standalone" in text.lower()
    assert "sandbox" in text.lower() or "non-metered" in text.lower()
    assert "outbound" in text.lower()
    assert "None — fully deterministic" in text
