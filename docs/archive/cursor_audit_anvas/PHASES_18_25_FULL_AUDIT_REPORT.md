# UCVE Phases 18–25 — Full Production Readiness Audit Report

**Audit date:** 2026-08-22  
**Scope:** Phase 18 through Phase 25 only  
**Prior phases:** 00–17 referenced only for cross-phase contract compatibility  
**Tracker claim:** All of 18–25 marked `COMPLETED` in `voice_engine_plan/implementation_plan/EXECUTION_TRACKER.md` (2026-08-22)  
**Audit verdict:** **0 / 8 Pass** — tracker overstates readiness

**Path convention note:** Specs often use hyphen paths (`telephony-gateway/`, `post-call/`, `worker-raw/`, `control-plane/`). Implementation uses underscore packages (`telephony_gateway/`, `post_call/`, `worker_raw/`, `control_plane/`). Hyphen paths are treated as present when the underscore package exists, unless a deliverable is truly missing.

---

## 1. Executive Summary & Phase Status Matrix

| Phase | Status | Core Functionality Checked | Critical Findings Count |
| :--- | :--- | :--- | :--- |
| Phase 18 | **Incomplete** | Telnyx webhook/signature, DID resolve, DirectSIP μ-law path, metering | 7 |
| Phase 19 | **Needs Fix** | Trunk config, failover router, adapters, webhook normalizer | 3 |
| Phase 20 | **Incomplete** | CallRecord models, recording policy, assembler, repo, migration | 6 |
| Phase 21 | **Incomplete** | Extraction schema, verification, HMAC dispatcher, review queue, worker | 6 |
| Phase 22 | **Incomplete** | MCPHost, ToolOrchestrator, builtins, filler, timeout | 6 |
| Phase 23 | **Incomplete** | Embedder policy, SpeculativeRetrieval, pgvector migration, ingestion | 7 |
| Phase 24 | **Needs Fix** | Waterfall, collector, SLOPolicy, demotion, latency hooks | 6 |
| Phase 25 | **Needs Fix** | UCVEErrorCode, ClientErrorMapper, AlertRouter, DLQ, sweeper | 7 |

### Shared systemic blockers

1. **Cross-phase wiring absent** — Phase 17 `PipelineOrchestrator` never receives telephony frames, MCP tools, RAG context, latency hooks, or post-call enqueue.
2. **Security fail-open paths** — Telnyx signature HMAC fallback on public key; webhook key optional; DID resolver defaults to a shared tenant; control-plane routes unmounted.
3. **Persistence is in-memory** — CallRecord repo, HumanReviewQueue, MCP/RAG stores, and DLQ ignore Postgres migrations; several tables lack RLS.
4. **Declared behavior not implemented** — Webhook 3× backoff, AlertRouter email/webhook, pgvector retrieve, MCP transports, and rolling-p50 demotion are stubs or no-ops.
5. **Phase tests are surface-level** — green tests mostly assert existence/happy-path mocks, not §7 deep contracts.

**Approximate finding volume:** ~48 High+Medium actionable items (see §5 Master Fix Checklist). Plus intentional Low/`[LATER]` stubs noted separately.

---

## 2. Detailed Gap Analysis & Anomalies (By Phase)

### Phase 18 — Telephony/SIP Base — **Incomplete**

#### Deliverable inventory (summary)

| Spec / expected | Actual | Status |
|---|---|---|
| `telephony-gateway/*` | `telephony_gateway/*` | Present (renamed) |
| Telnyx webhook + signature | `telephony_gateway/telnyx/` | Exists / insecure / incomplete |
| Transcoding μ-law / rebuffer | `telephony_gateway/transcoding/` | Exists / complete enough |
| DID resolver | `telephony_gateway/resolver/` | Exists / stubbed fail-open |
| `core/transport/direct_sip.py` | same | Incomplete (no real SIP/RTP) |
| `core/transport/livekit_sip.py` | same | Stubbed fake-success |
| `core/transport/caller_id.py` | same | Surface complete |
| `worker-raw/telephony/inbound_handler.py` | `worker_raw/telephony/inbound_handler.py` | Incomplete (no pipeline) |
| `009_telephony_dids.sql` | same | Incomplete (no RLS; migration number collision) |
| `tenant-portal-api/telephony_routes.py` | Missing; orphan `control_plane/routes/telephony.py` **unmounted** | Missing / dead |
| Session mint `transport_type=sip` | Missing on `PipelineSessionConfig` | Missing |
| Emit `telephony_sec` | Kind exists in `core/metering/kinds.py`; never recorded | Missing |

#### Findings

