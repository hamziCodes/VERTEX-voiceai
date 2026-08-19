"""Phase 28: SDK/API Surface and Versioning Strategy."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_28_sdk_api_surface_and_versioning_strategy.md"
)


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_flutter_roadmap_livekit_separate_self_hosted_docs() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "FLUTTER_ROADMAP" in text or "roadmap" in text.lower()
    assert "voice-livekit" in text or "@ucve/voice-livekit" in text
    assert "/docs" in text
    assert "None — fully deterministic" in text
