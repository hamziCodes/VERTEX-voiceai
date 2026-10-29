# Phase 12 — Telnyx Telephony

**Status:** IN PROGRESS — 12A–12E COMPLETE; NEXT 12F

**Goal:** Connect inbound and controlled single-call outbound Telnyx calls to the same production voice pipeline used by the web agent, with secure carrier admission, durable call identity, bidirectional media, low-latency interruption, exact metering, and deterministic cleanup.

**Depends on:** Phases 04, 07, and 09. Phase 11D must close before Phase 12D can claim complete post-call and privacy behavior.

**Audit coverage:** T01–T06.

## Approved product boundary

Hamzi has established that Wavia includes both the web voice agent and a calling agent through Telnyx. Phase 12 uses this sequence:

1. Telnyx is the first production carrier.
2. Secure inbound calling is implemented and proven offline first.
3. Controlled one-call outbound calling follows on the same lifecycle and media contracts.
4. Batch campaigns, predictive dialing, contact-list ingestion, and automatic bulk retries are excluded. They require a separate product, consent, compliance, spend, and abuse-control plan.
5. No live call, number purchase, deployment, or paid carrier request occurs without the Phase 15 approval gate.

## Architecture decision

Use **Telnyx call control plus a bidirectional carrier media WebSocket** as the v1 carrier boundary. The gateway owns webhook verification, call commands, stable call state, and the carrier media socket. The worker continues to own VAD → STT → LLM/tools → TTS, interruption, metering, and post-call finalization.

This is the recommended path because it reuses the existing asynchronous WebSocket pipeline and lets the carrier own PSTN/SIP signaling and RTP. Implementing a complete SIP user agent, SDP negotiation, UDP/RTP sockets, NAT traversal, jitter buffering, retransmission policy, and carrier interoperability inside Wavia would add substantial operational risk without improving the agent product.

Existing `DirectSIPTransport` remains a useful μ-law codec/rebuffer primitive until the carrier-media adapter supersedes or wraps it. It must not be described as a complete SIP transport. LiveKit, Twilio, and generic PTA adapters remain unavailable unless independently implemented and qualified; placeholders must never report connected or healthy.

Before 12A code is written, confirm the exact current Telnyx signature, call-control command, media message, codec, sequence, and close-reason schemas from official Telnyx documentation. Freeze sanitized JSON fixtures in tests. No credential values belong in fixtures or documentation.

## Target data flow

```text
Inbound PSTN
  → Telnyx signed webhook
  → event replay check + stable call lookup
  → DID → tenant + published agent resolution
  → quota/admission + pinned runtime plan
  → Telnyx answer/start-media command
  → signed/unguessable media WebSocket admission
  → μ-law frames → canonical 16 kHz PCM
  → PipelineOrchestrator (VAD → STT → LLM/tools → TTS)
  → PCM → paced μ-law media messages → Telnyx → caller
  → hangup/disconnect → one finalize + metering + post-call job

Controlled outbound
  → authenticated tenant request + destination policy + idempotency
  → Telnyx create-call command
  → same webhook, media, pipeline, and finalization path
```

## Current reality recorded during prework

- `control_plane/routes/telephony.py` is mounted and fails closed when no verification material is configured, but its module-level handler is not wired to runtime configuration or durable storage.
- `telephony_gateway/main.py` exposes an unsigned normalization endpoint and must not admit calls.
- `TelnyxWebhookHandler` verifies before processing but creates a fresh session UUID per event, accepts a missing carrier call ID by inventing one, and does not persist or execute call commands.
- `SIPParticipantResolver` contains demo DID mappings, uses a mismatched database column name, swallows database errors, and is synchronous.
- `DirectSIPTransport` converts and rebuffers audio but has no signaling, carrier WebSocket, RTP socket, pacing, sequence, jitter, or actual network egress.
- `TelnyxDirectSIPAdapter.connect()` marks itself connected without a connection and `receive_audio()` always returns `None`.
- `InboundTelephonySessionHandler` passes canonical frames into `process_frame_async()` and meters duration, but does not perform complete session admission/start/finalization or wire carrier egress.
- Trunk routing treats unknown health as healthy and invents a default Telnyx trunk when durable configuration is empty.
- Existing tests pass but primarily assert primitives and placeholder behavior. They do not execute a signed webhook-to-audible-response call lifecycle.

