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
    for name in required:
        assert (DEV_DOCS / name).is_file(), f"Missing required doc deliverable: {name}"


def test_readme_links_every_guide() -> None:
    readme = (DEV_DOCS / "README.md").read_text(encoding="utf-8")
    guides = [
        "QUICKSTART_HOST_BACKEND.md",
        "QUICKSTART_AGENT_STUDIO.md",
        "INTEGRATION_PATTERNS.md",
        "COMPLIANCE_INTEGRATOR_GUIDE.md",
        "TROUBLESHOOTING.md",
        "TELEPHONY_INTEGRATOR.md",
        "MCP_AND_RAG_SETUP.md",
        "GLOSSARY.md",
    ]
    for guide in guides:
        assert guide in readme, f"README.md missing link to {guide}"


def test_quickstart_references_phase_28_and_examples() -> None:
    quickstart = (DEV_DOCS / "QUICKSTART_HOST_BACKEND.md").read_text(encoding="utf-8")
    assert "HOST_BACKEND_MINT_GUIDE.md" in quickstart or "Phase 28" in quickstart
    assert "examples/host-backend" in quickstart


def test_compliance_guide_mentions_hipaa_baa_gate() -> None:
    compliance = (DEV_DOCS / "COMPLIANCE_INTEGRATOR_GUIDE.md").read_text(encoding="utf-8")
    assert "HIPAA" in compliance
    assert "BAA" in compliance
    assert "gate" in compliance.lower() or "blocked" in compliance.lower()


def test_troubleshooting_lists_at_least_10_error_codes() -> None:
    troubleshooting = (DEV_DOCS / "TROUBLESHOOTING.md").read_text(encoding="utf-8")
    from core.errors.codes import UCVEErrorCode

    found_codes = [code.value for code in UCVEErrorCode if code.value in troubleshooting]
    assert len(found_codes) >= 10, f"Troubleshooting doc only lists {len(found_codes)} codes: {found_codes}"


def test_telephony_guide_states_outbound_later() -> None:
    telephony = (DEV_DOCS / "TELEPHONY_INTEGRATOR.md").read_text(encoding="utf-8")
    assert "outbound" in telephony.lower()
    assert "[LATER]" in telephony or "later" in telephony.lower()


def test_glossary_defines_core_terms() -> None:
    glossary = (DEV_DOCS / "GLOSSARY.md").read_text(encoding="utf-8")
    for term in ["mint", "DATA frame", "caller_id"]:
        assert term.lower() in glossary.lower(), f"Glossary missing definition for: {term}"


def test_env_example_has_no_secrets() -> None:
    env_example = DEV_DOCS / "env" / ".env.example"
    assert env_example.is_file()
    content = env_example.read_text(encoding="utf-8").lower()
    assert "sk-" not in content
    assert "password=supersecret" not in content
    assert "apikey" not in content or "replace" in content