| ID | Component | Gap / Anomaly | Severity |
|---|---|---|---|
| P18-H1 | `telephony_gateway/telnyx/signature.py` `verify_telnyx_signature` (~L37–69) | Ed25519 failure swallowed (`except Exception: pass`) then HMAC-SHA256 using `public_key_or_secret` as HMAC key. Telnyx public key is public → attacker can forge HMAC signatures. | **High** |
| P18-H2 | `telephony_gateway/telnyx/webhook.py` `process_event` (~L35–43) | Signature verified only `if self.public_key:`. Empty key skips all verification. `control_plane/routes/telephony.py` constructs handler with empty key. | **High** |
| P18-H3 | `telephony_gateway/resolver/sip_participant_resolver.py` `resolve` (~L28–36) | Unknown DID returns `DEFAULT_TENANT_ID` / `DEFAULT_AGENT_ID`. `db_session` accepted but never queried; migration table unused. Tenant isolation bypass. | **High** |
| P18-H4 | `worker_raw/telephony/inbound_handler.py` (~L14–40) | Docstring claims PipelineOrchestrator connection; never constructs/calls it. No `AudioFrame` wrap. `close()` returns duration float only — no `UsageMeter.record(..., TELEPHONY_SEC, ...)`. | **High** |
| P18-H5 | `control_plane/routes/telephony.py` vs `control_plane/app.py` | Webhook route module exists but **no** `include_router` — dead code. Spec deliverable `tenant-portal-api/telephony_routes.py` missing. | **High** |
| P18-H6 | `core/transport/direct_sip.py` | Transcoder front-end only (μ-law→PCM rebuffer). No RTP/SIP stack, SDP, Call Control answer/media. Production inbound PSTN cannot run. | **High** |
| P18-H7 | `telephony_gateway/telnyx/webhook.py` (~L49–50) | Hardcoded default caller/callee (`+15550199000` / `+18005550199`) when payload fields missing — fabricated identity. | **High** |
| P18-M1 | `core/transport/livekit_sip.py` `connect` (~L21–26) | When flag enabled, returns `True` with no LiveKit room/participant I/O. | **Medium** |
| P18-M2 | `infra/db/migrations/009_telephony_dids.sql` | No `ENABLE/FORCE ROW LEVEL SECURITY`. Collides with `009_foundation_hardening.sql` numbering. | **Medium** |
| P18-M3 | `worker_raw/orchestration/session_config.py` `PipelineSessionConfig` | No `caller_id`, no `transport_type`. Sessions schema has `transport_type`; telephony path never sets `sip`. `CallerIdContext` never propagated. | **Medium** |
| P18-M4 | Webhook response / session mint | Returns raw UUIDs / dataclass; no Phase 13 HMAC/JWT mint; no persistence. | **Medium** |
| P18-M5 | `telephony_gateway` packaging | Not a uv workspace member (`pyproject.toml` members: core, control_plane, worker_raw only). Deploy fragility. | **Medium** |
| P18-M6 | Phase 17 contract | Same pipeline core as native WS not used; FSM/barge-in latent; Phase 20 expects CallerIdContext on session. | **Medium** |
| P18-L1 | `inbound_handler.py` | Unused import `mulaw_to_pcm16`; no `__init__.py` under `worker_raw/telephony/`. | **Low** |
| P18-L2 | `core/transport/caller_id.py` | No E.164 validation. | **Low** |

#### Phase 18 tests

File: `voice_engine_plan/tests/phase_tests/test_phase_18_telephony_sip_base.py`  
**Depth:** Surface. Missing: handler rejects invalid signature; DirectSIP → mock PipelineOrchestrator; `telephony_sec` increment; caller ID in session context.

---

### Phase 19 — Telephony Abstraction & Secondary Trunk — **Needs Fix**

#### Deliverable inventory (summary)

| Spec / expected | Actual | Status |
|---|---|---|
| `telephony_gateway/base.py` | same | Exists / ABC signatures flawed |
| `trunk_config.py`, `failover.py` | same | Exists / incomplete probes+audit |
| Adapters (DirectSIP, LiveKit, PTA, Twilio) | `telephony_gateway/adapters/` | Partial / stubs (some intentional) |
| `webhook_normalizer.py` | same | Surface complete |
| `010_sip_trunks.sql` | same | Exists / unused / no RLS |
| Periodic OPTIONS/ping health | — | Missing |
| Phase 12 audit on failover | — | Missing |
| Vault credential resolution | — | Missing |

#### Findings

| ID | Component | Gap / Anomaly | Severity |
|---|---|---|---|
| P19-H1 | `telephony_gateway/adapters/telnyx_direct_sip.py` `receive_audio` / `send_audio` | Always `None` / `pass`. Spec §7 requires DirectSIP adapter → 16 kHz frames to pipeline mock — unimplemented & untested. | **High** |
| P19-H2 | Stub / primary adapter `health_check` | Always `True` (Generic PTA, Twilio SIP, Telnyx DirectSIP) with no OPTIONS/ping — failover can route to non-functional trunks. | **High** |
| P19-H3 | Vault fail-closed | `SIPTrunkConfig.validate` only checks non-empty `credentials_ref` string. No Phase 09 vault fetch/materialization. | **High** |
| P19-M1 | `telephony_gateway/failover.py` `get_active_trunk` | Passive map lookup only. No periodic health, no transport `health_check()` calls, no Phase 12 audit on switch. | **Medium** |
| P19-M2 | `010_sip_trunks.sql` | Table unused by router; no RLS. | **Medium** |
| P19-M3 | `telephony_gateway/base.py` (~L44–66) | Abstract `connect`/`hangup`/`health_check` missing `self` — ABC/runtime footgun. | **Medium** |
| P19-M4 | `webhook_normalizer.py` | Always mints new `session_id` via `uuid4()` — no correlation to Phase 18 session mint. | **Medium** |
| P19-M5 | Intentional stubs misusable | `GenericPTAAdapter` / `TwilioSIPAdapter`: `connect()` succeeds; silent `pass` on `send_audio` if selected in failover chain. | **Medium** |
| P19-L1 | Spec-allowed stubs | `TwilioMediaStreamTransport` ABC — OK per §6. | **Low** |

#### Phase 19 tests

File: `voice_engine_plan/tests/phase_tests/test_phase_19_telephony_abstraction.py`  
**Depth:** Surface failover with injected health map. Missing: 16 kHz media path; periodic health; latency &lt; 10 ms failover assert; audit emission.

