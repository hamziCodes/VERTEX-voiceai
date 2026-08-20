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
    assert result.text == "hello world"


def test_numerals_converted_to_spoken_form(normalizer_module) -> None:
    TextNormalizer = normalizer_module.TextNormalizer

    res_en = TextNormalizer().normalize("Order 1234", language="en")
    assert "one thousand two hundred thirty four" in res_en.text

    res_ur = TextNormalizer().normalize("1234", language="ur")
    assert "ایک ہزار دو سو چونتیس" in res_ur.text


def test_pronunciation_lexicon_replacement(normalizer_module) -> None:
    TextNormalizer = normalizer_module.TextNormalizer
    lexicon = {"Vertex": "Ver-teks", "VoiceAI": "Voice A I"}
    result = TextNormalizer().normalize("Welcome to Vertex VoiceAI", language="en", lexicon=lexicon)
    assert "Ver-teks" in result.text
    assert "Voice A I" in result.text


def test_latin_english_in_urdu_passthrough_no_regen(normalizer_module) -> None:
    TextNormalizer = normalizer_module.TextNormalizer
    # Latin English words (AI, Order) in Urdu context pass through without regeneration
    result = TextNormalizer().normalize("Aapka Order AI status active hai", language="ur")
    assert result.needs_regeneration is False


def test_sentence_chunker_first_chunk_words_and_subsequent() -> None:
    from core.language.chunker import SentenceChunker

    chunker = SentenceChunker()
    text = "Hello there. How are you today? I am fine."
    chunks = chunker.chunk(text, first_chunk_words=2, min_chunk_words=3)

    assert len(chunks) >= 2
    # First chunk has exactly 2 words for TTFT optimization
    assert chunks[0] == "Hello there."


def test_regeneration_retry_limit_and_fallback_handoff() -> None:
    from core.language.regeneration import RegenerationManager

    mgr = RegenerationManager(max_retries=2)
    assert mgr.should_retry(0) is True
    assert mgr.should_retry(1) is True
    assert mgr.should_retry(2) is False  # 3rd attempt fails, escalate to failover

    triggered = mgr.handle_failed_regeneration("session-123", attempt=2)
    assert triggered is True

