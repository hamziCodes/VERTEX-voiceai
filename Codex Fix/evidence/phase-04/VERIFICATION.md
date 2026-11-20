# Phase 04 Verification — Interruption and Session Lifecycle

**Implementation date:** 2026-10-19
**Branch:** `wavia-fixv1`
**Implementation commit:** `b162577`
**Provider mode:** offline fixtures, mock transports, and local test doubles only
**Status:** READY FOR FINAL QA

## Defects confirmed

- F07: synthesis completion transitioned the FSM to listening before server and
  client playout drained. A sender-held chunk could survive a queue flush.
- F08: live-STT preparation and provider selection happened before the runner's
  cleanup boundary, so startup failures could bypass teardown.
- L10: verification always waited the full window; the active LLM/turn task was
  not owned by cancellation; callbacks accumulated; client scheduled audio had
  no required clear acknowledgment.
- The server accepted only bare `barge_in` while both public SDKs emitted
  `control.barge_in`.
- Full generated assistant text entered history before any proof that the user
  heard it.

## Implementation evidence

- `core/playback/turn_commit.py` converts client-confirmed PCM time to a stable
  word boundary and commits each assistant turn idempotently.
- Egress queue entries carry a generation. Barge-in increments the generation
  before awaiting cancellation, flushes queued chunks, and rejects a chunk a
  sender already dequeued.
- `ThreePointCancel.cancel_and_wait()` owns the live turn plus TTS consumers and
  waits for their cancellation. Runtime shutdown also owns verification,
  egress, live-STT, VAD and provider clients.
- Verification now resolves immediately when sustained VAD or the configured
  partial-word threshold passes; timeout still resumes false alarms.
- Canonical sequenced events are `control.barge_in`, `control.clear_audio`,
  `control.clear_audio_ack`, and `control.playback_drained`. Bare inbound
  `barge_in` is accepted until the next protocol major and emits a deprecation
  info event.
- Browser, Python SDK, and TypeScript SDK clear scheduled audio and acknowledge
  the played duration. Normal playback waits for `audio_end` plus client drain.
- Assistant history and transcript callbacks receive only played text. Missing
  clear acknowledgment commits no assistant text and emits a degraded event.
- Provider selection, live-STT startup, workers, finalization, transport close,
  Redis cleanup, and admission release now share the runner cleanup boundary.

## Red-test evidence

The first Phase 04 run had five failures: early verification exceeded 500 ms,
awaited cancellation did not exist, the schema lacked clear/drain events, and
runtime shutdown ownership did not exist. The played-text unit cases already
passed. After the foundation implementation, all seven initial tests passed.

## Automated verification

```text
pytest tests/e2e/scenarios/test_interruption_matrix.py tests/e2e/test_session_cleanup.py -q
24 passed

pytest tests/listening/test_barge_verify_live.py tests/e2e/scenarios/test_barge_in_e2e.py -q
4 passed

pytest tests/e2e/scenarios/test_interruption_matrix.py tests/e2e/test_session_cleanup.py tests/e2e/test_system_endpoints_e2e.py tests/audio/test_playout_buffer.py -q
43 passed

pytest voice_engine_plan/tests/phase_tests/test_phase_04_barge_in.py -q
7 passed

pytest -q
510 passed, 1 skipped, 2 warnings
```

The complete suite used `RUN_LIVE_PROVIDERS=0` and
`RUN_LIVE_DB_TESTS=0`. The two warnings are existing JWT tests that deliberately
exercise short HMAC keys. A first full run forced `UCVE_ENV=test` and
`RUN_MOCK_PROVIDERS=1`; two quick-mint tests correctly returned 401 because
that environment disables their development-only unauthenticated path. The
normal offline test environment passed fully.

One final full-suite attempt transiently missed the existing 1 ms ingress
backpressure timing assertion. The isolated test and its four-test module both
passed immediately, and the complete suite rerun passed 510/510. No production
logic was changed to mask the timing test.

Additional checks:

- Ruff passes for the new playback module and Phase 04 test files. Large
  pre-existing orchestration/FSM modules retain prior line-length and typing
  modernization debt.
- Node 24 TypeScript syntax checks pass for `client.ts` and `events.ts`.
- A full TypeScript build was not available because the package has no local
  dependencies and `tsc` is not installed. No dependency download was made.
- The deterministic sender race asserts zero stale chunks and under 100 ms from
  committed interruption to the server-side silence barrier.
- Plan integrity passes: `OK: 36 phases, tests, and trackers verified.`

## Human gate retained

The final QA pass must run the local browser interruption script against speech
in prebuffer, early playback, middle playback, and late playback positions. It
must confirm prompt silence, correct interrupting words, and a relevant next
answer. This was deferred until all phases at Hamzi's request.

## Rollback

Revert the Phase 04 implementation commit. No database migration, external
state mutation, provider request, carrier call, or paid action occurred.