---

### Phase 20 — Post-Call Intelligence Core Record Schema — **Incomplete**

#### Deliverable inventory (summary)

| Spec / expected | Actual | Status |
|---|---|---|
| `post_call/models/*` | same | Models present; some incomplete vs §3 |
| `post_call/pipeline/enqueue.py` | same | Incomplete (in-memory gate) |
| `post_call/pipeline/assembler.py` | same | Incomplete |
| `post_call/pipeline/recording_policy.py` | same | Buggy for `standard` disable |
| `011_call_records.sql` | same | Incomplete schema / no RLS |
| `core/db/repos/call_record_repo.py` | same | Stubbed in-memory |
| S3 upload when recording required | — | Missing |
| Phase 17 → PostCallPipeline wire | — | Missing |

#### Findings

| ID | Component | Gap / Anomaly | Severity |
|---|---|---|---|
| P20-H1 | `core/db/repos/call_record_repo.py` `PostgresCallRecordRepository` (~L14–21) | `db_pool` unused; dict store only. Idempotency is process-local. No SQL/`ON CONFLICT`/RLS session. | **High** |
| P20-H2 | S3 / object client | No upload. Recording is URI-only metadata in assembler (`recording_uri`). | **High** |
| P20-H3 | `worker_raw/orchestration/pipeline.py` (~L171–190) | Disconnect does **not** call `PostCallPipeline` / assembler; may emit audit without persisting `CallRecord`. | **High** |
| P20-H4 | `recording_policy.py` + `enqueue.py` | `validate_record` never passes `tenant_config`. For `standard`, `is_recording_required` defaults True when config omitted → standard no-recording path broken. | **High** |
| P20-H5 | `011_call_records.sql` | Missing `transcript_redacted_ref`, `transcript_raw_ref`, recording duration/checksum, verification issues; no RLS. Parallel to Phase 08 `session_transcripts` / `session_recordings` without dual-write/FK. | **High** |
| P20-H6 | Phase 10/11 wiring | `recording_enabled` / `policy_overrides` / zero-retention / dual transcript columns not applied in assembler/enqueue. | **High** |
| P20-M1 | Phase 12 audit from post-call persist | No audit emit from `PostCallPipeline` itself. | **Medium** |
| P20-M2 | `CallRecord` model | `VerificationIssue` list absent (lives only in Phase 21). Turns not sorted by `start_ms`. `caller_id` not E.164-validated. Compliance tier free `str`. | **Medium** |
| P20-M3 | `post_call` packaging | Not a uv workspace member; no `post_call/pyproject.toml`. | **Medium** |
| P20-L1 | `memory_embed_status` | Intentional stub enum — OK per §3/§6. | **Low** |
| P20-L2 | Phase 20 test | Dead helper `dual_channel_recording_default_check` — assertion always True. | **Low** |

#### Phase 20 tests

File: `voice_engine_plan/tests/phase_tests/test_phase_20_post_call_record_schema.py`  
**Depth:** Mostly surface. Missing: turns ordered by time; zero-retention redacted-only; real SQL idempotency; S3; assemble+enqueue &lt; 100 ms; standard disable via enqueue.

---

### Phase 21 — Structured Extraction & CRM Dispatch — **Incomplete**

#### Deliverable inventory (summary)

| Spec / expected | Actual | Status |
|---|---|---|
| Extraction schema/service | `post_call/extraction/` | Schema OK; service stubbed |
| Verification + phone/datetime | `post_call/verification/` | Partial (TZ unused) |
| Human review queue | `post_call/review/queue.py` | In-memory intentional stub |
| Summarization | `post_call/summarization/` | Heuristic placeholder |
| Webhook dispatcher/targets | `post_call/webhook/` | HMAC only; no retry/HTTP/DLQ |
| WhatsApp channel | `post_call/channels/whatsapp.py` | Intentional ABC stub |
| Worker | `post_call/worker.py` | Incomplete orchestration |
| `012_extraction_schemas_webhooks.sql` | same | Schema OK; no RLS |
| Control-plane extraction routes | `control_plane/routes/extraction_schemas.py` | Stub; **unmounted** |
| `FollowUpTrigger` stub | — | Missing |

#### Findings

| ID | Component | Gap / Anomaly | Severity |
|---|---|---|---|
| P21-H1 | `post_call/extraction/service.py` `extract` (~L33–42) | Substring mock (`extracted_{name}_val`), not Phase 06 FailoverRouter / structured LLM. | **High** |
| P21-H2 | `ExtractionService.__init__` BAA flag (~L14–15) | Constructor bool default **`True`**, not Phase 10 `TenantComplianceProfile` / `hipaa_baa_acknowledged_at`. Easy prod bypass. | **High** |
| P21-H3 | `post_call/webhook/dispatcher.py` `dispatch` (~L28–59) | Documents 3× exponential backoff + idempotency; **no retry loop**, no sleep/backoff, default path appends payload and returns `True` (false-success). `max_retries` unused. No DLQ. | **High** |
| P21-H4 | Phase 25 DLQ | `core/errors/dlq.py` unused by post-call / dispatcher. | **High** |
| P21-H5 | `post_call/worker.py` (~L52–86) | Extraction from raw turn text join (not Phase 11 redacted-only). Review gate incomplete; CRM payload missing `verified` (has `issues_count`). | **High** |
| P21-H6 | GDPR / consent | No block of raw audio URLs in webhook payload without consent. | **High** |
| P21-M1 | Audit / metering | No Phase 12 (`data_export`, `crm_dispatch`) and no Phase 14 `extraction_calls` meter. | **Medium** |
| P21-M2 | `control_plane/routes/extraction_schemas.py` | Not mounted; no Phase 13 auth/RBAC; create returns fake success, no DB. | **Medium** |
| P21-M3 | `HumanReviewQueue` | In-memory despite `human_review_queue` table in 012. | **Medium** |
| P21-M4 | `TenantWebhookTarget` | Model only — no load from `webhook_targets` / vault; secrets likely plaintext in model. | **Medium** |
| P21-M5 | `verification/datetime.py` | `clinic_timezone` ignored (UTC-vs-clinic lesson from awaazlabs). | **Medium** |
| P21-M6 | Phone verify | Only if `field.type == "phone"`; does not normalize extracted values in-place before CRM. | **Medium** |
| P21-M7 | `SummarizationService` | Heuristic truncation + hardcoded sentiment — not LLM. | **Medium** |
| P21-M8 | Migration 012 | No RLS on extraction_schemas / webhook_targets / human_review_queue. | **Medium** |
| P21-L1 | WhatsAppDispatcher | Intentional abstract stub — OK. | **Low** |
| P21-L2 | FollowUpTrigger | Spec What item missing (not in Deliverables list). | **Low** |

