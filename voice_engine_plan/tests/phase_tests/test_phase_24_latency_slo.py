"""Phase 24: Latency Budget Enforcement and SLO Policies."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_24_latency_budget_enforcement_and_slo_policies.md"
)


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_warn_only_and_playback_documented() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "warn-only" in text.lower() or "warn only" in text.lower()
    assert "playback_started" in text
    assert "[LATER]" in text
    assert "None — fully deterministic" in text
