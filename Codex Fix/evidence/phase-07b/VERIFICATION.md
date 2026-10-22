# Phase 07B Verification — Tenant Credentials and Independent Routing

**Implementation date:** 2026-10-22

**Branch:** `wavia-fixv1`

**Rollback base:** `d9e59f168f03ec15be1cb28db00e2305f54f75de`

**Approved planning checkpoint:** `5a3811346f828ee9ec123955c52808ec160912fa`

**Implementation commit:** `c6f43fca1f09b94a644fdebeecbf3f13bd4bb358` (`feat: bind tenant-scoped provider routes`).

**Status:** READY FOR FINAL QA

## Result

- Published routes carry an authenticated `platform`, `byok`, or `both`
  credential tier. The compiler enforces the tier/reference combination and
  session-plan schema `1.1.0` authenticates the policy.
- Platform lookup is isolated at an injected boundary. Provider adapters no
  longer read provider API-key environment variables.
- Tenant resolution, cache identity, rotation, revocation, and bounded TTL are
  tenant/provider/type/tier/reference/version aware. Resolved secret fields are
  excluded from repr and comparison.
- The approved English, Urdu, Arabic, and Malay release chains are encoded in
  the immutable provider catalog. OpenAI remains optional.
- Every authoritative session constructs six distinct route adapters before
  sending readiness: two each for STT, LLM, and TTS. Missing production
  credentials reject startup.
- STT, LLM, and TTS invoke the adapter selected by their own route router.
  Live Gladia receives the resolved primary credential; unsupported live STT
  retains the explicit batch route.
- Authentication, quota, rate-limit, configuration, and invalid-request
  evidence is credential scoped. Timeout and transient-server evidence is
  category/provider/model/region scoped. Half-open probes are single-owner and
  release on rejection, failure, timeout, or cancellation.
- All eight batch provider adapters use the same production-mode guard. A live
  upstream failure produces sanitized typed evidence and cannot synthesize a
  mock response in production.
- Session teardown closes every bound adapter once. Phase 6 TTS chunk sizing
  and explicit offline STT text remain wired through authoritative routes.

## Test-driven evidence

- Credential tests initially failed because the policy, repository, and
  platform boundary did not exist.
- Compiler/catalog tests initially failed because credential tiers and approved
  release chains were absent.
- Injection tests produced 11 expected failures because adapters loaded ambient
  keys and factories rejected explicit credentials.
- Routing tests initially failed collection because independent routes and
  typed invocation errors did not exist.
- Binding tests initially failed collection because session binding did not
  exist. A later full-suite failure exposed explicit offline-mock compatibility;
  this was fixed without weakening BYOK or production fail-closed behavior.

## Automated verification

All pytest commands ran with `UCVE_ENV=test`, `RUN_MOCK_PROVIDERS=1`,
`RUN_LIVE_PROVIDERS=0`, and `RUN_LIVE_DB_TESTS=0`.

```text
pytest tests/security/test_provider_credentials.py tests/providers \
  tests/agents/test_session_plan_compiler.py \
  tests/e2e/scenarios/test_failover_e2e.py \
  tests/listening/test_warm_stt_session.py \
  tests/latency/test_no_live_network.py -q
92 passed

pytest -q
605 passed, 1 skipped, 2 warnings

ruff check --select F,I,UP <all Phase 07B touched Python paths>
All checks passed

ruff check <all newly created Phase 07B Python paths>
All checks passed

python -m compileall -q <Phase 07B packages and tests>
Passed

python voice_engine_plan/scripts/verify_plan_integrity.py
OK: 36 phases, tests, and trackers verified.

git diff --check
Passed; only Windows LF-to-CRLF checkout notices were emitted.
```

The two warnings are existing hardening tests that deliberately use short HMAC
test keys. No provider request, telephony call, live database operation,
deployment, package publication, or paid traffic occurred.

## Security and scope review

- `.env` and raw API-key files were not opened.
- Credential-shaped literal scan: zero matches.
- Credential/authorization logging scan: zero matches.
- Live-network-enable additions: zero matches.
- Forbidden-scope edits under `.github/workflows`, `legacy_codebases/`,
  `docs/blueprint/`, `.env`, or raw-key paths: zero matches.
- Provider response bodies are not included in new routing errors or logs.
- Runtime plans, route identities, cache keys, and evidence contain metadata or
  credential references only.

## Deferred by design

- Durable encrypted credential persistence and distributed revocation/cache
  invalidation remain Phase 09. The current in-memory repository is development
  and test only, so cross-process BYOK is not production ready yet.
- Stream commit/repair rules, partial-output recovery, complete adapter deadline
  policy, and tool-call normalization remain Phase 07C.
- Provider/model/account availability, latency, language quality, voice quality,
  and quota behavior require separately approved live qualification.
- Final cross-phase browser, WebSocket, and telephony QA remains deferred until
  all phases are complete, as requested by Hamzi.

## Next exact action

Verify both local commit hashes and the worktree, then obtain Hamzi's separate
approval before pushing. Do not start Phase 07C before that checkpoint.
