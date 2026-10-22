# Phase 07 — Provider Routing, Failover, and Credentials

**Status:** SPLIT — 07A READY FOR FINAL QA; H07 RESOLVED; 07B PLAN REVIEW

**Goal:** Select real tenant-authorized providers by capability and make failover truthful, independent, stream-safe, and observable.

**Depends on:** Phase 06.

**Audit coverage:** F02, F05, P01–P04, L01 provider side, I14 OpenAI tools.

## Human gate before implementation

H07 was resolved by Hamzi on 2026-10-22. Phase 07B uses platform-managed and
tenant BYOK tiers with explicit fallback policy and the language chains recorded
in `07b-tenant-credentials-and-routing.md`.

## Execution split

- **07A — Provider contracts and typed failures:** strict capability catalog,
  unknown-provider rejection, failure taxonomy, compiler/factory integration,
  and offline contract tests. Does not resolve H07.
- **07B — Tenant credentials and independent routing:** SecretVault resolution,
  cache isolation/rotation, real provider instances, scoped health and circuit
  evidence. Blocked on H07 credential-tier and release-chain decisions.
- **07C — Stream-safe failover and adapter hardening:** pre/post-commit rules,
  tool-call normalization, adapter deadlines/cancellation, partial-stream repair,
  and both-down behavior. Live qualification remains a separate V5 gate.

Only one checkpoint is executed and verified at a time.

## Files and interfaces

- Create/modify: provider capability registry, chain compiler/router, health store, credential resolver, typed provider errors.
- Modify: STT/LLM/TTS factories and all adapters; remove environment lookup from adapter internals where session injection is required.
- Test: adapter contracts, chain routing, stream commit/failover, credential isolation and tool serialization.

## Tasks

- [ ] Define strict ProviderSpec by capability/model/region/language/streaming/tools/audio/compliance/key tier; reject unknown IDs.
- [ ] Inject resolved credential into adapter construction through tenant-scoped SecretVault; never cache across tenant/provider identity incorrectly.
- [ ] Implement actual provider IDs in callbacks; prove secondary instance differs from primary.
- [ ] Share circuit evidence by category/provider/model/region with bounded half-open probes; do not mix LLM and TTS health.
- [ ] Map HTTP/auth/quota/rate/timeout/config/invalid-output errors to typed categories and retry policy.
- [ ] Remove live-path mocks and always-healthy checks. Test mode selects test providers explicitly.
- [ ] Normalize tools per LLM adapter; fix OpenAI serialization/nonexistent option access and test fragmented tool calls.
- [ ] Implement pre-commit failover and post-commit repair rules; forbid duplicate side-effect tools.
- [ ] Add cancellation and connect/first/inter-chunk/overall deadlines to every adapter.
- [ ] Test per-language capability, compliance/BYOK/platform rules, rotation, cache eviction, primary 401/429/5xx/partial stream, and both-down behavior.

## Verification

```powershell
python -m pytest tests/providers tests/security/test_provider_credentials.py tests/e2e/scenarios/test_failover_e2e.py -q
```

Expected: distinct secondary called, tenant credentials isolated, no mock fallback in production, partial output never duplicated, tool schemas valid.

## Human intervention

Live provider qualification is one approved vendor at a time using the V5 request. Record cost, region, language and account/quota limitations.

## Exit criteria

- Every advertised provider has passing offline contract tests and explicit rollout state.
- Every resilience claim names two independently usable providers.
- Credential policy matches H07.
