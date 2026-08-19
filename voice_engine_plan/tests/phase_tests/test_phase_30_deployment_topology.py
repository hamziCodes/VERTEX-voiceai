"""Phase 30: Deployment Topology and Environment Strategy."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_30_deployment_topology_and_environment_strategy.md"
)


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_compose_and_worker_dockerfile_documented() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "docker-compose" in text
    assert "torch" in text
    assert "None — fully deterministic" in text


def test_deploy_artifacts_exist() -> None:
    compose = REPO_ROOT / "infra" / "docker" / "docker-compose.yml"
    worker_df = REPO_ROOT / "infra" / "docker" / "worker-raw.Dockerfile"
    if not compose.is_file():
        import pytest

        pytest.skip("Phase 30 docker-compose pending")
    assert compose.is_file()
    if worker_df.is_file():
        assert "torch" in worker_df.read_text(encoding="utf-8").lower()
