"""Phase 16: Text Normalization and Pronunciation."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def normalizer_module():
    try:
        from core.language import normalizer  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 16 implementation pending: {exc}")
    return normalizer


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_16_text_normalization_and_pronunciation_layer.md"
    )
    assert plan.is_file()


def test_markdown_stripped(normalizer_module) -> None:
    TextNormalizer = normalizer_module.TextNormalizer
    result = TextNormalizer().normalize("**hello** world", language="en")
    assert "**" not in result.text
