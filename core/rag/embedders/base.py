from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

EXPECTED_EMBEDDING_DIMENSIONS = 384


class EmbeddingPurpose(StrEnum):
    QUERY = "query"
    PASSAGE = "passage"


class EmbeddingError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.safe_message = message


@dataclass(frozen=True, slots=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    model_id: str
    version: str
    dimensions: int


class TextEmbedder(Protocol):
    model_id: str
    version: str
    dimensions: int

    async def embed(
        self, texts: list[str], *, purpose: EmbeddingPurpose
    ) -> EmbeddingBatch: ...
