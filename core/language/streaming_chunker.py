"""Incremental multilingual text chunking for low-latency speech synthesis."""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.language.registry import LanguageRegistry

_WORD_RE = re.compile(r"\S+")
_SENTENCE_RE = re.compile(r".*?[.!?؟۔]+(?=\s|$)", re.DOTALL)


@dataclass(frozen=True)
class SpeechChunk:
    """A stable piece of text that is safe to send to TTS."""

    text: str
    is_first: bool = False
    is_final: bool = False


class StreamingSpeechChunker:
    """Turn arbitrary LLM deltas into bounded, lossless speech chunks."""

    def __init__(
        self,
        *,
        first_chunk_words: int = 2,
        min_chunk_words: int = 3,
        max_words: int = 18,
    ) -> None:
        if first_chunk_words < 1 or min_chunk_words < 1:
            raise ValueError("Chunk word limits must be positive.")
        if max_words < min_chunk_words:
            raise ValueError("max_words must be at least min_chunk_words.")
        self.first_chunk_words = first_chunk_words
        self.min_chunk_words = min_chunk_words
        self.max_words = max_words
        self._buffer = ""
        self._emitted_any = False
        self._flushed = False

    @classmethod
    def for_language(
        cls,
        language: str,
        *,
        fallback_first_words: int = 2,
        first_chunk_words_override: int | None = None,
        min_chunk_words: int = 3,
        max_words: int = 18,
    ) -> StreamingSpeechChunker:
        profile = LanguageRegistry.load_defaults().get_profile(language)
        if first_chunk_words_override is not None and first_chunk_words_override > 0:
            first_words = first_chunk_words_override
        elif profile is not None:
            first_words = int(profile.tts_first_chunk_word_count)
        else:
            first_words = fallback_first_words
        return cls(
            first_chunk_words=first_words,
            min_chunk_words=min_chunk_words,
            max_words=max_words,
        )

    def push(self, text_delta: str) -> list[SpeechChunk]:
        if self._flushed:
            raise RuntimeError("Cannot push text after flush().")
        if text_delta:
            self._buffer += text_delta
        return self._drain(final=False)

    def flush(self) -> list[SpeechChunk]:
        if self._flushed:
            return []
        self._flushed = True
        chunks = self._drain(final=True)
        if chunks:
            last = chunks[-1]
            chunks[-1] = SpeechChunk(last.text, last.is_first, True)
        return chunks

    def _complete_word_count(self) -> int:
        matches = list(_WORD_RE.finditer(self._buffer))
        if not matches:
            return 0
        if not self._buffer[-1].isspace() and not re.search(r"[.!?؟۔]$", self._buffer):
            matches.pop()
        return len(matches)

    def _take_words(self, count: int) -> str:
        matches = list(_WORD_RE.finditer(self._buffer))
        end = matches[count - 1].end()
        text = self._buffer[:end].strip()
        self._buffer = self._buffer[end:].lstrip()
        return text

    def _emit(self, text: str) -> SpeechChunk:
        chunk = SpeechChunk(text=text.strip(), is_first=not self._emitted_any)
        self._emitted_any = True
        return chunk

    def _drain(self, *, final: bool) -> list[SpeechChunk]:
        output: list[SpeechChunk] = []
        while self._buffer.strip():
            complete_words = self._complete_word_count()
            if not self._emitted_any:
                if complete_words >= self.first_chunk_words:
                    output.append(self._emit(self._take_words(self.first_chunk_words)))
                    continue
                if final:
                    output.append(self._emit(self._buffer.strip()))
                    self._buffer = ""
                break

            sentence = _SENTENCE_RE.match(self._buffer)
            if sentence and len(sentence.group(0).split()) >= self.min_chunk_words:
                end = sentence.end()
                output.append(self._emit(self._buffer[:end]))
                self._buffer = self._buffer[end:].lstrip()
                continue
            if complete_words >= self.max_words:
                output.append(self._emit(self._take_words(self.max_words)))
                continue
            if final:
                output.append(self._emit(self._buffer.strip()))
                self._buffer = ""
            break
        return output
