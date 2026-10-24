from __future__ import annotations

import json

import numpy as np
import pytest

from core.rag.embedder_policy import EmbedderPolicy
from core.rag.embedders.base import EmbeddingError, EmbeddingPurpose
from core.rag.embedders.local_onnx import LocalONNXEmbedder


class _Encoding:
    def __init__(self, ids: list[int]) -> None:
        self.ids = ids
        self.attention_mask = [1] * len(ids)
        self.type_ids = [0] * len(ids)


class _Tokenizer:
    def enable_truncation(self, max_length: int) -> None:
        assert max_length == 512

    def enable_padding(self, **_kwargs) -> None:
        pass

    def encode_batch(self, texts: list[str]) -> list[_Encoding]:
        return [_Encoding([index + 1, 2]) for index, _text in enumerate(texts)]


class _Input:
    def __init__(self, name: str) -> None:
        self.name = name


class _Session:
    def get_inputs(self) -> list[_Input]:
        return [_Input("input_ids"), _Input("attention_mask"), _Input("token_type_ids")]

    def run(self, _outputs, feeds):
        batch, tokens = feeds["input_ids"].shape
        output = np.ones((batch, tokens, 384), dtype=np.float32)
        output[:, :, 0] = feeds["input_ids"]
        return [output]


@pytest.mark.asyncio
async def test_local_onnx_contract_is_batched_normalized_and_off_event_loop(
    tmp_path,
) -> None:
    (tmp_path / "model.onnx").write_bytes(b"fixture")
    (tmp_path / "tokenizer.json").write_text("{}", encoding="utf-8")
    (tmp_path / "embedding_model.json").write_text(
        json.dumps(
            {
                "model_id": "intfloat/multilingual-e5-small",
                "version": "fixture-v1",
                "dimensions": 384,
                "query_prefix": "query: ",
                "passage_prefix": "passage: ",
            }
        ),
        encoding="utf-8",
    )
    caller_thread = None

    def session_factory(_path: str):
        nonlocal caller_thread
        caller_thread = __import__("threading").get_ident()
        return _Session()

    embedder = LocalONNXEmbedder(
        tmp_path,
        session_factory=session_factory,
        tokenizer_factory=lambda _path: _Tokenizer(),
    )
    event_loop_thread = __import__("threading").get_ident()
    result = await embedder.embed(
        ["refund policy", "opening hours"], purpose=EmbeddingPurpose.QUERY
    )

    assert result.model_id == "intfloat/multilingual-e5-small"
    assert result.dimensions == 384
    assert len(result.vectors) == 2
    assert np.linalg.norm(result.vectors[0]) == pytest.approx(1.0)
    assert caller_thread != event_loop_thread


def test_local_adapter_refuses_missing_or_dimension_mismatched_bundle(tmp_path) -> None:
    with pytest.raises(EmbeddingError, match="model_bundle_missing"):
        LocalONNXEmbedder(tmp_path)

    (tmp_path / "model.onnx").write_bytes(b"fixture")
    (tmp_path / "tokenizer.json").write_text("{}", encoding="utf-8")
    (tmp_path / "embedding_model.json").write_text(
        json.dumps(
            {
                "model_id": "intfloat/multilingual-e5-small",
                "version": "v1",
                "dimensions": 768,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(EmbeddingError, match="dimension_mismatch"):
        LocalONNXEmbedder(tmp_path)


def test_policy_is_local_by_default_and_cloud_requires_explicit_factory(
    tmp_path,
) -> None:
    assert EmbedderPolicy.get_embedder_type("standard", tenant_opt_in=False) == "local"
    with pytest.raises(EmbeddingError, match="cloud_embedder_unavailable"):
        EmbedderPolicy.create_embedder(
            compliance_tier="standard",
            tenant_opt_in=True,
            local_model_path=tmp_path,
        )


def test_environment_policy_refuses_missing_local_bundle(monkeypatch) -> None:
    monkeypatch.delenv("UCVE_EMBEDDING_MODEL_PATH", raising=False)
    with pytest.raises(EmbeddingError, match="model_bundle_missing"):
        EmbedderPolicy.create_from_environment(compliance_tier="standard")