#### Phase 21 tests

File: `voice_engine_plan/tests/phase_tests/test_phase_21_crm_dispatch.py`  
**Depth:** Mixed; several §7 asserts missing or fake-green (HMAC receiver mock, idempotent retry, real HTTP 2xx, worker p95).

---

### Phase 22 — Real-Time MCP Tooling — **Incomplete**

#### Deliverable inventory (summary)

| Spec / expected | Actual | Status |
|---|---|---|
| `core/mcp/host.py` | same | Stubbed mock |
| `builtin_tools.py`, `orchestrator.py`, `filler.py`, `timeout_fallback.py` | same | Partial |
| Transports stdio/sse/streamable_http | `core/mcp/transports/` | Stubbed |
| `worker_raw/orchestration/tool_handler.py` | same | Exists; **not wired** into pipeline |
| `tests/fixtures/mcp/` | — | **Missing** |

#### Findings

| ID | Component | Gap / Anomaly | Severity |
|---|---|---|---|
| P22-H1 | `MCPHost.connect` / `list_tools` / `_exec_tool` (~L59–89) | Sets connected flag; hardcoded tool list; sleep + fake success. No real MCP protocol. | **High** |
| P22-H2 | Transports | `SSEMCPTransport` / `StreamableHTTPMCPTransport` / enabled stdio: `connect()` → `True` with no aiohttp/SSE/subprocess. | **High** |
| P22-H3 | Phase 09 vault | `MCPServerConfig.credentials_ref` field only; SecretVault never used under `core/mcp/`. | **High** |
| P22-H4 | Phase 17 / Phase 03 | `pipeline.py` `run_turn` has no tool_call handling / `TOOL_CALL_START` / `TOOL_RESULT`. `PipelineToolHandler` orphaned. FSM `TOOL_EXECUTING` never driven by MCP. | **High** |
| P22-H5 | Timeout → TTS fallback | On timeout embeds utterance in error content string; does not call `ToolTimeoutFallback`, enqueue TTS, or emit audit. | **High** |
| P22-H6 | Phase 12 audit | Actions `tool_call`, `tool_result`, `mcp_connect`, `tool_timeout_fallback` defined but never emitted from `core/mcp/*`. | **High** |
| P22-M1 | Allowlist / sandbox | `allowed_tools` never checked; no tenant tool-surface isolation; first connected host gets any name. | **Medium** |
| P22-M2 | Serial execution | No `asyncio.Lock` / queue — concurrent `execute_tool_call_serially` can overlap. | **Medium** |
| P22-M3 | Builtin tools | Disposition stubs only — no DB / CallRecord / warm-transfer event. | **Medium** |
| P22-M4 | Filler | Callback only; no TTS, language phrases, `tool.filler_started`, barge-in hook. | **Medium** |
| P22-M5 | DATA-framing | Boolean flag only — not proven prompt isolation. | **Medium** |
| P22-M6 | HIPAA / BAA MCP block | §5 requirement unimplemented. | **Medium** |
| P22-L1 | Concurrent MCP server cap (default 3) | Not implemented. | **Low** |

#### Phase 22 tests

File: `voice_engine_plan/tests/phase_tests/test_phase_22_mcp_tooling.py`  
**Depth:** Surface. Missing: DATA-framed not in system prompt; sync `to_thread`; barge cancels filler; disposition write; TTS fallback; audit; pipeline fixture round-trip.

---

### Phase 23 — Real-Time RAG & Knowledge Ingestion — **Incomplete**

#### Deliverable inventory (summary)

| Spec / expected | Actual | Status |
|---|---|---|
| `core/rag/models.py` | same | Complete dataclasses |
| `embedder_policy.py` | same | String policy only |
| `retriever.py` | same | Keyword mock |
| `speculative.py` | same | Partial Levenshtein |
| Ingestion worker + chunkers | `core/rag/ingestion/` | Chunk only; PDF not real PDF |
| Longitudinal memory | `core/rag/memory/longitudinal.py` | Status flip stub |
| Qdrant adapter | `core/rag/adapters/qdrant.py` | Intentional `[LATER]` |
| `013_knowledge_base_pgvector.sql` | same | No embedding/HNSW/RLS |
| `control_plane/routes/knowledge_bases.py` | same | Fake status; **unmounted** |
| `worker-jobs/kb_ingestion.py` | — | **Missing** |

