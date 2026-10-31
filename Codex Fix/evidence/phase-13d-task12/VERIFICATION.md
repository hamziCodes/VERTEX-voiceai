# Phase 13D Task 12 verification

Date: 2026-10-31 (PKT)

Scope: WorkOS-authenticated tenant-bound session minting; signed worker-mode constraints enforced before provider startup; Wavia TypeScript SDK browser runtime; explicit disabled/offline/mock/live state; microphone and connection lifecycle; realtime transcript; scheduled PCM playback; playback timing acknowledgements; interruption clearing; latency waterfall; quota, permission, unsupported-browser, worker, microphone, and token-expiry failures; deterministic cleanup.

## Automated evidence

- `npm.cmd --prefix sdk/typescript test` — exit 0; 4 tests passed, including `audio.start`/`audio.end` lifecycle exposure.
- `npm.cmd --prefix studio run test` — exit 0; 7 files, 58 tests passed, including microphone gating and failed-start cleanup regressions.
- `npm.cmd --prefix studio run typecheck` — exit 0.
- `npm.cmd --prefix studio run lint` — exit 0; zero warnings/errors.
- `npm.cmd --prefix studio run build` — exit 0; production build compiled and generated `/agents/[agentId]/test`.
- `py -3.12 -m pytest tests/studio/test_voice_test_session_api.py tests/auth/test_route_matrix.py tests/auth/test_session_security.py tests/listening/test_worker_mode_constraint.py -q -p no:cacheprovider --basetemp hamza_local/pytest-phase13d-task12-final` — exit 0; 34 passed.
- Changed Python Ruff and compile checks — exit 0.
- Complete offline Playwright gate against hidden local fixture/Next processes with exact-PID cleanup — exit 0; 10 passed using one worker.
- `git diff --check` — exit 0.
- Built client chunk scan for room-token fixture text and server secret variable names — no matches.
- Changed-path scan for `.github/workflows`, read-only legacy/blueprint trees, `.env`, and raw key files — no matches.
- Changed-diff private-key/live-key pattern scan — no matches.

## Browser and protocol coverage

- Creates and publishes a named agent, then opens its browser voice test without exposing a raw agent ID in the primary UI.
- Shows `Mock mode` before connection; unset configuration fails closed as `Live disabled`.
- Mints through the Studio BFF with the WorkOS identity and selected tenant; the browser receives only a 120-second room token and worker URL.
- Signs the configured provider/transcript mode into that room token. The worker rejects a mismatch with code 4403 before claiming the connection, loading a session, or initializing a provider.
- Uses `@ucve/voice-sdk`; Studio does not reproduce the realtime event envelope or WebSocket handshake.
- Receives user and agent transcript lines, PCM audio, and STT/LLM/TTS/audible timing values from an offline worker fixture.
- Schedules PCM chunks on the browser audio clock, acknowledges first scheduled playback, and acknowledges drain on `audio.end`.
- Clears buffered playback on `control.clear_audio` and records the interruption state.
- Covers unsupported browser, Studio permission, quota, live-disabled, worker-disconnected, microphone-denied, token-expiry, and cleanup states.
- Ends the session with one socket close, one microphone-track stop, and one audio-context close.
- Drops microphone frames until the WebSocket handshake and worker-mode validation both complete; failed or cancelled audio startup releases any acquired track/context.
- Confirms the room token is absent from URL, local storage, session storage, console errors, and built static chunks.
- Existing one-use token/refresh replay behavior remains covered by the included session-security regression tests.

## Security and operations notes

- `/v1/studio/sessions` derives tenant and role from the verified OIDC identity plus `X-Tenant-Id`; its request body cannot select a tenant.
- The endpoint requires `session:mint`; tenant viewers can inspect test readiness but cannot start a session.
- `WAVIA_VOICE_TEST_MODE` accepts only `offline`, `mock`, or `live`; every other value is `disabled`.
- The server-selected mode is sent to the control plane, carried as allowlisted signed JWT claims, preserved on refresh, and rechecked against the worker's local provider mode before provider startup.
- The local SDK package runs its TypeScript build during package preparation so a clean Studio install can resolve typed SDK exports.
- The stateful offline Playwright fixture is serialized because concurrent fixture resets caused cross-test false failures.
- No live WorkOS tenant, provider, carrier, phone call, external worker, or paid traffic was used.

## Visual review

Artifact: `studio/test-results/phase13d-voice-test.png` (ignored local test evidence).

The screenshot confirms the mode, connection state, transcript, interruption result, audio receipt, and four latency stages fit in one desktop viewport. The surface is deliberately semantic and unstyled; navigation composition, responsive layout, typography, focus treatment, and final visual polish remain assigned to Phase 13G after Hamzi supplies and approves visual references.

## Gate

Task 12 implementation and offline verification are complete. Phase 13D is ready for Hamzi's review and explicit commit/push confirmation. Phase 13E has not started.
