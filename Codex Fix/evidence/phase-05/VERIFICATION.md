# Phase 05 Verification — Realtime Protocol and SDK Parity

**Implementation date:** 2026-10-20

**Branch:** `wavia-fixv1`

**Rollback base:** `e6ea384989a208fba27440291d3a386d5aa8bf9c`

**Implementation commit:** `0f9390d`

**Provider mode:** offline mocks, fixtures, fake sockets, and local package consumers only

**Status:** READY FOR FINAL QA

## Defects confirmed

- The worker, browser demo, Python SDK, and TypeScript SDK used drifted event
  names and unversioned JSON shapes; no mandatory compatibility negotiation
  existed.
- Keepalive, remote close, token expiry, retry, sequence ordering, and
  reconnect/resume behavior were incomplete or differed by client.
- Python packaging used a broken source namespace when installed outside the
  repository. TypeScript core imports pulled React concerns into consumers and
  lacked a verified declaration/package path.
- Provider selection query parameters were accepted without an explicit local
  demo policy.
- Host-mint and WebSocket documentation contained stale paths, TTLs, and event
  examples.
- Flutter and LiveKit stubs could be read as shipped v1 clients although H05
  selected only raw-WebSocket Python and TypeScript for v1.

## Implementation evidence

- `sdk/shared/event_schema.json` is the canonical v1 event inventory. Generated
  Python/TypeScript types and `docs/sdk/REALTIME_PROTOCOL.md` are checked for
  byte-for-byte generator parity.
- Every JSON event now carries protocol version, event ID, monotonically
  increasing sequence, event type, timestamp, and payload. The first client
  frame must be `protocol.hello`; incompatible majors receive a typed error and
  close code 4406 before provider startup.
- Worker lifecycle handling covers keepalive timeout, ordered client controls,
  remote close, token-expiry notice/close, canonical transcripts/audio/latency,
  and explicit no-resume v1 negotiation.
- Python and TypeScript clients URL-encode tokens and parameters, perform the
  handshake, retry failed connection/negotiation attempts with bounded
  exponential backoff, answer keepalives, and surface close/expiry/error events.
- The React hook preserves host callbacks, owns cleanup, exposes audio/text and
  interruption controls, tracks speaking/remote close, and cancels playback
  once per clear event.
- Provider overrides require both a development/test environment and explicit
  `UCVE_ALLOW_DEMO_PROVIDER_OVERRIDES=1`; production session plans remain
  authoritative.
- Python and TypeScript release packages are version `1.0.4`; the wire protocol
  remains `1.0.0`. Flutter and LiveKit are explicitly roadmap-only, and the
  LiveKit package is private.

## Test-driven findings

- Initial protocol tests failed because `core.protocol` did not exist.
- Clean Python wheel import exposed absolute `sdk.python...` imports.
- Clean Node ESM import exposed extensionless module paths.
- Final review exposed that Python retried only socket establishment, not a
  failed negotiation; the new fake-socket regression failed first, then passed
  after the client closed the failed attempt and retried the full handshake.
- Final review also removed duplicate playback cancellation from the React hook.

## Automated verification

```text
pytest tests/sdk tests/e2e/test_realtime_protocol.py -q
21 passed

npm test  # sdk/typescript
3 passed; TypeScript build passed

pytest -q
531 passed, 1 skipped, 2 warnings

ruff check <Phase 05 Python paths>
All checks passed

generate_protocol_docs.py --check
generate_protocol_types.py --check
Both passed

node --check hamza_local/phase-05-execution/web-client-1.0.4.mjs
Passed

python voice_engine_plan/scripts/verify_plan_integrity.py
OK: 36 phases, tests, and trackers verified.
```

The full suite used `RUN_LIVE_PROVIDERS=0` and `RUN_LIVE_DB_TESTS=0`. The two
warnings are existing hardening tests that deliberately use short HMAC test
keys. No live database, provider, carrier, or network call was made.

## Package artifacts

Artifacts are verification-only and remain under gitignored `hamza_local/`.

- `ucve_voice_sdk-1.0.4-py3-none-any.whl` installed and imported from a clean
  consumer. SHA-256:
  `84025f789c9655908dbe6ab3781520cfd8d0758155f897f2ce5fbd150600cdaa`.
- `ucve-voice-sdk-1.0.4.tgz` imported its core entry without React and its React
  subpath with the declared React peer installed. SHA-256:
  `e20cc1767a87dbb12d2533dc9f66ac5862cd2587b6d90f070f54b100437ae9ac`.

## Security and scope review

- `.env`, raw API-key files, and secret values were not read or printed.
- A metadata-only scan of changed/untracked files found one runtime token
  variable assignment and two short test-fixture secret assignments; no
  credential literal or private-key/token signature was found.
- `.github/workflows`, legacy codebases, live infrastructure, deployment, and
  publication were untouched.
- `git diff --check` found no whitespace error; reported messages are the
  repository's LF-to-CRLF checkout warnings.

## Human gate retained

At final cross-phase QA, Hamzi reviews the public SDK surface and deprecation
policy and runs the long-running browser listening/interruption exercise. This
does not block the offline implementation commit. Publishing and any live
provider or telephony validation require separate approval in Phase 15.

## Rollback

Revert implementation commit `0f9390d` and its following evidence-only commit.
No external state or database migration needs rollback.
