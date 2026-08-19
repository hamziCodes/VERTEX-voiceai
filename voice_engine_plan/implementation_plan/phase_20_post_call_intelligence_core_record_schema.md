# Phase 20: Post-Call Intelligence Core Record Schema

## 1. Executive Summary & Core Logic

Define the canonical `CallRecord` and related models persisted after every session: diarized turns, recording pointers, disposition, extraction payload placeholders, verification issues, and compliance metadata. Generalizes awaazlabs Retell webhook persistence shape (`legacy_codebases/awaazlabs/ali-Awaazlabs-client-dashboard-backend/supabase/functions/retell-webhook/index.ts`) but sourced from **UCVE's own FSM** (Phase 03) rather than external Retell events. Feeds Phase 21 extraction/dispatch and Phase 23 RAG memory. Depends on Phase 08 storage (JSONB + S3), Phase 11 redaction columns, Phase 07 correlation IDs.

**Recording policy:** required for `hipaa`/`gdpr_strict` tiers; **tenant-configurable** (on/off) for `standard` tier — ties to Phase 10 compliance tiers.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| Pydantic v2 record models | Validation at persistence boundary |
| FSM-derived diarization | File 05 §2 — "free" from state transitions vs ML diarization |
| S3 URI for recordings | Phase 08 decision |
| Idempotent `call_id` key | Webhook + CRM retry safety (Phase 21) |
| Dual-channel default | Post-call QA and speaker separation |

**Reference docs:** blueprint File 05 §2–5; habiba session shutdown transcript JSONB (`worker/main.py` persist path, AUDIT_04 §3).

## 3. What / How / Why

- **What:**
  - `DiarizedTurn`: `{speaker, text, start_ms, end_ms, language, confidence}` — language from Phase 15 per turn
  - `CallRecording`: `{recording_s3_uri, dual_channel, duration_sec, checksum}` — **`dual_channel=True` default** (agent/caller separated when transport supports it; mono WS falls back to FSM-boundary diarization per File 05 §2 note)
  - `CallRecord`: `{call_id, tenant_id, agent_id, session_id, caller_id, started_at, ended_at, end_reason, transport_type, disposition, turns, recording, transcript_redacted_ref, transcript_raw_ref, compliance_tier, metrics_snapshot, memory_embed_status}` — **`caller_id`:** E.164 string from Phase 18 `CallerIdContext.from_number` when telephony-origin; `null` for native WS sessions without PSTN context
  - **`memory_embed_status`:** stub enum `{pending, skipped, complete, failed}` — unused in v1 but reserved for Phase 23 longitudinal memory / RAG dependency (File 5 §8)
  - `RecordingPolicy`: resolved from Phase 10 tier — `hipaa`/`gdpr_strict` → recording required; `standard` → tenant JSONB override `recording_enabled: bool` (default true, can disable)
  - `CallDisposition` enum — File 05 §5 (appointment_booked, needs_followup, escalated_human, etc.)
  - `VerificationIssue` placeholder list — populated Phase 21
  - `PostCallPipeline.enqueue(call_record)` — async job trigger
- **How:** Phase 17 disconnect handler assembles turns from FSM transition log + STT/LLM history. **`caller_id`** copied from session config populated by Phase 18 `CallerIdContext` at SIP admission (required for telephony sessions per Phase 18; optional/null for WS-only). Apply Phase 11 redaction before persist. Store redacted JSONB always; raw encrypted per tier. Upload recording blob to S3 when policy requires (Phase 08 client). Insert `call_records` row (migration this phase). Set `memory_embed_status=pending` stub. Emit Phase 12 audit `call_record_created`.
- **Why this approach:** awaazlabs CRM depends on post-call structured records but owns no voice engine (AUDIT_02). UCVE must own the record format. Retell coupling rejected. Dual-channel default supports QA and extraction quality. Alternative: mono-only — insufficient for telephony dispute resolution.

## Deliverables

- `post-call/__init__.py`
- `post-call/models/call_record.py`
- `post-call/models/diarized_turn.py`
- `post-call/models/disposition.py`
- `post-call/models/recording.py` — dual-channel default + tier policy
- `post-call/models/memory_embed.py` — stub status enum
- `post-call/pipeline/enqueue.py` — `PostCallPipeline`
- `post-call/pipeline/assembler.py` — build record from session state
- `post-call/pipeline/recording_policy.py` — tier-driven required/optional
- `infra/db/migrations/011_call_records.sql` — includes `caller_id VARCHAR(20)` nullable (E.164)
- `core/db/repos/call_record_repo.py`

## 4. Compute & Resource Profile (if applicable)

Assembly: ~10–50 ms per call (JSON serialize + DB insert). S3 upload async — don't block worker; dual-channel ~2× mono size — 2–10 MB/min audio typical. Record row ~50 KB with turns.

## 5. Compliance Notes (if applicable)

`CallRecord` is PHI for healthcare — encryption at rest (Postgres + S3 SSE). Raw transcript pointer omitted for zero-retention tenants (Phase 11). HIPAA tier: recording required — non-compliance fails persist gate. Disposition and metrics contain no direct PHI. Access via Phase 13 RBAC + Phase 12 audit on view/export.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Recording tiers:** **required** for `hipaa`/`gdpr_strict`; **tenant-configurable** for `standard` (Phase 10 tie-in).
2. **Mono vs dual-channel:** **dual-channel default** when transport supports separation; FSM fallback for mono WS.
3. **Longitudinal memory vectors:** **`memory_embed_status` stub field now** — Phase 23 dependency.
4. **`caller_id` on CallRecord:** **required field on model** — populated from Phase 18 `CallerIdContext` (E.164) for SIP sessions; nullable for WS-only sessions.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_20_post_call_record_schema.py`
- **Asserts:** CallRecord validates; turns ordered by time; redacted-only persist for zero-retention fixture; idempotent insert on duplicate call_id; assembler builds from mock FSM log; **`caller_id` populated from CallerIdContext fixture (E.164 format); WS session allows null caller_id**; S3 URI stored when recording required; HIPAA fixture rejects missing recording; standard tenant can disable recording; `dual_channel=True` default; `memory_embed_status` present defaulting to `pending`.
- **Pass threshold:** 100% model + assembler tests.
- **Latency target:** assemble+enqueue < 100 ms excluding S3 upload.
