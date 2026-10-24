from __future__ import annotations

import asyncio
import importlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from .base import (
    EXPECTED_EMBEDDING_DIMENSIONS,
    EmbeddingBatch,
    EmbeddingError,
    EmbeddingPurpose,
)

SUPPORTED_MODEL_IDS = frozenset({"intfloat/multilingual-e5-small"})


class LocalONNXEmbedder:
    """Offline ONNX sentence embedder loaded only from a provisioned local bundle."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        session_factory: Callable[[str], Any] | None = None,
        tokenizer_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self.model_path = Path(model_path).resolve()
        self.model_file = self.model_path / "model.onnx"
        self.tokenizer_file = self.model_path / "tokenizer.json"
        self.metadata_file = self.model_path / "embedding_model.json"
        if not all(
            path.is_file()
            for path in (self.model_file, self.tokenizer_file, self.metadata_file)
        ):
            raise EmbeddingError(
                "model_bundle_missing",
                "Local embedding model bundle is incomplete.",
            )
        try:
            metadata = json.loads(self.metadata_file.read_text(encoding="utf-8"))
            self.model_id = str(metadata["model_id"])
            self.version = str(metadata["version"])
            self.dimensions = int(metadata["dimensions"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise EmbeddingError(
                "model_metadata_invalid", "Embedding model metadata is invalid."
            ) from exc
        if self.model_id not in SUPPORTED_MODEL_IDS:
            raise EmbeddingError(
                "model_unsupported",
                "Embedding model is not in the approved local model set.",
            )
        if self.dimensions != EXPECTED_EMBEDDING_DIMENSIONS:
            raise EmbeddingError(
                "dimension_mismatch",
                "Embedding model must output "
                f"{EXPECTED_EMBEDDING_DIMENSIONS} dimensions.",
            )
        self.query_prefix = str(metadata.get("query_prefix", "query: "))
        self.passage_prefix = str(metadata.get("passage_prefix", "passage: "))
        self.max_length = min(512, max(8, int(metadata.get("max_length", 512))))
        self.pad_id = int(metadata.get("pad_id", 1))
        self.pad_token = str(metadata.get("pad_token", "<pad>"))
        self._session_factory = session_factory or self._default_session_factory
        self._tokenizer_factory = tokenizer_factory or self._default_tokenizer_factory
        self._session: Any | None = None
        self._tokenizer: Any | None = None
        self._load_lock = asyncio.Lock()

    @staticmethod
    def _default_session_factory(path: str) -> Any:
        ort = importlib.import_module("onnxruntime")

        return ort.InferenceSession(path, providers=["CPUExecutionProvider"])

    @staticmethod
    def _default_tokenizer_factory(path: str) -> Any:
        from tokenizers import Tokenizer

        return Tokenizer.from_file(path)

    async def _ensure_loaded(self) -> tuple[Any, Any]:
        if self._session is not None and self._tokenizer is not None:
            return self._session, self._tokenizer
        async with self._load_lock:
            if self._session is None or self._tokenizer is None:
                self._session, self._tokenizer = await asyncio.to_thread(
                    self._load_sync
                )
        return self._session, self._tokenizer

    def _load_sync(self) -> tuple[Any, Any]:
        session = self._session_factory(str(self.model_file))
        tokenizer = self._tokenizer_factory(str(self.tokenizer_file))
        tokenizer.enable_truncation(max_length=self.max_length)
        tokenizer.enable_padding(pad_id=self.pad_id, pad_token=self.pad_token)
        return session, tokenizer

    async def embed(
        self, texts: list[str], *, purpose: EmbeddingPurpose
    ) -> EmbeddingBatch:
        if not texts or any(not text.strip() for text in texts):
            raise EmbeddingError(
                "embedding_input_invalid", "Embedding input must contain text."
            )
        if len(texts) > 128:
            raise EmbeddingError(
                "embedding_batch_too_large", "Embedding batch exceeds 128 items."
            )
        session, tokenizer = await self._ensure_loaded()
        prefix = (
            self.query_prefix
            if purpose == EmbeddingPurpose.QUERY
            else self.passage_prefix
        )
        vectors = await asyncio.to_thread(
            self._embed_sync,
            session,
            tokenizer,
            [f"{prefix}{text.strip()}" for text in texts],
        )
        return EmbeddingBatch(
            vectors=vectors,
            model_id=self.model_id,
            version=self.version,
            dimensions=self.dimensions,
        )

    def _embed_sync(
        self, session: Any, tokenizer: Any, texts: list[str]
    ) -> list[list[float]]:
        encodings = tokenizer.encode_batch(texts)
        input_ids = np.asarray([item.ids for item in encodings], dtype=np.int64)
        attention_mask = np.asarray(
            [item.attention_mask for item in encodings], dtype=np.int64
        )
        type_ids = np.asarray([item.type_ids for item in encodings], dtype=np.int64)
        available = {item.name for item in session.get_inputs()}
        feeds: dict[str, np.ndarray[Any, Any]] = {}
        if "input_ids" in available:
            feeds["input_ids"] = input_ids
        if "attention_mask" in available:
            feeds["attention_mask"] = attention_mask
        if "token_type_ids" in available:
            feeds["token_type_ids"] = type_ids
        outputs = session.run(None, feeds)
        raw = np.asarray(outputs[0], dtype=np.float32)
        if raw.ndim == 3:
            weights = attention_mask[:, :, None].astype(np.float32)
            raw = (raw * weights).sum(axis=1) / np.maximum(weights.sum(axis=1), 1e-9)
        if raw.ndim != 2 or raw.shape[1] != self.dimensions:
            raise EmbeddingError(
                "dimension_mismatch", "Embedding model returned an unexpected shape."
            )
        norms = np.linalg.norm(raw, axis=1, keepdims=True)
        if np.any(norms <= 1e-12):
            raise EmbeddingError(
                "embedding_zero_vector", "Embedding model returned an empty vector."
            )
        normalized = raw / norms
        return [[float(value) for value in row] for row in normalized]
