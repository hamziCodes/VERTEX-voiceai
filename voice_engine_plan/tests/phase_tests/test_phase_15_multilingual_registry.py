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


def test_router_short_phrase_requires_consecutive(language_module) -> None:
    router = language_module.router.LanguageRouter()

    # 1st short turn (< 3 words) -> stays en
    t1 = type("T", (), {"text": "haan ji", "language": "ur"})()
    res1 = router.route(t1, current_language="en")
    assert res1 == "en"

    # 2nd consecutive short turn in ur -> switches to ur
    t2 = type("T", (), {"text": "kya hai", "language": "ur"})()
    res2 = router.route(t2, current_language="en")
    assert res2 == "ur"


def test_unsupported_language_keeps_current(language_module) -> None:
    router = language_module.router.LanguageRouter()
    transcript = type("T", (), {"text": "bonjour le monde", "language": "fr"})()
    result = router.route(transcript, current_language="en")
    assert result == "en"


def test_ur_default_cs_false_and_ar_ms_measure_only(language_module) -> None:
    reg = language_module.registry.LanguageRegistry.load_defaults()

    ur_prof = reg.get_profile("ur")
    assert ur_prof is not None
    assert ur_prof.code_switching_default is False

    ar_prof = reg.get_profile("ar")
    assert ar_prof is not None
    assert ar_prof.cs_measure_only is True

    ms_prof = reg.get_profile("ms")
    assert ms_prof is not None
    assert ms_prof.cs_measure_only is True


def test_rtl_voice_validation_rejects_invalid_ar_voice(language_module) -> None:
    reg = language_module.registry.LanguageRegistry.load_defaults()

    # Valid RTL voice passes
    assert reg.validate_voice_for_publish("ar", "ar-multilingual-1") is True

    # Invalid voice for Arabic fails publish gate
    assert reg.validate_voice_for_publish("ar", "invalid-english-voice") is False


def test_adding_a_language_doc_exists_and_has_4_steps() -> None:
    doc = REPO_ROOT / "core" / "language" / "profiles" / "ADDING_A_LANGUAGE.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "Step 1" in text and "Step 4" in text

