"""Compliance-aware embedding adapter selection."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from core.rag.embedders.base import EmbeddingError, TextEmbedder
from core.rag.embedders.local_onnx import LocalONNXEmbedder


class EmbedderPolicy:
    @staticmethod
    def is_cloud_embedder_allowed(
        compliance_tier: str, tenant_opt_in: bool = False
    ) -> bool:
        return (
            compliance_tier.lower().strip() not in {"hipaa", "gdpr_strict"}
            and tenant_opt_in
        )

    @staticmethod
    def get_embedder_type(compliance_tier: str, tenant_opt_in: bool = False) -> str:
        if EmbedderPolicy.is_cloud_embedder_allowed(compliance_tier, tenant_opt_in):
            return "cloud"
        return "local"

    @staticmethod
    def create_embedder(
        *,
        compliance_tier: str,
        tenant_opt_in: bool,
        local_model_path: str | Path,
        cloud_factory: Callable[[], TextEmbedder] | None = None,
    ) -> TextEmbedder:
        selected = EmbedderPolicy.get_embedder_type(compliance_tier, tenant_opt_in)
        if selected == "cloud":
            if cloud_factory is None:
                raise EmbeddingError(
                    "cloud_embedder_unavailable",
                    "Cloud embedding was selected but no approved adapter "
                    "is configured.",
                )
            return cloud_factory()
        return LocalONNXEmbedder(local_model_path)

    @staticmethod
    def create_from_environment(
        *,
        compliance_tier: str,
        tenant_opt_in: bool = False,
        cloud_factory: Callable[[], TextEmbedder] | None = None,
    ) -> TextEmbedder:
        selected = EmbedderPolicy.get_embedder_type(compliance_tier, tenant_opt_in)
        if selected == "cloud":
            if cloud_factory is None:
                raise EmbeddingError(
                    "cloud_embedder_unavailable",
                    "Cloud embedding was selected but no approved adapter "
                    "is configured.",
                )
            return cloud_factory()
        model_path = (os.environ.get("UCVE_EMBEDDING_MODEL_PATH") or "").strip()
        if not model_path:
            raise EmbeddingError(
                "model_bundle_missing",
                "UCVE_EMBEDDING_MODEL_PATH must identify a local model bundle.",
            )
        return LocalONNXEmbedder(model_path)
