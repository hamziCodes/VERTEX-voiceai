# Phase 23: Real-Time RAG and Knowledge Ingestion Contracts

## 1. Executive Summary & Core Logic

Implement tenant-isolated knowledge retrieval for live calls and post-call longitudinal memory — pgvector in existing Postgres (File 6 §3.1, File 1 §3.6 Tier 1), speculative retrieval from stabilizing STT partials (File 6 §3.2), and ingestion contracts for PDF/FAQ/web sources. Consumes Phase 20 `memory_embed_status` stub; feeds Phase 17 prompt assembly and Phase 21 context. `[NEW]` across all four legacy repos (AUDIT_05 §3) — awaazlabs dashboard `knowledge` UI has no backend pipeline (AUDIT_02 §6).

Depends on Phase 08 tenant KB config, Phase 10 DATA-framing + compliance tier embedder policy, Phase 06 embedder provider chain, Phase 22 injection ordering.

**Embedder policy:** inherits Phase 10 compliance tier — **local/self-hosted default for HIPAA (and `gdpr_strict`) tenants**; **cloud embedder allowed for `standard` tier** when tenant opts in.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| pgvector in Postgres | File 6 §3.1 — no extra SaaS; Qdrant optional adapter `[LATER]` |
| `RAGRetriever` ABC | Swappable vector backend |
| `SpeculativeRetrieval` with conservative reconcile | Wrong spoken RAG worse than slower response |
| DATA-framed `retrieved_context` turn | File 6 §1 — habiba persona isolation pattern |
| Async ingestion worker | Decouple upload from query path |
| Tier-aware embedder selection | Phase 10 compliance — PHI embeddings stay in-tenant |

**Reference docs:** blueprint File 06 §3; File 05 §8 longitudinal memory; MULTI/v3 "never invent price/stock" prompt discipline (AUDIT_01/03 §6).

## 3. What / How / Why

- **What:**
  - `KnowledgeBaseChunk`: `{chunk_id, tenant_id, source_document_id, text, embedding, metadata}`
  - `KnowledgeBaseSource`: from File 8 schema — `{source_type: pdf_upload|faq_list|web_scrape|manual_entry, source_uri, refresh_interval_hours}`
  - **`EmbedderPolicy`:** resolves from Phase 10 `compliance_tier` — `hipaa`/`gdpr_strict` → local embedder chain only (Phase 06); `standard` → local default, cloud embedder if tenant enables in JSONB
  - **`ChunkConfig`:** default **400 tokens** chunk size, **64 token overlap** (within 300–500 moderate range — not over-tuned pre-launch)
  - `RAGRetriever.retrieve(query, tenant_id, top_k=3) -> list[KnowledgeBaseChunk]` — tenant-scoped; RLS enforced
  - **`SpeculativeRetrieval`:** issue embed+search on stabilizing STT partial (2 consecutive unchanged partials); `reconcile(final_transcript, speculative_task)` — **conservative threshold: normalized Levenshtein ≤ 0.08** to reuse speculative results; **otherwise always re-query** (prefer slower correct retrieval over wrong spoken content)
  - **Injection:** `retrieved_context` conversation turn before user turn — non-blocking: if retrieval incomplete at send time, proceed without RAG (File 6 §3.3)
  - **Ingestion pipeline:** `IngestionWorker` — chunk PDF (pdfplumber/pymupdf), FAQ JSON, web scrape stub; embed via tier-resolved embedder chain; store in `knowledge_chunks` table
  - **Longitudinal memory:** on Phase 20 enqueue, if tenant enables, embed call summary facts → same vector store with `metadata.type=caller_memory`; update `memory_embed_status` on `CallRecord`; keyed by `caller_id` when present (Phase 20)
  - **Tool vs RAG priority:** registered MCP tool wins over RAG when both could answer (File 6 §4)
- **How:** Phase 17 on STT partial → `SpeculativeRetrieval.speculate()`; on STT final → conservative reconcile → inject into prompt builder before LLM. Post-call: Phase 20 assembler triggers async embed job. Ingestion: control-plane upload endpoint → S3 raw doc → worker job → pgvector insert. Tenant isolation: every query filters `tenant_id` + optional `agent_id` scope.
- **Why this approach:** Serial RAG after STT final blows File 1 §4 latency budget. Speculative overlap is the designed mitigation — but **aggressive reuse rejected** because incorrect KB content read aloud destroys caller trust. pgvector avoids Qdrant-as-required anti-pattern (File 9 §5 #20). Tier-aware embedders align with Phase 10 PHI posture.

## Deliverables

- `core/rag/__init__.py`
- `core/rag/models.py` — `KnowledgeBaseChunk`, `KnowledgeBaseSource`, `ChunkConfig`
- `core/rag/embedder_policy.py` — tier-aware embedder resolution (Phase 10)
- `core/rag/retriever.py` — `RAGRetriever`, `PgVectorRetriever`
- `core/rag/speculative.py` — `SpeculativeRetrieval` with conservative reconcile
- `core/rag/ingestion/worker.py` — `IngestionWorker`
- `core/rag/ingestion/chunkers/pdf.py`
- `core/rag/ingestion/chunkers/faq.py`
- `core/rag/memory/longitudinal.py` — updates `memory_embed_status`
- `core/rag/adapters/qdrant.py` — optional stub `[LATER]`
- `infra/db/migrations/013_knowledge_base_pgvector.sql`
- `control-plane/routes/knowledge_bases.py` — upload + status CRUD stub
- `worker-jobs/kb_ingestion.py`

## 4. Compute & Resource Profile (if applicable)

Embed+search: 50–150 ms local model; 100–300 ms cloud. Conservative reconcile may increase re-query rate (~40% vs aggressive 60% reuse — acceptable for correctness). Ingestion: ~1–5 s per PDF page async. pgvector index: HNSW recommended at >100k chunks/tenant.

## 5. Compliance Notes (if applicable)

KB documents may contain PHI if tenant uploads clinical FAQs — classify as `phi` when healthcare tier. Retrieved chunks are untrusted DATA — poisoning defense same as MCP (File 6 §5). **HIPAA tenants: cloud embedder blocked** unless local-only exception documented. Embeddings of PHI require BAA on embedder subprocessor when cloud used (standard tier opt-in). Caller memory vectors subject to Phase 11 erasure — delete on tenant erasure request; scope by `caller_id` when set.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Default embedder:** **inherits Phase 10 tier** — local/self-hosted for HIPAA/`gdpr_strict`; cloud allowed for `standard` tier opt-in.
2. **Chunk size/overlap:** **400 / 64 tokens** — moderate default within 300–500 range; not over-tuned pre-launch.
3. **Speculative edit-distance threshold:** **conservative — ≤ 0.08 normalized Levenshtein to reuse; else re-query** — wrong spoken content worse than latency.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_23_realtime_rag.py`
- **Asserts:** tenant A chunks invisible to tenant B; HIPAA fixture blocks cloud embedder; standard tier allows cloud opt-in; speculative reuse only below 0.08 threshold; re-query on divergent final; non-blocking proceed when retrieval slow; ingestion produces chunks with 400/64 config; `memory_embed_status` transitions pending→complete; DATA-framed injection not in system prompt; tool-call priority over RAG when tool matches intent.
- **Pass threshold:** 100% retriever + speculative unit tests; ingestion fixture completes.
- **Latency target:** retrieve top-3 < 200 ms p95 with local embedder (CI mock index).
