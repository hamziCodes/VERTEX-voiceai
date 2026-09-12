"""Phase 27: Self-Serve Agent Builder UX Flow Spec Test Suite."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_27_self_serve_agent_builder_ux_flow_spec.md"
)
DOCS_DIR = REPO_ROOT / "docs" / "agent-studio"
STUDIO_DIR = REPO_ROOT / "agent-studio"


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_standalone_spa_and_no_outbound_ui() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "standalone" in text.lower()
    assert "sandbox" in text.lower() or "non-metered" in text.lower()
    assert "outbound" in text.lower()
    assert "None — fully deterministic" in text


def test_all_deliverable_artifacts_exist() -> None:
    expected_files = [
        DOCS_DIR / "WIREFLOWS.md",
        DOCS_DIR / "SCREEN_INVENTORY.md",
        DOCS_DIR / "COMPONENT_CONTRACTS.md",
        DOCS_DIR / "ACCEPTANCE_CRITERIA.md",
        DOCS_DIR / "HUMAN_REVIEW_QUEUE_UX.md",
        DOCS_DIR / "RTL_BUILDER_NOTES.md",
        DOCS_DIR / "TEST_CALL_BILLING.md",
        DOCS_DIR / "OUTBOUND_UI_DEFERRED.md",
        STUDIO_DIR / "README.md",
    ]
    for p in expected_files:
        assert p.is_file(), f"Missing required Phase 27 deliverable: {p}"


def test_file_8_section_5_checklist_mapped_in_screen_inventory() -> None:
    inventory = (DOCS_DIR / "SCREEN_INVENTORY.md").read_text(encoding="utf-8")
    # All major File 8 §5 features:
    features = [
        "SCR-01",  # Agent list / directory
        "SCR-02",  # Template picker
        "SCR-03",  # Persona editor
        "SCR-04",  # Languages & vocal timbre
        "SCR-05",  # Provider priority chains
        "SCR-06",  # Tools & MCP
        "SCR-07",  # Knowledge bases
        "SCR-08",  # Structured extraction
        "SCR-09",  # Telephony
        "SCR-10",  # Compliance
        "SCR-11",  # Test sandbox
        "SCR-12",  # Human review queue
        "SCR-13",  # Live monitor
    ]
    for feat in features:
        assert feat in inventory, f"Missing feature mapping for {feat} in SCREEN_INVENTORY.md"


def test_wizard_steps_reference_phase_26_api_endpoints() -> None:
    contracts = (DOCS_DIR / "COMPONENT_CONTRACTS.md").read_text(encoding="utf-8")
    wireflows = (DOCS_DIR / "WIREFLOWS.md").read_text(encoding="utf-8")
    combined = contracts + "\n" + wireflows

    # Phase 26 endpoints:
    assert "/v1/agents" in combined
    assert "autosave" in combined.lower()
    assert "publish" in combined.lower()
    assert "pin" in combined.lower()


def test_human_review_queue_flow_documented() -> None:
    hrq = (DOCS_DIR / "HUMAN_REVIEW_QUEUE_UX.md").read_text(encoding="utf-8")
    assert "Human Review Queue" in hrq
    assert "redacted" in hrq.lower()
    assert "confidence" in hrq.lower()
    assert "webhook" in hrq.lower()


def test_rtl_validation_ux_references_phase_15_rule() -> None:
    rtl_notes = (DOCS_DIR / "RTL_BUILDER_NOTES.md").read_text(encoding="utf-8")
    assert "Arabic" in rtl_notes or "arabic" in rtl_notes.lower()
    assert "RTL" in rtl_notes
    assert "voice" in rtl_notes.lower()
    assert "15" in rtl_notes


def test_acceptance_criteria_covers_publish_gate_and_sandbox_billing() -> None:
    ac = (DOCS_DIR / "ACCEPTANCE_CRITERIA.md").read_text(encoding="utf-8")
    assert "Publish" in ac
    assert "INSUFFICIENT_PROVIDER_ROUTES" in ac
    assert "ARABIC_RTL_VOICE_REQUIRED" in ac
    assert "HIPAA_BAA_REQUIRED" in ac
    assert "Sandbox" in ac or "sandbox" in ac
    assert "30" in ac


def test_outbound_explicitly_excluded() -> None:
    outbound_doc = (DOCS_DIR / "OUTBOUND_UI_DEFERRED.md").read_text(encoding="utf-8")
    assert "Outbound" in outbound_doc
    assert "19" in outbound_doc
    assert "inbound" in outbound_doc.lower()


def test_standalone_spa_documented() -> None:
    studio_readme = (STUDIO_DIR / "README.md").read_text(encoding="utf-8")
    assert "Standalone SPA" in studio_readme or "standalone" in studio_readme.lower()
    assert "React" in studio_readme
    assert "TypeScript" in studio_readme