## Implementation checkpoints

Each checkpoint starts with failing tests, ends with focused regression/static checks, receives its own implementation commit and evidence file, and updates `EXECUTION_TRACKER.md`. No checkpoint may weaken the explicit offline/live gates.

### 12A — Carrier contract and secure webhook boundary

**Create/modify:**

- `telephony_gateway/telnyx/{models,signature,webhook,fixtures}.py`
- `telephony_gateway/main.py`
- `control_plane/routes/telephony.py`
- `tests/telephony/test_telnyx_webhook_security.py`
- sanitized Telnyx fixtures under `tests/fixtures/telephony/`

**Work:**

- Define strict typed event models and an allowlist of supported Telnyx event names; reject unknown or malformed events.
- Verify the carrier signature over the exact raw request bytes. The public carrier endpoint uses Telnyx's verified scheme only; test-only HMAC helpers cannot be selected in production.
- Validate finite timestamp freshness and reject missing configuration, invalid encodings, tampering, future/stale timestamps, and malformed JSON.
- Remove or lock down the unsigned `/v1/telephony/webhook/{carrier}` normalization route. Establish one canonical carrier webhook owner.
- Load verification configuration through the existing credential/config boundary without logging it.
- Return quickly after durable event acceptance; never run the voice pipeline inline in the webhook request.

**Offline verification:**

```powershell
py -3.12 -m pytest tests/telephony/test_telnyx_webhook_security.py tests/hardening/test_remediation_r1_r7.py -q -p no:cacheprovider
```

**Human intervention:** none. Sanitized public protocol fixtures only; no account access or call.

**Completed:** implementation commit `45a60bf`; evidence: [`../evidence/phase-12a/VERIFICATION.md`](../evidence/phase-12a/VERIFICATION.md).

- The canonical gateway endpoint verifies Telnyx Ed25519 against the exact raw request bytes and finite five-minute timestamp window before JSON parsing.
- Missing configuration, malformed encodings, HMAC input, tampering, stale/future timestamps, unknown events, invalid phone numbers, and malformed envelopes fail closed.
- A typed event sink accepts each event ID once before the endpoint returns; duplicate delivery receives a safe 200 without repeated processing.
- The old unsigned generic gateway endpoint and duplicate control-plane webhook owner were removed.
- The production endpoint remains 503 until Phase 12B injects a durable PostgreSQL event sink. The in-memory sink is limited to deterministic offline tests.
- Official protocol details were frozen into a sanitized fixture; no account, credential, carrier request, or call was used.

### 12B — Durable call identity, DID resolution, and idempotent lifecycle

**Create/modify:**

- append-only telephony runtime migration after the current migration head
- `core/db/repos/telephony_repo.py`
- `telephony_gateway/resolver/sip_participant_resolver.py`
- `telephony_gateway/telnyx/webhook.py`
- `tests/telephony/test_call_lifecycle.py`
- `tests/db/test_phase12b_live_telephony.py`

**Work:**

- Persist carrier event ID, call-control ID, direction, tenant, agent, internal session ID, state, timestamps, disconnect reason, and command idempotency keys.
- Map every event for one carrier call to one internal session. Atomically reject duplicate event IDs while allowing valid reordered lifecycle events.
- Resolve normalized E.164 DIDs against durable tenant-scoped data and a published agent. Unknown/inactive DIDs and ownership mismatches fail closed.
- Remove demo mappings, fabricated call IDs, swallowed database errors, and default trunks.
- Make state transitions explicit and monotonic: received → admitted → answered → media_active → ending → ended/failed.
- Keep webhook event receipt separate from executed carrier commands so retries cannot duplicate answer, media-start, hangup, usage, or post-call jobs.
- Apply canonical RLS policies to telephony DID, trunk, call, event, and command data. Do not edit an already-applied migration to achieve this.

