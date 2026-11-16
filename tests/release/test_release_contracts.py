"""Phase 15: published contracts and image recipes stay tied to the code."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKER_DIR = REPO_ROOT / "infra" / "docker"
SERVICE_IMAGES = {
    "control-plane.Dockerfile": "control_plane.app",
    "worker-raw.Dockerfile": "worker_raw.main",
    "telephony-gateway.Dockerfile": "telephony_gateway.main",
    "worker-managed.Dockerfile": "worker_managed.main",
    "worker-jobs.Dockerfile": "worker_jobs.main",
}
FIRST_PARTY = (
    "core",
    "control_plane",
    "post_call",
    "telephony_gateway",
    "worker_raw",
    "worker_jobs",
    "worker_managed",
)


def test_openapi_yaml_is_the_runtime_schema() -> None:
    from control_plane.app import app

    published = yaml.safe_load((REPO_ROOT / "openapi.yaml").read_text(encoding="utf-8"))
    assert published == app.openapi(), (
        "openapi.yaml drifted: python scripts/release/export_openapi.py"
    )


def test_openapi_json_is_served_from_the_app() -> None:
    from fastapi.testclient import TestClient

    from control_plane.app import app

    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["paths"].keys() == app.openapi()["paths"].keys()


@pytest.mark.parametrize("dockerfile,module", sorted(SERVICE_IMAGES.items()))
def test_service_image_recipe(dockerfile: str, module: str) -> None:
    text = (DOCKER_DIR / dockerfile).read_text(encoding="utf-8")
    assert "pip install --no-deps --require-hashes -r /app/requirements/runtime.txt" in text
    # No hand-picked dependency lists: the lock export is the only source.
    assert not re.search(r'pip install[^\n]*"\w', text)
    for package in FIRST_PARTY:
        assert f"COPY {package}/ /app/{package}/" in text
    for asset in ("infra/scaling/", "infra/db/", "examples/web-client/", "openapi.yaml"):
        assert asset in text
    assert "core.vad.download_silero --check" in text
    assert f'python -c "import {module}"' in text
    assert "USER wavia" in text


def test_dockerignore_keeps_secrets_out_and_runtime_assets_in() -> None:
    rules = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    for required in (".env", ".env.*", "!.env.example", "API KEYS*", ".git", "hamza_local",
                     "legacy_codebases", "tests"):
        assert required in rules
    for kept in ("infra", "requirements", "openapi.yaml", "README.md", "uv.lock", "examples"):
        assert kept not in rules


def test_runtime_requirements_are_hash_pinned() -> None:
    lines = (REPO_ROOT / "requirements" / "runtime.txt").read_text(encoding="utf-8")
    pins = re.findall(r"^([A-Za-z0-9_.-]+)==\S+", lines, flags=re.MULTILINE)
    assert pins, "no pinned requirements"
    assert lines.count("--hash=sha256:") >= len(pins)
    names = {p.lower() for p in pins}
    for needed in ("psycopg-pool", "python-multipart", "tokenizers", "boto3", "onnxruntime"):
        assert needed in names
    assert "torch" not in names


def test_runtime_requirements_match_uv_lock() -> None:
    if shutil.which("uv") is None:
        try:
            import uv  # noqa: F401
        except ImportError:
            pytest.skip("uv not available")
    result = subprocess.run(
        ["bash", "scripts/release/export_requirements.sh", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 127 or "python: No module named uv" in result.stderr:
        pytest.skip("uv not runnable from bash here")
    assert result.returncode == 0, result.stderr


def test_silero_model_is_the_pinned_release() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from core.vad.download_silero import is_valid

    assert is_valid()