#### Findings

| ID | Component | Gap / Anomaly | Severity |
|---|---|---|---|
| P23-H1 | `PgVectorRetriever` (~L21–45) | `_mock_chunks` + keyword intersection; `db_pool` unused. | **High** |
| P23-H2 | `013_knowledge_base_pgvector.sql` | `CREATE EXTENSION vector` but **no** `embedding vector(...)` column, no HNSW, no RLS, no `agent_id` scope, no `knowledge_sources` table. | **High** |
| P23-H3 | Phase 17 injection | No `retrieved_context` / `SpeculativeRetrieval` in `PipelineOrchestrator.run_turn`. Non-blocking “proceed without RAG” absent. | **High** |
| P23-H4 | `EmbedderPolicy` | Returns `"local"` / `"cloud"` strings only; no Phase 06 embedder provider chain; ingestion never embeds. | **High** |
| P23-H5 | `worker-jobs/kb_ingestion.py` | Missing. Control-plane → S3 → worker → pgvector path incomplete. `IngestionWorker.ingest_source` chunks in memory only. | **High** |
| P23-H6 | `LongitudinalMemoryEmbedder` | Sets `COMPLETE` without embedding/`caller_id` keying/`metadata.type=caller_memory`. Phase 20 never calls it. Phase 11 erasure of memory vectors missing. | **High** |
| P23-H7 | Knowledge route | Hardcoded `total_chunks: 42`; not `include_router`’d; no upload endpoint. | **High** |
| P23-M1 | SpeculativeRetrieval | Missing “2 consecutive unchanged partials” gate; always retrieves immediately; no cancel/timeout task. | **Medium** |
| P23-M2 | Tool vs RAG priority | Spec File 6 §4 / §7 — unimplemented in orchestrator. | **Medium** |
| P23-M3 | PDF chunker | Splits pre-supplied text; no pdfplumber/pymupdf. | **Medium** |
| P23-M4 | Tenant isolation tests | Only prove dict filtering — not SQL/RLS. | **Medium** |
| P23-M5 | HIPAA cloud block | Policy-only; not enforced at retrieve/ingest call sites. | **Medium** |

#### Phase 23 tests

File: `voice_engine_plan/tests/phase_tests/test_phase_23_realtime_rag.py`  
**Depth:** Surface / in-memory. Missing: live pgvector/RLS; non-blocking; tool-over-RAG; DATA-framed; retrieve p95; Levenshtein boundary assertions.

---

### Phase 24 — Latency Budget Enforcement & SLO — **Needs Fix**

#### Deliverable inventory (summary)

| Spec / expected | Actual | Status |
|---|---|---|
| Waterfall / collector / slo_policy / demotion / playback | `core/latency/` | Models present; integration incomplete |
| `budgets/default.yaml` | same | Exists / unwired |
| Latency hooks | `worker_raw/orchestration/latency_hooks.py` | Stubbed; unused by pipeline |
| Benchmark harness | `tests/latency-benchmarks/` (+ duplicate under core) | Percentile math only; fixtures missing |
| S2S waterfall docs | `docs/latency/S2S_WATERFALL_LATER.md` | Intentional `[LATER]` OK |

#### Findings

| ID | Component | Gap / Anomaly | Severity |
|---|---|---|---|
| P24-H1 | `core/latency/demotion.py` | Spec/CHANGELOG: rolling **p50**, N=5, opt-in `enforce_demotion`. Impl: consecutive single-turn counters. Does **not** update Phase 06 `FailoverRouter` / `ProviderHealthState.priority_index`. | **High** |
| P24-H2 | `LatencyCollector` | Never calls `demotion_rule`; orphaned from collection path. | **High** |
| P24-H3 | Phase 17 wiring | `pipeline.py` has zero latency hooks; stage stamps never recorded. `LatencyHooks.start_turn` only. | **High** |
| P24-H4 | Phase 25 breach | No emit of `LATENCY_SLO_BREACH` / AlertRouter. Collector only appends strings to `warnings_emitted`. | **High** |
| P24-H5 | Phase 07 metrics | `ucve_turn_latency_ms` never observed; no WS `metric` emit. | **High** |
| P24-H6 | Cross-contract with Phase 06 | Hooks exist for demotion writes; never written. | **High** |
| P24-M1 | Stage budgets | `StageBudget` / `default.yaml` unused in `record_turn`. | **Medium** |
| P24-M2 | Playback / e2e | TTS-first-byte used for `total_e2e_ms` then SLO-gated — violates “logging gap only / excluded from SLO gate”. No 2s timeout path. | **Medium** |
| P24-M3 | `SLOPolicy` loader | No Phase 08 tenant JSONB load. | **Medium** |
| P24-M4 | Benchmark fixtures | `tests/latency-benchmarks/fixtures/` missing; harness not scripted audio→providers. Dual harness copies drift risk. | **Medium** |

#### Phase 24 tests

File: `voice_engine_plan/tests/phase_tests/test_phase_24_latency_slo.py`  
**Depth:** Surface unit. Missing: FailoverRouter assertion; PHI-in-trace check; collector overhead; Prometheus; Phase 08 load.

---

### Phase 25 — Error Taxonomy & Alerting — **Needs Fix**

#### Deliverable inventory (summary)

