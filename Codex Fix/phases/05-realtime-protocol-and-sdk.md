# Phase 05 — Realtime Protocol and SDK Parity

**Status:** NOT STARTED

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

- [ ] Enumerate client→server and server→client messages with schema version, IDs, payload, ordering and error semantics: ready, ping/pong, transcript partial/final, text turn, audio metadata, latency, barge/clear/ack, error/degraded, close.
- [ ] Add a handshake that rejects incompatible major protocol/SDK versions and reports supported range.
- [ ] Implement keepalive, remote close, reconnect/resume policy, token expiry/refresh signal, and bounded retry/backoff.
- [ ] Fix React hook ownership: preserve callbacks, expose send-audio, track remote close/speaking, cancel playback, cleanup on unmount.
- [ ] URL-encode connection parameters and forbid raw credentials/provider override outside demo policy.
- [ ] Fix Python package namespace/build README and verify a wheel from a clean directory.
- [ ] Fix TS build declarations/module outputs and verify import without React plus hook import with declared React peer.
- [ ] Update host-backend examples to use the actual authenticated mint contract and clearly label local-only demos.
- [ ] Generate protocol docs from the canonical schema; remove drifted examples and ttl/event names.
- [ ] Implement or explicitly mark Flutter/LiveKit packages unavailable according to H05.

## Verification

```powershell
python -m pytest tests/sdk tests/e2e/test_realtime_protocol.py -q
# Exact Python build/install and TypeScript build/test commands are finalized after package-manager inspection.
```

Expected: Python/TS clients complete >40-second offline sessions, answer ping, send/receive all events, interrupt playback, handle close/expiry, and install outside repo root.

## Human intervention

Hamzi reviews the public API and deprecation policy. Publishing is not part of this phase.

## Exit criteria

- Runtime, shared schema, docs, demo and release SDKs pass conformance.
- Package artifacts install in clean consumers.
- Roadmap stubs cannot be mistaken for functioning features.
