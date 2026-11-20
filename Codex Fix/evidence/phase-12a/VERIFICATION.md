# Phase 12A Verification Evidence

**Date:** 2026-10-27

**Branch:** `wavia-fixv1`

**Implementation commit:** `45a60bf`

**Result:** PASS

## Source contract

The implementation was checked against current official Telnyx material before code changes:

- Telnyx sends `telnyx-signature-ed25519` and `telnyx-timestamp`; verification uses the exact raw request body and the account public key: <https://github.com/team-telnyx/ai/blob/main/skills/telnyx-voice-python/SKILL.md>
- The signed input is `{timestamp}|{json_payload}`, the replay window is five minutes, duplicate delivery uses the event ID, and successful handlers acknowledge quickly: <https://github.com/team-telnyx/knowledge-base/blob/main/wiki/dev-docs/telnyx-messaging-3--part-3.md>
- Voice API v2 events identify the event and call using the event ID, `call_control_id`, `call_leg_id`, and `call_session_id`: <https://developers.telnyx.com/public/llms/calling/voice-api-full.txt>

Only sanitized public schema facts were copied into the local fixture. No Telnyx account or API was accessed.

## Delivered behavior

- Added strict typed Telnyx call-event models with an explicit supported event allowlist and required call identity/E.164 fields.
- Replaced the mixed Ed25519/HMAC verifier with Ed25519-only verification over `timestamp + "|" + exact_raw_body`.
- Enforced strict base64 lengths, finite integer timestamps, a symmetric 300-second freshness window, and fail-closed missing configuration.
- Added an async event-sink boundary that atomically accepts an event ID once before acknowledgment. The local sink is test-only; Phase 12B supplies PostgreSQL durability.
- Added one canonical gateway route at `/v1/telephony/webhooks/telnyx` and removed the unsigned generic route plus the duplicate control-plane handler.
- Accepted events return 202, recognized duplicates return 200 without repeat processing, invalid signatures return 401, invalid events return 422, and unavailable durable configuration returns 503.
- The webhook request performs verification, validation, and event acceptance only. It does not run the voice pipeline inline.

## Failure-first evidence

The new test initially failed collection because `InMemoryTelnyxEventSink` and `TelnyxWebhookService` did not exist. The first compatibility run then exposed the two prior insecure expectations: HMAC acceptance and unsigned endpoint success. Both tests were updated to assert the new Ed25519 and fail-closed contracts.

## Automated verification

### Focused and related telephony

```powershell
py -3.12 -m pytest tests/telephony/test_telnyx_webhook_security.py tests/hardening/test_remediation_r1_r7.py voice_engine_plan/tests/phase_tests/test_phase_18_telephony_sip_base.py tests/e2e/test_system_endpoints_e2e.py tests/e2e/scenarios/test_telephony_inbound_e2e.py -q -p no:cacheprovider --basetemp hamza_local/pytest-phase12a-final-focused
```

Result: **49 passed**.

### Full forced-offline suite

```powershell
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_LIVE_DB_TESTS='0'
$env:RUN_LIVE_REDIS_TESTS='0'
$env:UCVE_ENV='test'
py -3.12 -m pytest -q -p no:cacheprovider --basetemp hamza_local/pytest-phase12a-full
```

Result: **878 passed, 11 skipped, 2 warnings** in 9.26 seconds. Both warnings are the existing intentionally short HMAC fixtures in `tests/hardening/test_h1_auth_crypto.py`.

### Static and integrity gates

- Ruff formatting and changed-file lint: **passed**.
- Scoped mypy with only imported FastAPI/Pydantic decorator diagnostics suppressed: **5 source files passed**.
- Python compilation: **passed**.
- `git diff --check`: **passed**.
- Plan integrity: **`OK: 36 phases, tests, and trackers verified.`**
- Four Windows `%SystemDrive%` cache files were moved intact to gitignored `hamza_local/pytest-os-cache-phase12a`; nothing was deleted.

## Boundaries and next exact action

- No environment file, raw-key file, carrier account, provider, phone number, webhook destination, deployment, paid traffic, or live call was accessed.
- Phase 12A does not claim durable call identity or production-ready carrier admission. The endpoint remains unavailable until a durable sink is installed.
- Begin 12B with failure-first migration/repository tests for stable carrier-call identity, atomic event-ID deduplication, monotonic lifecycle state, active E.164 DID-to-published-agent resolution, and command idempotency. Then run a disposable PostgreSQL proof; do not contact Telnyx.