| Spec / expected | Actual | Status |
|---|---|---|
| `core/errors/codes.py` | same | Mostly complete; `QUOTA_SOFT_WARN` missing as enum member |
| structured / client_mapper / redaction | same | Partial maps |
| `dlq.py` | same | In-memory stub |
| `alert_router.py` | same | Email/webhook stubs |
| `014_dead_letter_queue.sql` | same | Unused by repo |
| `control_plane/routes/alerts.py` | same | Echo stub; **unmounted** |
| `worker_jobs/dlq_retry_sweeper.py` | same | Fake retry (attempt++) |

#### Findings

| ID | Component | Gap / Anomaly | Severity |
|---|---|---|---|
| P25-H1 | `AlertRouter.route_alert` (~L36–48) | Email/webhook stubs set flags only — no SMTP, no HMAC HTTP. Spec: warn→Phase 07 metric; critical→Phase 12 audit + email — **neither wired**. | **High** |
| P25-H2 | `DeadLetterQueueRepository` | In-memory; migration 014 unused; post-call never enqueues on failure. | **High** |
| P25-H3 | `DLQRetrySweeper.run_sweep` | Only `job.attempts += 1` — no dispatch callback, no exponential backoff. | **High** |
| P25-H4 | Quota soft warn | `QuotaEnforcer` sets `is_soft_cap_warn` only. `QUOTA_SOFT_WARN` absent from `codes.py`. Never fires AlertRouter. | **High** |
| P25-H5 | `LATENCY_SLO_BREACH` | Code exists; Phase 24 never produces/consumes via AlertRouter. | **High** |
| P25-H6 | Middleware | No conversion of `UCVEError` → `StructuredError` / sanitized API JSON in control plane. | **High** |
| P25-H7 | Cross-wiring | Phases 07/12/14/24 contracts for alerts unmet. | **High** |
| P25-M1 | `ERROR_CODE_HTTP_STATUS_MAP` | Missing several codes → silent 500 fallback (`BARGE_IN_FAILED`, `DATA_CLASSIFICATION_BLOCKED`, `CALLER_ID_MISSING`, `REVIEW_REQUIRED`, `LATENCY_SLO_BREACH`, etc.). | **Medium** |
| P25-M2 | `GENERIC_CLIENT_MESSAGES` | Incomplete map → generic fallback for many codes. | **Medium** |
| P25-M3 | `UCVE_DEBUG_ERRORS` | Debug header for correlation_id not implemented. | **Medium** |
| P25-M4 | `DeadLetterJob` | Missing `last_attempt_at` (spec schema). | **Medium** |
| P25-M5 | Alerts route | Not registered; non-persistent echo. | **Medium** |
| P25-M6 | Severity routing | `warn` has no log/metric path; email only flagged on error/critical without send. | **Medium** |
| P25-L1 | Redaction | Key-set only; PHI in free-text `message` may leak into alert payload. | **Low** |

#### Phase 25 tests

File: `voice_engine_plan/tests/phase_tests/test_phase_25_error_alerting.py`  
**Depth:** Surface. Missing: each code→HTTP; real DLQ from post-call; quota soft-warn→AlertRouter; email channel; log vs WS correlation_id split.

---

## 3. Actionable Remediation Plan

### Wave A — Security & admission (block deploy until done)

1. Split Ed25519 vs HMAC secrets in `verify_telnyx_signature`; remove public-key-as-HMAC fallback; fail closed if key unset.
2. Reject unknown DIDs; load from DB with RLS; remove default-tenant fail-open.
3. Mount telephony / extraction / knowledge / alerts routers with Phase 13 auth.
4. Add `telephony_gateway` and `post_call` to uv workspace members.

### Wave B — Phase 17 bridges

1. `InboundTelephonySessionHandler` → wrap PCM as `AudioFrame` → `PipelineOrchestrator.process_frame` / `run_turn`.
2. Set `transport_type=sip` + `CallerIdContext` on session config; record `TELEPHONY_SEC` on close.
3. Inject `PipelineToolHandler` + FSM tool events; inject speculative RAG into prompt assembly.
4. Call `LatencyHooks` per stage; on disconnect enqueue `PostCallPipeline`.

### Wave C — Real persistence & isolation

1. SQL `PostgresCallRecordRepository` with idempotent `ON CONFLICT`; S3 upload when recording required.
2. Wire Phase 10/11 recording / redaction / zero-retention.
3. Fix migration 013: embedding column + HNSW + RLS + agent scope; real `PgVectorRetriever` SQL; add `worker_jobs/kb_ingestion.py`.
4. DLQ + review queue + webhook targets from Postgres; vault-resolve trunk/MCP/webhook secrets.
5. Add RLS to telephony DIDs, sip_trunks, call_records, extraction/webhook/review tables.

### Wave D — Declared runtime behavior

1. `WebhookDispatcher`: real HTTP, 3× exponential backoff, idempotency key store, DLQ + AlertRouter on final failure.
2. BAA from Phase 10 profile; LLM extraction via FailoverRouter; CRM payload includes `verified`.
3. Real MCP HTTP/SSE transports; timeout → TTS filler + `ToolTimeoutFallback` + audit events.
4. Demotion: rolling p50 over N=5; when `enforce_demotion` update Phase 06 `priority_index`; breach → `LATENCY_SLO_BREACH` → AlertRouter.
5. Implement AlertRouter SMTP + HMAC webhook + Phase 07 metrics + Phase 12 audit; wire quota soft-warn.
6. Deepen all §7 phase tests; keep Phases 00–17 green.

### Regression guard (Phases 00–17)

- Do not change locked Phase 00–17 contracts without changelog.
- Contract tests: telephony/MCP/RAG/post-call must call into the same `PipelineOrchestrator` / FSM / metering / compliance types already locked.
- Re-run full phase suite 00–25 after each wave.

