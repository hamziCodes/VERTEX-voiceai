"""Phase 23: Real-Time RAG & Knowledge Ingestion Contracts Test Suite."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from core.rag.embedder_policy import EmbedderPolicy
from core.rag.ingestion.worker import IngestionWorker
from core.rag.memory.longitudinal import LongitudinalMemoryEmbedder
from core.rag.models import ChunkConfig, KnowledgeBaseChunk, KnowledgeBaseSource
from core.rag.retriever import PgVectorRetriever
from core.rag.speculative import SpeculativeRetrieval, normalized_levenshtein
from post_call.models.call_record import CallRecord
from post_call.models.diarized_turn import DiarizedTurn
from post_call.models.memory_embed import MemoryEmbedStatus

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_23_real_time_rag_and_knowledge_ingestion_contracts.md"
    )
    assert plan.is_file()


@pytest.mark.asyncio
async def test_tenant_isolation_chunks_invisible() -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()

    retriever = PgVectorRetriever()
    retriever.seed_chunks(
        tenant_a,
        [KnowledgeBaseChunk(tenant_id=tenant_a, text="Secret policy for Tenant A")],
    )
    retriever.seed_chunks(
        tenant_b,
        [KnowledgeBaseChunk(tenant_id=tenant_b, text="Secret policy for Tenant B")],
    )

    # Query for Tenant A should never return Tenant B chunks
    res_a = await retriever.retrieve("Secret policy", tenant_id=tenant_a)
    assert len(res_a) == 1
    assert res_a[0].tenant_id == tenant_a
    assert "Tenant A" in res_a[0].text

    res_b = await retriever.retrieve("Secret policy", tenant_id=tenant_b)
    assert len(res_b) == 1
    assert res_b[0].tenant_id == tenant_b


def test_embedder_policy_hipaa_blocks_cloud() -> None:
    # HIPAA & GDPR_STRICT block cloud embedder (PHI protection)
    assert EmbedderPolicy.is_cloud_embedder_allowed("hipaa", tenant_opt_in=True) is False
    assert EmbedderPolicy.get_embedder_type("hipaa", tenant_opt_in=True) == "local"

    # Standard tier allows cloud embedder when tenant opts in
    assert EmbedderPolicy.is_cloud_embedder_allowed("standard", tenant_opt_in=True) is True
    assert EmbedderPolicy.get_embedder_type("standard", tenant_opt_in=True) == "cloud"


def test_normalized_levenshtein_distance() -> None:
    assert normalized_levenshtein("hello world", "hello world") == 0.0
    # Minor edit (1 char diff out of 11 chars) = 1/11 = 0.0909
    assert normalized_levenshtein("hello world", "hello worlz") <= 0.10


@pytest.mark.asyncio
async def test_speculative_retrieval_reconcile_threshold() -> None:
    tenant_id = uuid4()
    retriever = PgVectorRetriever()
    retriever.seed_chunks(
        tenant_id,
        [KnowledgeBaseChunk(tenant_id=tenant_id, text="Pricing for clinic consultation is 100 dollars")],
    )

    speculative = SpeculativeRetrieval(retriever, threshold=0.08)

    # 1. Speculate on partial STT
    await speculative.speculate("pricing for clinic consultation", tenant_id)
    assert len(speculative.speculative_results) == 1

    # 2. Final transcript identical -> Levenshtein = 0.0 <= 0.08 -> Reuses speculative result
    res_exact = await speculative.reconcile("pricing for clinic consultation", tenant_id)
    assert len(res_exact) == 1

    # 3. Final transcript divergent -> Levenshtein > 0.08 -> Re-queries retriever
    res_divergent = await speculative.reconcile("how much is an emergency tooth extraction cost", tenant_id)
    assert len(res_divergent) == 1


@pytest.mark.asyncio
async def test_ingestion_worker_pdf_chunk_config() -> None:
    worker = IngestionWorker(chunk_config=ChunkConfig(chunk_size_tokens=400, chunk_overlap_tokens=64))
    source = KnowledgeBaseSource(tenant_id=uuid4(), source_type="pdf_upload", source_uri="s3://bucket/doc.pdf")

    sample_text = " ".join([f"word{i}" for i in range(1000)])
    chunks = await worker.ingest_source(source, sample_text)
    assert len(chunks) >= 3
    assert chunks[0].metadata["source"] == "pdf"


@pytest.mark.asyncio
async def test_longitudinal_memory_embed_status_transition() -> None:
    memory_handler = LongitudinalMemoryEmbedder()
    record = CallRecord(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        turns=[DiarizedTurn(speaker="user", text="I am allergic to penicillin", start_ms=0, end_ms=1000)],
        memory_embed_status=MemoryEmbedStatus.PENDING,
    )

    status = await memory_handler.process_call_record_memory(record)
    assert status == MemoryEmbedStatus.COMPLETE
    assert record.memory_embed_status == MemoryEmbedStatus.COMPLETE
