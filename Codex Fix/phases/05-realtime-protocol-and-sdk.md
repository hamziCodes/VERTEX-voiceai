# Phase 05 — Realtime Protocol and SDK Parity

**Status:** READY FOR FINAL QA

**Goal:** Ship one versioned realtime contract implemented consistently by worker, demo, Python SDK, TypeScript SDK, and declared optional clients.

**Depends on:** Phase 04.

**Audit coverage:** S01, S02, F03, I14 protocol/examples.

## Human gate before implementation

Resolve H05. Flutter or LiveKit may be marked roadmap-only without blocking the core release; if advertised for v1, their stubs must be implemented and tested.

## Files and interfaces

- Canonical: `sdk/shared/event_schema.json` plus generated/validated Python and TypeScript types.
- Modify: `worker_raw/ws_session.py`, `core/transport/native_websocket.py`, SDK clients/hooks, demo.
- Modify: Python/TS package manifests, imports, build outputs, READMEs, host-backend examples.
- Create: protocol conformance tests and fresh-consumer packaging fixtures.

## Tasks

- [x] Enumerate client→server and server→client messages with schema version, IDs, payload, ordering and error semantics: ready, ping/pong, transcript partial/final, text turn, audio metadata, latency, barge/clear/ack, error/degraded, close.
- [x] Add a handshake that rejects incompatible major protocol/SDK versions and reports supported range.
- [x] Implement keepalive, remote close, reconnect/resume policy, token expiry/refresh signal, and bounded retry/backoff.
- [x] Fix React hook ownership: preserve callbacks, expose send-audio, track remote close/speaking, cancel playback, cleanup on unmount.
- [x] URL-encode connection parameters and forbid raw credentials/provider override outside demo policy.
- [x] Fix Python package namespace/build README and verify a wheel from a clean directory.
- [x] Fix TS build declarations/module outputs and verify import without React plus hook import with declared React peer.
- [x] Update host-backend examples to use the actual authenticated mint contract and clearly label local-only demos.
- [x] Generate protocol docs from the canonical schema; remove drifted examples and ttl/event names.
- [x] Implement or explicitly mark Flutter/LiveKit packages unavailable according to H05.

## Verification

```powershell
python -m pytest tests/sdk tests/e2e/test_realtime_protocol.py -q
# Exact Python build/install and TypeScript build/test commands are finalized after package-manager inspection.
```

Expected: Python/TS clients complete >40-second offline sessions, answer ping, send/receive all events, interrupt playback, handle close/expiry, and install outside repo root.

## Human intervention

Hamzi approved the v1 scope on 2026-10-20: the raw-WebSocket Python and
TypeScript SDKs are release clients; Flutter and LiveKit remain explicitly
roadmap-only. Hamzi reviews the completed public API and deprecation policy.
That review and the long-running browser listening check are deferred to the
final cross-phase QA at Hamzi's request. Publishing is not part of this phase.

## Exit criteria

- Runtime, shared schema, docs, demo and release SDKs pass conformance.
- Package artifacts install in clean consumers.
- Roadmap stubs cannot be mistaken for functioning features.
