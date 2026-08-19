# Phase 18: Telephony/SIP Base Integration (Telnyx + Direct SIP Sovereign Path)

## 1. Executive Summary & Core Logic

Productize inbound PSTN admission: Telnyx webhooks, DID→agent resolution, μ-law↔PCM16 transcoding, and **DirectSIPTransport** piping into the **same Phase 17 pipeline**. Harvests `legacy_codebases/habiba-sdk-agent/tenant_portal_api/telephony_routes.py`, `telephony_webhooks.py`, `worker/telephony_runtime.py`, and TypeScript signing helpers `telephony/src/routes.ts` for webhook auth and DID resolution patterns — but **exit criteria follow sovereign-first architecture**, not habiba's LiveKit-coupled media path.

> **Architecture correction (resolved):** An earlier draft flagged "LiveKit required for exit test." That contradicted Stage 1 ingestion and blueprint File 09 Phase 3: *"Sovereign path (native WS + Direct SIP) ships first without LiveKit"* and *"inbound PSTN reaches the same pipeline core as native WS … **without requiring LiveKit**."* **Correct policy:** Phase 18 exit test validates **Telnyx webhook → DirectSIPTransport → Phase 17 `PipelineOrchestrator`**. `LiveKitSIPTransport` may exist as an **optional convenience adapter** (habiba harvest) but is **not** an exit gate and must not be required in CI.

**Scope:** inbound-only for v1; outbound dial deferred. **Caller ID (E.164)** propagation to session context is **required** — clinic/hospital clients need call context for Phase 21 extraction.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| Telnyx webhook signature verify | habiba `telephony_webhooks.py` public-key pattern |
| **`DirectSIPTransport` (primary exit path)** | File 09 Phase 3; File 01 §3.6 sovereign plane |
| `LiveKitSIPTransport` (optional) | habiba production convenience — not orchestrator |
| `TelephonyTranscoder` at adapter edge | File 07 §2.1 — pipeline sees 16 kHz PCM16 only |
| 20 ms → 512 sample rebuffer | File 07 §2.2 |

**Reference docs:** blueprint File 07 §4.1; File 09 §2 Phase 3 exit criteria; habiba `docs/TELEPHONY_API_AND_SCHEMA_CONTRACT.md`.

## 3. What / How / Why

- **What:**
  - `TelnyxWebhookHandler`: inbound call events, signature validation (fail closed — contrast awaazlabs Retell fail-open)
  - `SIPParticipantResolver`: DID → `(tenant_id, agent_id)` — habiba chain: dispatch job → SIP DB → JWT metadata (`AUDIT_04 §3` step 9)
  - **`DirectSIPTransport` (exit gate):** RTP/SIP media leg → `TelephonyTranscoder` → normalized PCM to Phase 17 orchestrator — **no LiveKit room required**
  - `LiveKitSIPTransport` adapter (optional): bridges SIP audio into room → normalized PCM — convenience only; feature-flagged `UCVE_ENABLE_LIVEKIT_SIP=false` default
  - `TelephonyTranscoder`: μ-law 8 kHz ↔ PCM16 16 kHz; outbound downsample for PSTN egress (inbound path only in v1)
  - **`CallerIdContext`:** E.164 `from_number` attached to session config — available to Phase 20 assembler and Phase 21 extraction
  - Telephony session mint: extends Phase 13 — telephony-origin sessions tagged `transport_type=sip`
  - Emit `telephony_sec` usage (Phase 14 kind registered)
  - **Outbound dial:** `[LATER]` — habiba `telephony_service.py:999–1183` exists but not v1 scope
- **How:** Telnyx webhook hits `telephony-gateway/telnyx/webhook.py` → resolve agent → mint internal session → attach **DirectSIP** media leg → pipe audio into `PipelineOrchestrator`. **FSM and barge-in remain Phase 03/04** — SFU hints (if LiveKit optional leg active) do not bypass `BargeInController`. Credentials from Phase 09 vault (`telnyx` provider ID; `livekit` only if optional adapter enabled).
- **Why this approach:** Only legacy repo with real PSTN (`habiba`). Re-deriving webhook auth from scratch wastes audited patterns. Sovereign Direct SIP satisfies File 01 §3.6 — LiveKit must not be the only PSTN path. Alternative: LiveKit-first exit — **rejected** (architecture correction above).

## Deliverables

- `telephony-gateway/__init__.py`
- `telephony-gateway/telnyx/webhook.py`
- `telephony-gateway/telnyx/signature.py`
- `telephony-gateway/transcoding/mulaw.py` — G.711 tables
- `telephony-gateway/transcoding/rebuffer.py`
- `telephony-gateway/resolver/sip_participant_resolver.py`
- `core/transport/direct_sip.py` — **`DirectSIPTransport` (primary)**
- `core/transport/livekit_sip.py` — optional adapter (not exit gate)
- `core/transport/caller_id.py` — `CallerIdContext`
- `worker-raw/telephony/inbound_handler.py`
- `infra/db/migrations/009_telephony_dids.sql` — DID inventory
- `tenant-portal-api/telephony_routes.py` — port habiba route shapes (inbound-only v1)
- `docs/telephony/SOVEREIGN_PATH_EXIT_CRITERIA.md` — explicit LiveKit-not-required statement

## 4. Compute & Resource Profile (if applicable)

Transcoding: ~0.05 ms per 20 ms telephony frame on CPU. Direct SIP avoids LiveKit ~20–40 ms SFU hop — preferred for latency-sensitive tenants. LiveKit SIP (optional) adds ~20–40 ms — acceptable when enabled. Telnyx webhook handler < 50 ms before audio path starts.

## 5. Compliance Notes (if applicable)

Call recordings from PSTN are PHI for healthcare tenants — Phase 08 S3 storage with encryption. Telephony metadata (caller ID) is PII — Phase 11 redaction before CRM export (Phase 21). Telnyx as subprocessor — Phase 10 registry entry required. LiveKit subprocessor entry only if optional adapter enabled per tenant.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions (includes architecture correction):

1. **Exit test path:** validates **sovereign path** — Telnyx + **DirectSIPTransport** + Phase 17 pipeline; **LiveKit not required** (prior "LiveKit required" recommendation superseded).
2. **Caller ID propagation:** **required** — E.164 in `CallerIdContext` for session/extraction.
3. **Outbound dial:** **inbound-only for v1**; outbound deferred `[LATER]`.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_18_telephony_sip_base.py`
- **Asserts:** webhook signature verify pass/fail; DID resolves tenant+agent; transcoder 8↔16 kHz length correct; **inbound call via DirectSIP reaches Phase 17 mock pipeline with LiveKit unconfigured**; invalid signature rejected; telephony_sec meter incremented; caller ID present in session context; optional LiveKit adapter skipped when flag false.
- **Pass threshold:** inbound PSTN simulation completes one turn on DirectSIP path without LiveKit.
- **Latency target:** webhook-to-first-audio budget +100 ms vs WS baseline (PSTN leg overhead).
