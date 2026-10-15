# Phase 00 test inventory

Date: 2026-10-15

## Runtime

- Supported project runtime: Python 3.12 or newer from `pyproject.toml`.
- Verified local command: `py -3.12` reports Python 3.12.10.
- Verified test runner: `py -3.12 -m pytest --version` reports pytest 9.1.1.
- Repository `.venv` is stale and points to an obsolete Microsoft Store Python path. Do not use it as Phase 00 evidence.

## Test configuration

- Pytest roots: `tests` and `voice_engine_plan/tests`.
- Async mode: strict.
- Excluded recursion: legacy codebases, `.git`, `.venv`, `node_modules`, `dist`, and `build`.
- Offline provider environment: `UCVE_ENV=test`, `RUN_MOCK_PROVIDERS=1`, and `RUN_LIVE_PROVIDERS` absent.

## Existing suites relevant to the voice path

- `tests/listening`: VAD, capture, pre-speech buffering, noise gate, live-STT adapter behavior, barge verification, and tool loop.
- `tests/providers`: provider factory and adapter mock behavior.
- `tests/e2e`: mock process scenarios, endpoints, telephony simulation, post-call, failover, and WebSocket flow.
- `tests/latency_benchmarks` and `tests/latency-benchmarks`: incomplete or duplicate historical aggregation harnesses; neither measures acoustic end-of-speech through acknowledged playback.
- `tests/latency`: Phase 00 network-denied baseline, report schema, deterministic providers, corpus, and production credential guard.

## Side effects and network boundaries

- Phase 00 writes only timestamped JSON beneath the caller-provided output directory.
- The Phase 00 suite patches DNS and socket connection entry points and allows loopback only.
- Existing E2E tests may create in-process TestClient applications and use local state. They run with mock providers and no live-provider flag.
- No Phase 00 command reads `.env`, raw key files, or environment values. Only fixed test variables are set by name.

## Existing regression result before Phase 00 fixes

Command:

```powershell
$env:UCVE_ENV='test'
$env:RUN_MOCK_PROVIDERS='1'
Remove-Item Env:RUN_LIVE_PROVIDERS -ErrorAction SilentlyContinue
py -3.12 -m pytest tests/listening tests/providers tests/e2e -q
```

Result: 64 passed, 3 failed in 18.67 seconds.

The failures are recorded without modification in this phase:

1. `tests/listening/test_speech_capture.py::test_process_frame_async_does_not_clear_on_onset` expected capture after six loud frames, but capture remained false.
2. `tests/e2e/test_system_endpoints_e2e.py::test_control_plane_quick_mint` expected HTTP 200, but received 401.
3. `tests/e2e/test_system_endpoints_e2e.py::test_worker_raw_websocket_handshake_and_turn` could not mint its setup token because the same endpoint returned 401.

These failures predate the Phase 00 harness and belong to later listening and authentication phases.
