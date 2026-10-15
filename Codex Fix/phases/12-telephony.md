# Phase 12 — Telephony

**Status:** NOT STARTED

**Goal:** Complete an offline-tested carrier webhook/signaling/media lifecycle connected to the same voice pipeline, then prepare a separately approved live certification.

**Depends on:** Phase 04 for conversation behavior; Phases 07 and 09 before production integration.

**Audit coverage:** T01–T06.

## Human gate before implementation

Resolve H12. Recommended first boundary: Telnyx inbound only. Outbound adds dialing permissions, calling windows, consent, destination controls, cost and campaign safeguards and should be a separate sub-plan if selected.

## Files and interfaces

- Modify: telephony gateway webhooks/signatures/resolver/call store, Direct SIP or chosen media adapter, inbound worker handler.
- Create: stable carrier-call lifecycle mapping, replay store, RTP/media session interface and fake carrier/media server.
- Test: signature vectors, lifecycle ordering/replay, codec/DSP/RTP, full fake phone conversation, hangup/cleanup, trunk selection.

## Tasks

- [ ] Choose one carrier/transport implementation and mark all other stubs unavailable instead of healthy.
- [ ] Verify carrier signature over exact raw body with timestamp freshness and atomic event-ID replay rejection.
- [ ] Resolve DID to tenant/published agent from durable storage and keep one stable session per carrier call ID across reordered/duplicate events.
- [ ] Implement answer/start-media/end commands and real bidirectional media callback/stream. If direct SIP is chosen, cover SDP, RTP sockets, sequence/timestamps, jitter/loss and pacing; if carrier media WebSocket is chosen, document that exact boundary.
- [ ] Connect media ingress to the admitted runtime session, warm STT, turn queue, TTS egress, interruption, teardown, metering and post-call finalization.
- [ ] Validate μ-law vectors, 8↔16 kHz duration/quality, 20 ms packets, arbitrary fragmentation, jitter/reorder/loss and DTMF.
- [ ] Separate new-call trunk failover from established-call failure. Never promise transparent mid-call migration without proof.
- [ ] Persist call control state/idempotency and avoid duplicate answers/charges/jobs.
- [ ] Make gateway/control-plane route ownership and docs consistent; remove or protect unsigned normalization endpoint.
- [ ] Run the full offline test plan already documented in `AUDIT.md`.

## Verification

```powershell
python -m pytest tests/telephony tests/e2e/scenarios/test_telephony_inbound_e2e.py -q
```

Expected: signed started→answered→media→DTMF→ended events yield one session/record; actual fake audio traverses VAD→STT→LLM→TTS→μ-law; duplicates/reordering are idempotent; all sockets/tasks close.

## Human intervention

After offline completion, stop. Request one sandbox call with named carrier, allowed test number, maximum cost, command, and sanitized evidence. Never dial automatically.

## Exit criteria

- Offline media conversation passes under jitter/loss/hangup.
- Stubs cannot report connected/healthy.
- Live release remains blocked until Hamzi approves and passes staging certification.
