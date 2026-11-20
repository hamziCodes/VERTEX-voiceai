from __future__ import annotations

import pytest

from core.language.streaming_chunker import SpeechChunk, StreamingSpeechChunker


@pytest.mark.parametrize(
    ("language", "text", "first_words"),
    [
        ("en", "Hello there this response has no punctuation", 3),
        ("ur", "آپ کیسے ہیں میں آپ کی مدد کر سکتا ہوں", 2),
        ("ar", "كيف حالك يمكنني مساعدتك اليوم", 2),
    ],
)
def test_first_safe_chunk_uses_language_profile_word_target(
    language: str, text: str, first_words: int
) -> None:
    chunker = StreamingSpeechChunker.for_language(language, max_words=5)
    emitted: list[SpeechChunk] = []
    for token in (word + " " for word in text.split()):
        emitted.extend(chunker.push(token))

    assert emitted
    assert len(emitted[0].text.split()) == first_words
    assert emitted[0].is_first is True


def test_streaming_chunker_preserves_text_across_arbitrary_deltas() -> None:
    text = "Hello there. How are you today? I am ready"
    chunker = StreamingSpeechChunker(first_chunk_words=2, min_chunk_words=3)
    chunks: list[SpeechChunk] = []
    for delta in ("Hel", "lo ", "there. How", " are you ", "today? I am", " ready"):
        chunks.extend(chunker.push(delta))
    chunks.extend(chunker.flush())

    assert " ".join(chunk.text for chunk in chunks) == text
    assert [chunk.text for chunk in chunks] == [
        "Hello there.",
        "How are you today?",
        "I am ready",
    ]
    assert chunks[-1].is_final is True


def test_punctuation_free_text_is_bounded_and_flush_is_idempotent() -> None:
    chunker = StreamingSpeechChunker(
        first_chunk_words=2, min_chunk_words=3, max_words=4
    )
    emitted = chunker.push("one two three four five six seven eight nine ")
    emitted.extend(chunker.flush())

    assert [len(chunk.text.split()) for chunk in emitted] == [2, 4, 3]
    assert chunker.flush() == []


def test_runtime_first_word_override_takes_precedence_over_profile() -> None:
    chunker = StreamingSpeechChunker.for_language(
        "en",
        first_chunk_words_override=2,
    )

    chunks = chunker.push("one two ")

    assert [chunk.text for chunk in chunks] == ["one two"]


def test_urdu_and_arabic_sentence_terminators_split_stable_chunks() -> None:
    chunker = StreamingSpeechChunker(first_chunk_words=2, min_chunk_words=2)

    chunks = chunker.push("ایک دو تین چار۔ پانچ چھ سات؟ ")

    assert [chunk.text for chunk in chunks] == [
        "ایک دو",
        "تین چار۔",
        "پانچ چھ سات؟",
    ]