**Offline verification:**

```powershell
py -3.12 -m pytest tests/telephony/test_call_lifecycle.py -q -p no:cacheprovider
# Then run the documented disposable PostgreSQL Phase 12B command.
```

**Human intervention:** Hamzi may run the disposable PostgreSQL verification command. Shared database migration remains separately approved.

**Completed:** implementation commit `4d8bf04`; evidence:
[`../evidence/phase-12b/VERIFICATION.md`](../evidence/phase-12b/VERIFICATION.md).

- Durable PostgreSQL admission now maps one Telnyx call-control ID to one internal
  session, accepts each event ID once, and records reordered events without state
  regression.
- DID admission requires an active tenant-owned E.164 binding and the agent's
  current immutable published version. Demo mappings and silent fallbacks are gone.
- Commands have a separate durable idempotency ledger; no carrier command is
  executed in this checkpoint.
- Canonical RLS and composite ownership constraints cover DIDs, trunks, calls,
  events, and commands. The disposable PostgreSQL proof passed and was removed.
- No shared migration, carrier request, provider traffic, paid action, or live call
  occurred.

### 12C — Bidirectional Telnyx media transport

**Create/modify:**

- `telephony_gateway/telnyx/media.py`
- `telephony_gateway/transcoding/{mulaw,rebuffer}.py`
- `telephony_gateway/adapters/telnyx_media_stream.py`
- `tests/telephony/test_telnyx_media.py`
- `tests/telephony/fake_telnyx.py`

**Work:**

- Implement an authenticated, call-bound media WebSocket with bounded queues and explicit open/start/media/DTMF/stop/error states.
- Decode inbound base64 μ-law payloads, preserve sequence/timestamp metadata, handle arbitrary fragmentation, and emit canonical 16 kHz mono PCM frames.
- Convert pipeline PCM to carrier format with a stateful filtered resampler, exact duration accounting, 20 ms framing where required, real-time pacing, and bounded backpressure.
- Define reorder, loss, duplicate, late-frame, silence-fill, slow-sink, and disconnect policies. Expose counters without storing audio or phone numbers in logs.
- Flush or discard codec buffers according to the close reason; never leak audio between calls.
- Keep raw SIP/RTP and LiveKit out of the v1 runtime path.

**Offline verification:**

```powershell
py -3.12 -m pytest tests/telephony/test_telnyx_media.py tests/audio -q -p no:cacheprovider
```

**Required measurements:** sample count and duration conservation; packet cadence; bounded queue depth; no leaked tasks; deterministic loss/reorder behavior; ingress-to-worker and worker-to-egress overhead percentiles from fake-clock tests.

**Human intervention:** none. Use generated PCM/μ-law and a local fake carrier only.

**Completed:** implementation commit `61ea1e7`; evidence:
[`../evidence/phase-12c/VERIFICATION.md`](../evidence/phase-12c/VERIFICATION.md).

- Added an authenticated, exact-URL-signed, call-bound Telnyx media WebSocket
  adapter with explicit connected/start/media/DTMF/mark/stop/error handling.
- Inbound PCMU is decoded and statefully resampled to canonical 16 kHz PCM;
  outbound PCM is statefully downsampled, encoded to PCMU, framed at 20 ms, and
  paced through a bounded queue.
- Reorder state is bounded for long calls. Duplicate, late, missing, oversized,
  malformed, identity-mismatched, and unexpected-disconnect cases have explicit
  fail-closed behavior and counters.
- Playback clear, partial-frame discard, callback failure, carrier stop, and
  disconnect cleanup close without leaked worker tasks or cross-call audio.
