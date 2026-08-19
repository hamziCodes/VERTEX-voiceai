"""Phase 23: Real-Time RAG and Knowledge Ingestion."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_23_real_time_rag_and_knowledge_ingestion_contracts.md"
)


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_embedder_tier_policy_documented() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "hipaa" in text.lower()
    assert "0.08" in text
    assert "400" in text
    assert "None — fully deterministic" in text


def test_speculative_conservative_threshold() -> None:
    try:
        from core.rag.speculative import SpeculativeRetrieval  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 23 implementation pending: {exc}")
    sr = SpeculativeRetrieval()
    assert sr.reuse_threshold <= 0.08