---

## 4. Verification & Testing Protocol

### 4.1 Current surface suite (baseline)

```bash
python -m pytest ^
  voice_engine_plan/tests/phase_tests/test_phase_18_telephony_sip_base.py ^
  voice_engine_plan/tests/phase_tests/test_phase_19_telephony_abstraction.py ^
  voice_engine_plan/tests/phase_tests/test_phase_20_post_call_record_schema.py ^
  voice_engine_plan/tests/phase_tests/test_phase_21_crm_dispatch.py ^
  voice_engine_plan/tests/phase_tests/test_phase_22_mcp_tooling.py ^
  voice_engine_plan/tests/phase_tests/test_phase_23_realtime_rag.py ^
  voice_engine_plan/tests/phase_tests/test_phase_24_latency_slo.py ^
  voice_engine_plan/tests/phase_tests/test_phase_25_error_alerting.py -v

python voice_engine_plan/scripts/verify_plan_integrity.py
```

### 4.2 Must-add integration assertions before production

| Phase | New assertions |
|---|---|
| 18 | Invalid signature + unset key rejected; unknown DID rejected; μ-law inbound completes one orchestrator turn; `telephony_sec` incremented; route mounted returns 401/403 without auth |
| 19 | DirectSIP adapter yields 16 kHz frames to mock pipeline; unhealthy primary fails over with audit event; stub trunks never report healthy without probe |
| 20 | SQL idempotent save; HIPAA missing recording rejected; standard disable recording succeeds; zero-retention omits raw; pipeline disconnect enqueues CallRecord |
| 21 | Mock receiver verifies HMAC; 3 failures → DLQ; BAA false blocks HIPAA extract; review approve then single dispatch; payload includes `verified` |
| 22 | Real transport mock round-trip; timeout triggers TTS fallback + audit; concurrent tool calls serialize; vault miss fail-closed |
| 23 | Cross-tenant SQL/RLS deny; embedding similarity retrieve; speculative reuse at ≤0.08 and re-query above; non-blocking when retrieve slow |
| 24 | Stage stamps from live pipeline; rolling p50 demotion updates FailoverRouter when opt-in; Prometheus `ucve_turn_latency_ms` observed; breach alerts |
| 25 | Every error code → HTTP status; soft quota warn → AlertRouter; DLQ Postgres insert from failed dispatch; sweeper retries with backoff then expires at 30d |

### 4.3 Tracker recommendation

Set Phases 18–25 to `IN_PROGRESS` (or `READY_FOR_MANUAL_TEST` where live Telnyx/LiveKit credentials are required) until Waves A–D and deepened §7 tests pass. **Do not use current `COMPLETED` as a production gate.**

---

## 5. Master Fix Checklist (~50 items)

Use this as the working backlog. Check off when fixed **and** verified.

### Wave A — Security & admission

- [ ] **FIX-001** — `telephony_gateway/telnyx/signature.py`: Ed25519-only OR separate HMAC secret; never HMAC with public key; no bare `except Exception: pass`
- [ ] **FIX-002** — `telephony_gateway/telnyx/webhook.py`: fail closed when public key / secret unset
- [ ] **FIX-003** — `telephony_gateway/resolver/sip_participant_resolver.py`: reject unknown DID; query DB; remove DEFAULT_TENANT fail-open
- [ ] **FIX-004** — Remove hardcoded default caller/callee fabrication in Telnyx webhook handler
- [ ] **FIX-005** — Mount `control_plane/routes/telephony.py` with Phase 13 auth
- [ ] **FIX-006** — Mount extraction / knowledge / alerts routers with auth
- [ ] **FIX-007** — Add `telephony_gateway` + `post_call` to uv workspace / packaging

### Wave B — Pipeline bridges

- [ ] **FIX-008** — Wire DirectSIP PCM → `AudioFrame` → `PipelineOrchestrator`
- [ ] **FIX-009** — Extend `PipelineSessionConfig` with `transport_type` + `caller_id`; set `sip` on telephony mint
- [ ] **FIX-010** — Emit `telephony_sec` metering on inbound session close
- [ ] **FIX-011** — Inject `PipelineToolHandler` + FSM `TOOL_EXECUTING` into `run_turn`
- [ ] **FIX-012** — Inject `SpeculativeRetrieval` / RAG context into prompt assembly (non-blocking)
- [ ] **FIX-013** — Wire `LatencyHooks` stage stamps into pipeline
- [ ] **FIX-014** — On disconnect, enqueue `PostCallPipeline` / assemble+persist CallRecord

### Wave C — Persistence & isolation

- [ ] **FIX-015** — Real SQL `PostgresCallRecordRepository` with `ON CONFLICT` idempotency
- [ ] **FIX-016** — S3 (or Phase 08 object client) upload when recording required
- [ ] **FIX-017** — Fix `RecordingPolicy.validate_record` to pass tenant_config; standard disable works
- [ ] **FIX-018** — Phase 11 redaction / zero-retention path in assembler+enqueue
- [ ] **FIX-019** — Expand `011_call_records.sql` fields + RLS; align with Phase 08 transcript/recording tables
- [ ] **FIX-020** — RLS on `009_telephony_dids.sql` / resolve migration number collision
- [ ] **FIX-021** — Load `010_sip_trunks` into failover router; RLS; vault-resolve `credentials_ref`
- [ ] **FIX-022** — Fix `013_knowledge_base_pgvector.sql`: embedding column, HNSW, RLS, agent scope
- [ ] **FIX-023** — Real `PgVectorRetriever` SQL (not keyword mock)
- [ ] **FIX-024** — Add `worker_jobs/kb_ingestion.py` + embed via EmbedderPolicy→provider chain
- [ ] **FIX-025** — Persist HumanReviewQueue / webhook targets / DLQ to Postgres (`012`, `014`)
- [ ] **FIX-026** — RLS on extraction_schemas / webhook_targets / human_review_queue / call_records / sip_trunks