- Generated audio and a local fake carrier proved sample conservation, metadata,
  deterministic loss fill, queue bounds, packet cadence, and processing
  percentiles. No Telnyx account, carrier endpoint, provider, or live call was
  used.

### 12D — Full inbound pipeline, interruption, teardown, and post-call

**Create/modify:**

- `worker_raw/telephony/inbound_handler.py`
- `worker_raw/orchestration/pipeline.py` only where a transport-neutral lifecycle hook is missing
- telephony session supervisor/registry under `worker_raw/telephony/`
- `tests/telephony/test_inbound_pipeline.py`
- `tests/e2e/scenarios/test_telephony_inbound_e2e.py`

**Work:**

- Admit through the same quota, pinned agent-plan, provider credential, and session ownership rules as web voice.
- Warm STT before media readiness, start the durable call record, drive VAD/STT turns, and send real TTS bytes back through the carrier adapter.
- Preserve barge-in semantics: stop queued and carrier playback, cancel generation, keep the interrupting speech, and resume one consistent session.
- Propagate caller identity and `transport_type=telephony` without exposing phone numbers in ordinary logs.
- Make carrier hangup, tool-requested end, provider failure, media loss, worker shutdown, and timeout converge on one idempotent finalizer.
- Record exact telephony/agent/STT/TTS usage once and enqueue one post-call job. Use Phase 11 privacy/recording policy.

**Offline verification:**

```powershell
py -3.12 -m pytest tests/telephony/test_inbound_pipeline.py tests/e2e/scenarios/test_telephony_inbound_e2e.py tests/interruption tests/post_call -q -p no:cacheprovider
```

**Exit evidence:** a local fake-carrier conversation must prove nonempty audio traverses carrier ingress → VAD → STT → LLM → TTS → carrier egress; interruption works; duplicate hangups finalize once; all sockets, queues, provider sessions, and tasks close.

**Human intervention:** none. No carrier/provider traffic is needed; use deterministic fake providers.

**Completed:** implementation commit `49478ad`; evidence:
[`../evidence/phase-12d/VERIFICATION.md`](../evidence/phase-12d/VERIFICATION.md).

- Added one bounded session supervisor that owns authoritative-plan validation,
  admission lease/heartbeat, provider binding and STT warmup, Telnyx media,
  pipeline workers, published limits, usage, post-call finalization, and cleanup.
- Generated PCMU traverses the real VAD → batch STT → streaming LLM → streaming
  TTS pipeline and returns as nonempty paced PCMU through the fake carrier.
- Carrier clear integrates with the existing generation-based barge-in contract;
  canceling one turn leaves the worker alive and preserves the interrupting turn.
- Carrier stop/disconnect, tool end, provider-pipeline failure, worker shutdown,
  maximum duration, and maximum turns converge on one idempotent finalizer.
- Telephony, agent, STT, and TTS usage are recorded once. One privacy-aware call
  record and one post-call job are finalized, with caller identity stored in the
  record but absent from ordinary logs.
- The frozen Phase 18 DirectSIP codec/rebuffer constructor remains only for
  offline compatibility tests. It does not enter the production Telnyx path.
- No carrier/provider request, account access, live call, shared database, or
  paid action occurred.

### 12E — Controlled single-call outbound and new-call resilience

**Create/modify:**

- authenticated outbound command route/service
- `telephony_gateway/telnyx/client.py`
- destination/calling-window/spend/idempotency policy
- `tests/telephony/test_outbound_call.py`
- `tests/telephony/test_trunk_readiness.py`

**Work:**

