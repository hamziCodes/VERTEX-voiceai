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
    infra_docker = REPO_ROOT / "infra" / "docker"
    docs_deploy = REPO_ROOT / "docs" / "deploy"
    ci_workflow = REPO_ROOT / ".github" / "workflows" / "ci.yml"

    required_docker_files = [
        "docker-compose.yml",
        "docker-compose.staging.yml",
        "control-plane.Dockerfile",
        "worker-raw.Dockerfile",
        "telephony-gateway.Dockerfile",
        "worker-managed.Dockerfile",
        ".env.example",
    ]
    for filename in required_docker_files:
        assert (infra_docker / filename).is_file(), f"Missing docker artifact: {filename}"

    required_doc_files = [
        "ENVIRONMENT_MATRIX.md",
        "COMPOSE_QUICKSTART.md",
        "KUBERNETES.md",
    ]
    for filename in required_doc_files:
        assert (docs_deploy / filename).is_file(), f"Missing deploy doc: {filename}"

    assert ci_workflow.is_file(), "Missing CI workflow file"


def test_compose_services_defined() -> None:
    compose_text = (REPO_ROOT / "infra" / "docker" / "docker-compose.yml").read_text(encoding="utf-8")
    for service in ["postgres:", "redis:", "control-plane:", "worker-raw:"]:
        assert service in compose_text, f"Missing service {service} in docker-compose.yml"


def test_worker_raw_installs_the_locked_onnx_runtime_not_torch() -> None:
    # Phase 15: the worker runs Silero VAD on onnxruntime; torch was only a
    # fallback when onnxruntime is absent and added gigabytes to the image.
    # Every image installs exactly the hash-pinned export of uv.lock.
    worker_df = (REPO_ROOT / "infra" / "docker" / "worker-raw.Dockerfile").read_text(encoding="utf-8")
    assert "--require-hashes -r /app/requirements/runtime.txt" in worker_df
    runtime = (REPO_ROOT / "requirements" / "runtime.txt").read_text(encoding="utf-8").lower()
    assert "\nonnxruntime==" in runtime and "\nnumpy==" in runtime
    assert "\ntorch==" not in runtime


def test_environment_matrix_covers_tiers() -> None:
    matrix_text = (REPO_ROOT / "docs" / "deploy" / "ENVIRONMENT_MATRIX.md").read_text(encoding="utf-8")
    for tier in ["dev", "staging", "prod"]:
        assert tier in matrix_text.lower(), f"ENVIRONMENT_MATRIX.md missing tier: {tier}"


def test_compose_quickstart_references_ws_and_sovereign() -> None:
    quickstart = (REPO_ROOT / "docs" / "deploy" / "COMPOSE_QUICKSTART.md").read_text(encoding="utf-8")
    assert "sovereign" in quickstart.lower() or "ws" in quickstart.lower()
    assert "/health" in quickstart


def test_livekit_is_optional_not_default() -> None:
    compose_text = (REPO_ROOT / "infra" / "docker" / "docker-compose.yml").read_text(encoding="utf-8")
    assert 'UCVE_ENABLE_LIVEKIT: "false"' in compose_text or "UCVE_ENABLE_LIVEKIT=false" in compose_text