### Wave D — Declared behavior

- [ ] **FIX-027** — `WebhookDispatcher`: HTTP client, 3× exponential backoff, idempotency store
- [ ] **FIX-028** — On final webhook failure: DLQ insert + AlertRouter
- [ ] **FIX-029** — ExtractionService: real LLM via Phase 06; BAA from Phase 10 profile (default deny)
- [ ] **FIX-030** — CRM payload includes `verified`; block raw audio URLs without consent
- [ ] **FIX-031** — Apply clinic_timezone in datetime verification; normalize phones before dispatch
- [ ] **FIX-032** — Real MCP HTTP/SSE transports; stdio subprocess when enabled
- [ ] **FIX-033** — Vault-resolve MCP `credentials_ref`; enforce `allowed_tools`; HIPAA MCP block
- [ ] **FIX-034** — Timeout → `ToolTimeoutFallback` + TTS filler + Phase 12 audit events
- [ ] **FIX-035** — Serial tool execution with `asyncio.Lock`; concurrent-server cap
- [ ] **FIX-036** — SpeculativeRetrieval: 2 consecutive partials gate; cancel/timeout; tool-over-RAG priority
- [ ] **FIX-037** — Longitudinal memory real embed + Phase 20 hook + Phase 11 erasure path
- [ ] **FIX-038** — Demotion: rolling p50 (N=5); update FailoverRouter when `enforce_demotion`
- [ ] **FIX-039** — LatencyCollector: wire demotion; observe `ucve_turn_latency_ms`; per-stage budgets from YAML
- [ ] **FIX-040** — SLO breach → `LATENCY_SLO_BREACH` → AlertRouter; exclude TTS-first-byte from SLO gate
- [ ] **FIX-041** — `SLOPolicy` load from Phase 08 tenant config
- [ ] **FIX-042** — AlertRouter: real email + HMAC webhook; warn→metric; critical→audit+email
- [ ] **FIX-043** — Add `QUOTA_SOFT_WARN`; wire QuotaEnforcer soft-cap → AlertRouter
- [ ] **FIX-044** — Control-plane middleware: `UCVEError` → sanitized `StructuredError` JSON
- [ ] **FIX-045** — Complete HTTP status + client message maps for all `UCVEErrorCode`s; `UCVE_DEBUG_ERRORS`
- [ ] **FIX-046** — DLQ sweeper: real retry callback + exponential backoff + 30d expiry; add `last_attempt_at`
- [ ] **FIX-047** — Adapter health: real OPTIONS/ping; stubs must not report healthy forever; DirectSIP `receive_audio` yields frames
- [ ] **FIX-048** — Fix `BaseTelephonyTransport` abstract method signatures (`self`); failover audit events
- [ ] **FIX-049** — Deepen phase tests 18–25 to cover §7 asserts listed in §4.2
- [ ] **FIX-050** — Re-open EXECUTION_TRACKER 18–25 to IN_PROGRESS; mark COMPLETED only after Waves A–D green + integrity script OK

### Intentional / deferrable (do not block Wave A unless misused)

- [ ] **LATER-01** — LiveKit real media path (flag currently fake-success — at least fail closed when enabled without creds)
- [ ] **LATER-02** — Twilio Media Stream / WhatsApp / Qdrant / FollowUpTrigger / S2S waterfall docs — per-spec `[LATER]` OK if not selected in prod paths
- [ ] **LATER-03** — Memory embed status enum stub until longitudinal embedder ships (FIX-037)

---

## 6. Highest-impact file index (quick jump)

| Priority | Path |
|---|---|
| P0 | `telephony_gateway/telnyx/signature.py` |
| P0 | `telephony_gateway/telnyx/webhook.py` |
| P0 | `telephony_gateway/resolver/sip_participant_resolver.py` |
| P0 | `worker_raw/telephony/inbound_handler.py` |
| P0 | `control_plane/app.py` (mount routers) |
| P0 | `worker_raw/orchestration/pipeline.py` (all bridges) |
| P0 | `core/db/repos/call_record_repo.py` |
| P0 | `post_call/webhook/dispatcher.py` |
| P0 | `core/mcp/host.py` + transports |
| P0 | `core/rag/retriever.py` + `infra/db/migrations/013_knowledge_base_pgvector.sql` |
| P0 | `core/latency/demotion.py` + `collector.py` |
| P0 | `core/errors/alert_router.py` + `dlq.py` |

---

## 7. Related artifacts

- Live IDE canvas: `C:/Users/hamza/.cursor/projects/d-PROJECTS-PASSION-PROJECTS-VERTEX-voiceai/canvases/phases-18-25-production-audit.canvas.tsx`
- Project canvas copy: [`phases-18-25-production-audit.canvas.tsx`](./phases-18-25-production-audit.canvas.tsx)
- Plan trackers: `voice_engine_plan/implementation_plan/EXECUTION_TRACKER.md`, `voice_engine_plan/tests/phase_tests/TEST_TRACKER.md`
- Changelog: `voice_engine_plan/CHANGELOG_PLAN.md`
