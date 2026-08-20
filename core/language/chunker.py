"""UCVE Sentence Chunker for TTS Stream Dispatch."""

from __future__ import annotations

import re


class SentenceChunker:
    """Chunks text into sentence units; first chunk is 2 words for TTFT optimization."""

    def chunk(
        self, text: str, first_chunk_words: int = 2, min_chunk_words: int = 3
    ) -> list[str]:
        """Chunk text stream into TTFT-optimized initial chunk followed by sentence units."""
        text = text.strip()
        if not text:
            return []

        words = text.split()
        if len(words) <= first_chunk_words:
            return [text]

        chunks = []
        # First chunk: first_chunk_words (2 words) for low TTFT latency
        first_chunk = " ".join(words[:first_chunk_words])
        remaining_text = " ".join(words[first_chunk_words:])
        chunks.append(first_chunk)

        # Split remaining text by sentence boundary punctuation
        raw_sentences = re.split(r"(?<=[.!?\n])\s+", remaining_text)
        current_chunk = ""

        for sentence in raw_sentences:
            if not sentence.strip():
                continue
            if not current_chunk:
                current_chunk = sentence.strip()
            else:
                if len(current_chunk.split()) < min_chunk_words:
                    current_chunk += " " + sentence.strip()
                else:
                    chunks.append(current_chunk)
                    current_chunk = sentence.strip()

        if current_chunk:
            chunks.append(current_chunk)

        return chunks
