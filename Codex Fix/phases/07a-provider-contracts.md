# Phase 07A — Provider Contracts and Typed Failures

**Status:** READY FOR COMMIT APPROVAL

**Goal:** Give every advertised provider one strict, source-controlled runtime
identity and make unsupported selections and provider failures explicit.

## Scope

- Immutable provider specifications for category, engine-supported languages,
  streaming shape, tool support, audio formats, default models, compliance
  qualification, credential-policy state, and rollout state.
- One catalog used by factories, the published-plan compiler, and the existing
  provider registry.
- Typed configuration and runtime failure categories with deterministic HTTP
  status classification and retryability.
- Offline contract tests for every advertised STT, LLM, and TTS provider.

## Excluded

- Tenant credential resolution or caching.
- Release-chain selection or BYOK/platform policy.
- Circuit sharing, real secondary invocation, or stream repair.
- Live provider qualification, calls, or charges.

## Verification

```powershell
$env:UCVE_ENV='test'
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_PROVIDERS='0'
py -3.12 -m pytest tests/providers tests/agents/test_session_plan_compiler.py -q
```

## Exit criteria

- Unknown provider IDs fail closed instead of silently becoming a default.
- Category and engine-language mismatches are rejected before adapter creation.
- Every advertised provider has an offline contract and explicit qualification
  and credential-policy status.
- H07 remains open and 07B is not started.

Automated evidence is recorded in `../evidence/phase-07a/VERIFICATION.md`.
