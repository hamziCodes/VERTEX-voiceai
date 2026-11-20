# Phase 12D Verification Evidence

**Date:** 2026-10-28

**Branch:** `wavia-fixv1`

**Implementation commit:** `49478ad`

**Result:** PASS

## Delivered behavior

- `TelephonySessionSupervisor` is the one-call owner for local call/session
  uniqueness, authoritative pinned-plan validation, capacity admission,
  admission heartbeat, provider binding, STT warmup, media workers, limits,
  metering, post-call finalization, and teardown.
- Media admission still requires the exact-URL Telnyx signature and call-control
  identity from Phase 12C. Invalid plans and exhausted capacity fail before media,
  provider, or post-call startup.
- STT is prepared before the adapter begins consuming carrier frames. The same
  `PipelineOrchestrator` used by web voice processes canonical audio through VAD,
  STT, LLM, tools, and TTS.
- The media adapter can flush a final partial outbound frame and wait for carrier
  egress, so a completed TTS turn does not retain audio until the next turn.
- Telephony control handling maps pipeline clear-audio to Telnyx `clear` and
  immediately acknowledges the local transport boundary. Barge-in cancels the
  active child turn while preserving the long-lived turn worker and interrupting
  speech.
- Published maximum duration and maximum turns are enforced. Input and turn
  queues are bounded and drained before shutdown so blocked carrier callbacks
  cannot strand worker tasks.
- Carrier stop, unexpected disconnect, tool-requested end, provider-pipeline
  failure, worker shutdown, duration timeout, and turn limit all converge on one
  idempotent finalizer.
- The finalizer records retry-safe telephony, agent, STT, and TTS usage; finalizes
  one privacy-aware call record; and creates one post-call job. Repeated stop or
  hangup signals do not duplicate any of them.
- Caller identity is stored on the tenant-scoped call record and is not emitted
  in ordinary runtime logs.
- The Phase 18 DirectSIP codec/rebuffer API remains available only as a frozen
  offline compatibility mode. Production inbound execution uses the authenticated
  Telnyx media supervisor.

## Failure-first evidence

The Phase 12D test first failed during collection because the session supervisor
did not exist. The initial implementation then exposed a real barge-in ownership
bug: awaiting `run_turn()` directly allowed the cancellation contract to cancel
the long-lived turn worker. Each generation now runs in a child task, matching
the proven web-session design, so the worker survives and executes the
interrupting turn.

The first full-suite run exposed the frozen Phase 18 constructor contract. A
strict offline compatibility wrapper now preserves that codec/rebuffer test while
keeping it outside production routing. A later full-suite run exposed a fake-only
zero-delay polling race; the local waiter now advances in deterministic 1 ms
steps. Three repeated focused runs passed before the final full-suite run.

## Automated verification

### Phase 12D focused and full-pipeline E2E

```powershell
py -3.12 -m pytest tests/telephony/test_inbound_pipeline.py tests/e2e/scenarios/test_telephony_inbound_e2e.py -q -p no:cacheprovider --basetemp hamza_local/pytest-phase12d-e2e-final2
```

Result: **11 passed** in 2.34 seconds. The same selection then passed three
consecutive runs: **11/11/11 passed**.

The local fake-carrier scenario proves nonempty generated audio traverses PCMU
ingress → canonical PCM → VAD → STT → LLM → TTS → paced PCMU egress. It also
proves carrier clear and a second interrupting turn, exact once-only metering and
post-call enqueue, plan/capacity rejection, tool end, disconnect, provider
failure, worker stop, duration/turn limits, admission release, and zero leaked
adapter/orchestrator tasks.

### Related telephony, interruption, cleanup, and post-call regression

```powershell
py -3.12 -m pytest tests/telephony tests/e2e/scenarios/test_telephony_inbound_e2e.py tests/e2e/scenarios/test_barge_in_e2e.py tests/e2e/scenarios/test_interruption_matrix.py tests/e2e/test_session_cleanup.py tests/post_call -q -p no:cacheprovider --basetemp hamza_local/pytest-phase12d-related-final
```

Result: **117 passed** in 3.41 seconds.

### Full forced-offline suite

```powershell
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_DB_TESTS='0'
$env:RUN_LIVE_REDIS_TESTS='0'
$env:UCVE_ENV='test'
py -3.12 -m pytest -q -p no:cacheprovider --basetemp hamza_local/pytest-phase12d-full-final2
```

Result: **910 passed, 12 skipped, 2 warnings** in 8.41 seconds. The warnings
are the existing deliberately short invalid HMAC fixtures in
`tests/hardening/test_h1_auth_crypto.py`.

### Static and integrity gates

- Ruff formatting and scoped lint: **passed**.
- Scoped mypy: **4 source files passed**.
- Python compilation: **passed**.
- `git diff --check`: **passed**.
- Plan integrity: **`OK: 36 phases, tests, and trackers verified.`**
- Windows `%SystemDrive%` test-cache output was moved intact into ignored
  `hamza_local/pytest-os-cache-phase12d-final`; nothing was committed or deleted.

## Boundaries and next exact action

- No environment file, raw key file, Telnyx account, carrier endpoint, provider,
  shared database, destination number, deployment, paid traffic, or live call was
  accessed.
- Phase 12D proves the complete inbound behavior offline. It does not execute
  Telnyx answer/start-media commands, expose the production media route, or place
  an outbound call.
- Begin Phase 12E with failure-first tests for an authenticated, tenant-scoped,
  consent-backed, allowlisted, time-windowed, rate/concurrency/spend-bounded,
  idempotent single-call request. Implement typed Telnyx call creation and
  ambiguous-response reconciliation without contacting Telnyx. Keep campaigns,
  contact lists, bulk retries, and live calls unavailable.
