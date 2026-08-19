"""Phase 15: Multilingual Language Registry and Routing."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def language_module():
    try:
        from core import language  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 15 implementation pending: {exc}")
    return language


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_15_multilingual_language_registry_and_routing_policies.md"
    )
    assert plan.is_file()


def test_phase_11_redaction_checkpoint_documented() -> None:
    readme = REPO_ROOT / "core" / "language" / "profiles" / "README.md"
    limitations = REPO_ROOT / "core" / "compliance" / "redaction_limitations.md"
    if not readme.is_file():
        pytest.skip("Language profiles README not scaffolded yet")
    content = readme.read_text(encoding="utf-8")
    assert "Phase 11" in content or "redaction" in content.lower()
    if limitations.is_file():
        assert "Urdu" in limitations.read_text(encoding="utf-8") or "Arabic" in limitations.read_text(
            encoding="utf-8"
        )


def test_router_three_word_immediate_switch(language_module) -> None:
    router = language_module.router.LanguageRouter()
    transcript = type("T", (), {"text": "one two three four", "language": "ur"})()
    result = router.route(transcript, current_language="en")
    assert result == "ur"
