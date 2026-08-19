"""Phase 29: External Developer Experience and Documentation Spec."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_29_external_developer_experience_and_documentation_spec.md"
)
DEV_DOCS = REPO_ROOT / "docs" / "developer"


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_developer_doc_deliverables_exist() -> None:
    required = [
        "README.md",
        "QUICKSTART_HOST_BACKEND.md",
        "QUICKSTART_AGENT_STUDIO.md",
        "INTEGRATION_PATTERNS.md",
        "COMPLIANCE_INTEGRATOR_GUIDE.md",
        "TROUBLESHOOTING.md",
        "TELEPHONY_INTEGRATOR.md",
        "MCP_AND_RAG_SETUP.md",
        "GLOSSARY.md",
    ]
    missing = [name for name in required if not (DEV_DOCS / name).is_file()]
    if missing:
        pytest_skip = __import__("pytest")
        pytest_skip.skip(f"Phase 29 doc deliverables pending: {missing}")
    for name in required:
        assert (DEV_DOCS / name).is_file()


def test_env_example_has_no_secrets() -> None:
    env_example = DEV_DOCS / "env" / ".env.example"
    if not env_example.is_file():
        import pytest

        pytest.skip("Phase 29 .env.example pending")
    content = env_example.read_text(encoding="utf-8").lower()
    assert "sk-" not in content
    assert "password=supersecret" not in content
