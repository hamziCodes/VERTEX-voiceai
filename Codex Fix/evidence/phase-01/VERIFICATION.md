# Phase 01 Verification Evidence

**Date:** 2026-10-16
**Implementation commit:** `575c571`
**Status:** automated verification complete; local human browser check pending

## Implemented contract

- Primary metric: acoustic end-of-speech to receipt of the correlated first-playback acknowledgement.
- Server stages use server monotonic time. Client scheduling and playback timestamps remain in the client performance clock domain.
- The server reports the primary measure as `server_ack_upper_bound` because acknowledgement transport time is included.
- Missing anchors remain null and include explicit reasons. Synthetic greetings are `playback_ack_only` and do not enter user-perceived percentiles.
- Unknown, duplicate, excluded, and malformed acknowledgements do not mutate another turn.
- SLO status is provisional; no fixed 450 ms breach claim remains in runtime telemetry.

## Automated evidence

All commands set `RUN_LIVE_PROVIDERS=0`, `RUN_LIVE_DB_TESTS=0`, and `RUN_MOCK_PROVIDERS=1` where applicable.

| Check | Result |
|---|---|
| Focused Phase 01, compatibility, and barge-in suite | 34 passed in 2.54 s |
| Full offline pytest suite | 434 passed, 1 skipped, 2 known pre-existing VAD failures |
| Ruff on changed latency, SDK, hook, and test files | passed |
| Ruff fatal/undefined-name scan on worker pipeline/session | passed |
| Plan integrity | `OK: 36 phases, tests, and trackers verified.` |
| Shared JSON schema parse | passed |
| Runtime fabricated-latency pattern scan | no matches |
| Diff whitespace check | passed |
| Tracked credential-path scan | only intentional `.env.example` templates; no raw `.env` or API-key file |

The two full-suite failures match the cleanup baseline and are Phase 02 listening/VAD defects:

1. `tests/listening/test_speech_capture.py::test_process_frame_async_does_not_clear_on_onset`
2. `voice_engine_plan/tests/phase_tests/test_phase_17_pipeline_integration.py::test_vad_adapter_speech_detection`

TypeScript build verification was not run because `sdk/typescript/node_modules` and a global `tsc` are absent. No dependency download was performed.

## Regenerated offline baseline

Artifact: `latency-baseline-20261016T090200117411Z.json`

| Samples | Excluded | p50 | p95 | p99 |
|---:|---:|---:|---:|---:|
| 42 | 0 | 1.1 ms | 22.7 ms | 23.2 ms |

This is a scripted, network-blocked harness baseline. It verifies repeatable report generation and must not be interpreted as real microphone-to-speaker production latency.

## Required local human check

This check is free, local, uses mock providers, and places no telephone or provider calls.

In PowerShell terminal 1, from the repository root:

```powershell
$env:UCVE_ENV='development'
$env:UCVE_DEMO_MODE='1'
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_LIVE_DB_TESTS='0'
py -3.12 -m uvicorn control_plane.app:app --host 127.0.0.1 --port 8000
```

In PowerShell terminal 2, from the repository root:

```powershell
$env:UCVE_ENV='development'
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_LIVE_DB_TESTS='0'
py -3.12 -m uvicorn worker_raw.main:app --host 127.0.0.1 --port 8081
```

Open `http://127.0.0.1:8000/demo/`, start a session, allow microphone access, and speak three short turns. For each turn confirm:

1. audio is audible;
2. the latency badge says `PROVISIONAL` rather than a fixed breach/pass claim;
3. the latency event has a unique `turn_id`;
4. `acoustic_end`, `server_send`, and `playback_ack_received` are non-null;
5. `durations_ms.user_perceived_e2e` is non-null and non-negative;
6. `measurement_quality` is `server_ack_upper_bound`.

Return one screenshot of the latency panel and a sanitized three-row table containing only `turn_id`, `measurement_quality`, `user_perceived_e2e`, `stt_after_acoustic_end`, `llm_ttft`, `tts_ttfb`, `prebuffer_ms`, and `underrun`. Do not return tokens, headers, environment values, transcripts, or credentials.

## Gate decision

After the three-turn evidence is recorded, mark Phase 01 complete and begin Phase 02. If any required anchor is null or audio is not heard, keep Phase 01 open and diagnose that path before endpoint tuning.
