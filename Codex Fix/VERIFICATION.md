# Verification Handbook

## Purpose

This defines evidence required before a phase is complete. Commands remain offline and use test-only values unless a human gate authorizes live access.

## Levels

| Level | Default | Purpose |
|---|---|---|
| V0 Static | yes | imports, types/schema, secret/mock/dead-path scans |
| V1 Focused unit | yes | changed behavior and edge cases |
| V2 Offline integration | yes | complete process with fake providers/carriers and disposable stores |
| V3 Build/package | when relevant | wheels, npm artifacts, containers, fresh consumers |
| V4 Local human | when requested | listen and inspect actual browser behavior |
| V5 Live provider/carrier | never automatic | credentials, cost, destinations, vendor behavior |
| V6 Publish/deploy | never automatic | external release action |

## Environment rules

- Set `UCVE_ENV=test`, `RUN_MOCK_PROVIDERS=1`; ensure `RUN_LIVE_PROVIDERS` is absent for offline tests.
- Remove provider/carrier credentials from the test process.
- Use generated secrets and disposable DB/Redis instances.
- Block outbound network for V0–V3 when possible.
- Never print environment values; configuration scans may print names only.

## Standard commands

```powershell
# Focused test
python -m pytest tests/path/test_file.py -q

# Full current offline suite; Phase 00 will make exact exclusions explicit
python -m pytest tests voice_engine_plan/tests/phase_tests -q

# Find production paths that may fake success
rg -n "RUN_LIVE_PROVIDERS|RUN_MOCK_PROVIDERS|Mock reply|mock_text|_tone_pcm|status.*processed|return True" core control_plane worker_raw telephony_gateway post_call sdk

# Inspect realtime contract usage
rg -n "event_type|control\\.|text_turn|user_turn|ping|pong|barge_in|playback_started" worker_raw sdk examples docs

# Workspace review
git status --short
git diff --check
git diff --stat
```

Never claim the full suite passes unless the current run exits zero and its full summary was read.

## Phase verification scan

At every phase end verify:

1. Diff contains only phase work and preserves pre-existing changes.
2. Focused tests prove the original defect; where feasible they fail without the fix.
3. No error path becomes mock success, fake content, or silence.
4. New queues, buffers, retries, timeouts, tasks, and resources are bounded.
5. Tenant reads/writes derive tenant from authenticated context.
6. No secret, transcript preview, or provider response body enters logs.
7. Protocol/config docs describe final behavior.
8. `TRACEABILITY.md` and phase evidence are updated.
9. Rollback and migration recovery paths are known.
10. Human listening, paid runs, publishing, and deployment remain pending until explicitly approved.

## Latency corpus and report

Phase 00 formalizes fixtures for short English, short Urdu, Urdu/English mixed speech, Arabic, punctuation-free LLM output, natural pauses, low volume, background noise, four barge-in timings, 8/16/24/48 kHz audio, and irregular packets.

Each report includes commit, runtime profile, fixture, provider mode, sample count, p50/p95/p99, stage medians, dropped frames/chunks, queue high-water marks, sample drift, interruption-to-silence, and raw versus excluded samples with reasons.

## When Hamzi runs a verification

The executor supplies one copy-paste command, working directory, expected summary, offline/cost status, duration, artifact/output to return, and a reminder not to paste secrets. Hamzi returns sanitized summary/error text and metrics. The executor records the evidence and diagnoses failures.

## Live-test request format

Before V5, stop and state:

```text
Purpose:
Provider/carrier:
Maximum expected cost:
Allowed destination(s), if telephony:
Credential variable NAMES needed:
Command:
Expected duration:
Success criteria:
Sanitized output/artifacts to return:
```

Approval applies only to that run.
