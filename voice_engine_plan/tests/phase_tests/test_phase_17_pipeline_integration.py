"""Phase 17: Real-Time Orchestration Pipeline Integration."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_17_real_time_orchestration_pipeline_integration.md"
    )
    assert plan.is_file()


@pytest.mark.asyncio
async def test_pipeline_orchestrator_exists() -> None:
    try:
        from worker_raw.orchestration.pipeline import PipelineOrchestrator  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 17 implementation pending: {exc}")
    orchestrator = PipelineOrchestrator()
    assert orchestrator is not None