- Allow one authenticated outbound call request with a tenant-owned published agent, E.164 destination, explicit purpose/consent record, destination allowlist, calling window, per-tenant concurrency/rate/spend caps, and idempotency key.
- Keep bulk lists and campaigns unavailable.
- Use typed bounded retries only before call creation is known. Reconcile ambiguous carrier responses by idempotency/call ID rather than blind redial.
- Treat unknown health, missing credentials, missing DID ownership, and unimplemented adapters as unavailable.
- Define failover only for new calls. Established calls fail and finalize honestly; no transparent mid-call carrier migration claim.
- Align actual management/runtime endpoints, configuration names, OpenAPI, SDK docs, and runbooks.

**Offline verification:**

```powershell
py -3.12 -m pytest tests/telephony/test_outbound_call.py tests/telephony/test_trunk_readiness.py tests/e2e -q -p no:cacheprovider
```

**Human intervention:** no call is placed here. Before any staging request, Hamzi must provide/confirm an allowed destination through local environment, maximum spend, permitted time window, and explicit live-run approval. Secret values never enter git or chat.

**Completed:** implementation commits `1cb234c` and `038cd64`; evidence:
[`../evidence/phase-12e/VERIFICATION.md`](../evidence/phase-12e/VERIFICATION.md).

- Added authenticated, tenant-scoped one-call creation with explicit purpose,
  consent, E.164 validation, destination allowlist, calling window, durable
  idempotency, and concurrency/rate/spend/duration ceilings.
- Added PostgreSQL RLS policy/request state, tenant-owned published-agent/DID/
  trunk resolution, privacy erasure coverage, and a tenant BYOK Telnyx client.
- `RUN_LIVE_TELEPHONY=1` is required before secret resolution or carrier I/O.
  Ambiguous responses are persisted and never blindly redialed.
- Unknown health, incomplete trunks, and unimplemented adapters fail closed;
  failover is new-call-only. Campaign and batch surfaces remain unavailable.
- Full forced-offline verification passed 929 tests with 13 expected skips.
  The disposable PostgreSQL execution is retained as the first Phase 12F gate
  because Docker Desktop was unavailable; no live call was placed.

### 12F — Offline close gate and separately approved live certification

**Offline close gate:**

```powershell
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_DB_TESTS='0'
$env:RUN_LIVE_REDIS_TESTS='0'
py -3.12 -m pytest tests/telephony tests/e2e/scenarios/test_telephony_inbound_e2e.py -q -p no:cacheprovider
py -3.12 -m pytest -q -p no:cacheprovider --basetemp hamza_local/pytest-phase12-full
py -3.12 -m ruff check telephony_gateway worker_raw/telephony tests/telephony
py -3.12 -m compileall -q telephony_gateway worker_raw/telephony
py -3.12 voice_engine_plan/scripts/verify_plan_integrity.py
git diff --check
```

The disposable PostgreSQL test is run separately with the repository's isolated Phase 12 compose file and removed with volumes afterward.

**Live certification remains a manual gate:** one approved Telnyx sandbox/test call at a time, to an allowlisted number, under a named spend cap. Capture sanitized event ordering, connection timings, acoustic-end-to-first-audible latency, loss/jitter, barge-in, cleanup, and carrier billing correlation. Stop on the first unexplained retry, destination mismatch, signature failure, privacy leak, or duplicate charge.

## Phase exit criteria

- Signed, replay-safe inbound webhook admission maps one Telnyx call to one tenant, published agent, and internal session.
- Fake carrier media proves a real bidirectional voice turn and barge-in under jitter, loss, duplicates, slow sinks, and hangup.
- Controlled outbound is policy-gated, idempotent, rate/spend bounded, and cannot become a campaign dialer.
- Unimplemented transports and unknown health fail closed.
- Metering, post-call, privacy, and cleanup occur exactly once.
- Endpoint/configuration/SDK/runbook documentation matches executable routes.
- Full offline suite passes with no external traffic or charges.
- Production/live readiness remains blocked until Phase 15 live certification is explicitly approved and passes.

## Prework evidence

See [`../evidence/phase-12-prework/READINESS.md`](../evidence/phase-12-prework/READINESS.md).
