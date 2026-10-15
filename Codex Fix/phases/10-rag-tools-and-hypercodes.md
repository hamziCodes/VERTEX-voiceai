# Phase 10 — RAG, Tools, and Hypercodes

**Status:** NOT STARTED

**Goal:** Deliver durable agent-scoped knowledge retrieval and allowlisted real tool execution without elevating tenant data or enabling duplicate side effects.

**Depends on:** Phases 07 and 09.

**Audit coverage:** F04, F09, F10, P02 tool loop, I08 knowledge, I13 KB job.

## Human gate before implementation

Resolve H10. “Hypercodes” were not found in current source/docs, so this phase cannot define or implement them until Hamzi supplies expected behavior or a reference path.

## Files and interfaces

- Repair: ingestion models/job, chunkers, embedder interface, pgvector repository/retriever.
- Implement: MCP HTTP/SSE transports as applicable, host registry, credential references, allowlists, tool result schema.
- Modify: runtime session plan and LLM continuation loop.
- Test: ingestion→search, tenant/agent scope, prompt injection, tool ownership/timeout/idempotency/continuation.

## Tasks

- [ ] Define source types, parser limits, chunking, embedder selection and durable status/error state.
- [ ] Parse PDF bytes with bounded resources; never stringify raw binary as document text.
- [ ] Generate embeddings under compliance policy and query the vector column; remove lexical mock fallback from production.
- [ ] Scope every chunk/search by authenticated tenant and pinned agent KB bindings.
- [ ] Insert retrieved text as untrusted data with citations/source IDs, not privileged system instructions; test adversarial documents.
- [ ] Implement required MCP transports using protocol-correct JSON-RPC/network behavior; keep stdio local-only.
- [ ] Resolve tool name to owning host, enforce allowed_tools/schema/timeouts/credentials, sanitize outputs, and close transports.
- [ ] Continue the LLM with tool_call_id/result until bounded completion; cap calls/time/tokens and prevent side-effect replay.
- [ ] Make escalation/end-conversation tools invoke actual lifecycle hooks or mark unavailable.
- [ ] Implement/document hypercodes only after H10; add its audit mapping and acceptance tests.

## Verification

```powershell
python -m pytest tests/rag tests/mcp tests/listening/test_tool_loop.py -q
```

Expected: durable upload→embedding→agent-scoped retrieval; cross-tenant search empty/denied; injection ignored; correct host executes once; timeout/degraded result is explicit.

## Human intervention

Hamzi defines v1 systems/tools and supplies only sanitized sample schemas/data. Any real CRM/business-system call is separately approved.

## Exit criteria

- No KB status reports ready without completed durable ingestion.
- RAG and tools are connected to the pinned runtime plan.
- Side effects are idempotent and auditable.
