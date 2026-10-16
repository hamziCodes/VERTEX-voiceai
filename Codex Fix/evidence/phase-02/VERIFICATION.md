# Phase 02 Repair Slice Verification

**Date:** 2026-10-16

**Status:** automated checks complete; local microphone check pending

**Scope:** failed Phase 01 browser gate, Silero streaming input, truthful mock
mode, and compact demo console

**Implementation commits:** `be21fb4` (VAD/runtime), `66714cf` (demo console)

## Root cause

Two independent conditions made the browser appear broken:

1. The bundled Silero ONNX model expects each 16 kHz inference window to carry
   64 samples of rolling context before the 512-sample frame. The adapter sent
   only the frame, so real speech produced very low probabilities and did not
   reliably start capture.
2. `RUN_MOCK_PROVIDERS=1` intentionally disables real transcription. With an
   empty `UCVE_STT_MOCK_TEXT`, Gladia's batch fallback emits no words. The UI did
   not explain this state.

## Implemented

- Added and reset the 64-sample Silero context while preserving recurrent model
  state.
- Restricted ONNX inference to canonical 512-sample, 16 kHz frames; other frame
  sizes use the deterministic energy fallback.
- Added non-debug `vad_state` transition telemetry.
- Added `provider_mode` and `stt_transcript_mode` to `session_ready` without
  exposing credential values.
- Added explicit offline/live and transcript-mode notices in the demo.
- Rebuilt Voice Playground as a three-panel desktop workspace with a tabbed
  diagnostics inspector and responsive stacking.

## Automated evidence

All provider and database live gates were disabled. No calls were placed.

| Check | Result |
|---|---|
| New VAD/runtime/frontend contracts plus affected integration tests | 20 passed |
| Listening suite plus Phase 17 integration | 41 passed |
| Full offline development-demo suite | 446 passed, 1 skipped |
| Desktop Playwright geometry | all three panels fit 1440x900; body scroll locked |
| Inspector interaction | Metrics tab became the sole active/selected panel |
| Mobile Playwright geometry | no horizontal overflow at 390x844 |
| Duplicate HTML IDs | none |
| Ruff on new/directly repaired modules | passed |
| Ruff fatal-error scan on touched legacy modules | passed |
| Plan integrity | `OK: 36 phases, tests, and trackers verified.` |

The full-suite warnings concern deliberately short test-only JWT keys and are
unchanged by this repair.

## Fixture diagnosis

Before the fix, six local multilingual FLEURS WAV fixtures produced maximum
Silero probabilities between 0.0012 and 0.1138 and no onset events. Feeding the
model its required rolling context produced maxima from 0.9922 to 1.0. With the
production adapter fixed, all six fixtures emitted a speech-start transition.
Some clips do not emit speech-end because they lack the configured trailing
silence; that behavior belongs to the endpoint-profile A/B work still pending
in Phase 02.

## Human verification

Restart both local services so they load this code. For a free deterministic
mock check, add this only to the current PowerShell worker process:

```powershell
$env:UCVE_ENV='development'
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_LIVE_DB_TESTS='0'
$env:UCVE_STT_MOCK_TEXT='Offline speech detected'
py -3.12 -m uvicorn worker_raw.main:app --host 127.0.0.1 --port 8081
```

Keep the control plane in development demo mode, reload `/demo/`, and speak a
short phrase followed by about one second of silence. Confirm:

1. the badge says `OFFLINE MOCK`;
2. the notice says transcript text is a fixed offline test value;
3. voice state changes from `LISTENING` to `SPEECH DETECTED` and back;
4. the transcript displays `Offline speech detected`;
5. the response audio plays and the Latency tab receives a correlated turn.

The displayed words are simulated in this check. Testing actual recognition
requires explicit live-provider approval because it can incur a charge.

## Remaining Phase 02 work

- Warm the selected streaming STT before session readiness and make provider
  selection generic.
- Measure endpoint candidates and obtain H04 profile selection.
- Prove packet-size invariance and observable ingress/backpressure behavior.
- Test disconnect/reconnect and duplicate-final handling.
