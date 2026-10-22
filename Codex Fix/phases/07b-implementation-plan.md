# Phase 07B Tenant Credentials and Independent Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce the approved credential tiers, inject resolved credentials into distinct provider routes, and isolate credential caches and circuit evidence across tenants and provider scopes.

**Architecture:** Published routes carry a typed credential tier and a reference rather than a secret. A tenant-scoped resolver returns a non-serializable credential descriptor, factories construct one adapter per route from the injected key, and category-specific routers track provider-wide and credential-scoped failures separately. The current encrypted in-memory repository remains explicitly development/test only; durable persistence stays in Phase 09.

**Tech Stack:** Python 3.12, Pydantic v2, dataclasses/protocols, asyncio, pytest, existing UCVE provider interfaces.

**Spec:** `Codex Fix/phases/07b-tenant-credentials-and-routing.md`

## Global Constraints

- Work only on `wavia-fixv1`; never push `main` or edit `.github/workflows`.
- Never read `.env` or raw API-key files and never print, persist in plans/logs, or commit secret values.
- Keep `legacy_codebases/` and `docs/blueprint/` read-only.
- Set `UCVE_ENV=test`, `RUN_MOCK_PROVIDERS=1`, `RUN_LIVE_PROVIDERS=0`, and `RUN_LIVE_DB_TESTS=0` for evidence-bearing tests.
- Do not place provider or telephony calls, use live databases, deploy, publish packages, or incur charges.
- Runtime plans and logs contain credential references and metadata only.
- Preserve compatibility for existing explicit mock/test construction while removing adapter-internal provider-key environment lookup.
- Do not begin Phase 07C in this plan.
- Do not commit or push until Hamzi gives the separate required confirmation after verification.

## Review Focus

- A `byok` route with no reference or missing tenant credential must fail closed; Task 2 compiler tests and Task 1 resolver tests pin this behavior.
- Two tenants using the same provider must never share cached tenant credentials or auth/quota circuit failures; Tasks 1 and 4 test isolation.
- Rotation must make the old cache identity unusable immediately; Task 1 tests versioned eviction.
- Provider environment variables must not silently replace an injected or missing adapter credential; Task 3 tests every adapter family.
- A production chain with two configured names but only one resolvable credential must be rejected before audio starts; Task 5 tests startup binding.

---

### Task 1: Credential policy, repository ports, and isolated resolution

**Files:**
- Create: `core/secrets/policy.py`
- Create: `core/secrets/repository.py`
- Create: `core/secrets/platform.py`
- Modify: `core/secrets/cache.py`
- Modify: `core/secrets/vault.py`
- Modify: `core/secrets/__init__.py`
- Test: `tests/security/test_provider_credentials.py`

**Interfaces:**
- Produces: `CredentialTier(StrEnum)` with `PLATFORM`, `BYOK`, and `BOTH`.
- Produces: frozen `CredentialRecord` and `ResolvedCredential`; `ResolvedCredential.secret` uses `field(repr=False, compare=False)`.
- Produces: `SecretRepository` protocol and `InMemorySecretRepository` development/test implementation.
- Produces: `PlatformSecretProvider` protocol and `EnvironmentPlatformSecretProvider.resolve(provider_id, credential_type) -> PlatformCredential | None`.
- Produces: `SecretVault.resolve_credential(tenant_id, provider_id, *, credential_ref, credential_type, tier) -> ResolvedCredential`.
- Preserves: `SecretVault.resolve(...) -> str` as a compatibility wrapper for existing callers/tests.

- [ ] **Step 1: Write failing resolver and cache tests**

Add tests named `test_platform_never_uses_tenant_secret`, `test_byok_never_falls_back_to_platform`, `test_both_prefers_byok_then_explicit_platform`, `test_cache_identity_isolates_tenant_ref_type_tier_and_version`, `test_rotation_evicts_old_version`, and `test_resolved_credential_repr_omits_secret`.

- [ ] **Step 2: Verify the new tests fail**

Run: `py -3.12 -m pytest tests/security/test_provider_credentials.py -q`

Expected: collection/import failures for the new policy, repository, and resolved-credential contracts.

- [ ] **Step 3: Implement the credential contracts and repository port**

Implement the interfaces above. `CredentialRecord` owns ciphertext, key version, credential reference, and rotation version. Repository lookup is keyed by tenant, provider, credential type, and reference. Environment lookup is confined to `EnvironmentPlatformSecretProvider` and recognizes only `PLATFORM_<PROVIDER>_API_KEY` for platform credentials.

- [ ] **Step 4: Replace string cache keys with `CredentialCacheKey`**

Create a frozen key containing tenant, provider, credential type, tier, reference, and rotation/version. Add predicate-based invalidation for rotation/revocation while retaining `clear()`.

- [ ] **Step 5: Implement strict resolution semantics**

`platform` ignores tenant records; `byok` requires a reference and never falls back; `both` tries the referenced tenant record and then the injected platform provider. Audit hooks receive metadata only. Decryption and missing-secret errors remain fail closed.

- [ ] **Step 6: Run Task 1 tests**

Run: `py -3.12 -m pytest tests/security/test_provider_credentials.py voice_engine_plan/tests/phase_tests/test_phase_09_credential_vaulting.py -q`

Expected: all pass with compatibility tests retained.

- [ ] **Step 7: Record the Task 1 checkpoint in `hamza_local/phase-07b-execution/progress.md`**

Do not commit; list modified files and the exact passing command.

### Task 2: Publish credential policy in immutable session plans

**Files:**
- Modify: `control_plane/agents/models/provider_config.py`
- Modify: `control_plane/agents/compiler.py`
- Modify: `core/runtime/session_plan.py`
- Modify: `core/providers/spec.py`
- Modify: `tests/agents/test_session_plan_compiler.py`
- Modify: `tests/providers/test_provider_catalog.py`

**Interfaces:**
- Consumes: `CredentialTier` from Task 1.
- Produces: `ProviderRoute.credential_tier: CredentialTier = CredentialTier.PLATFORM`.
- Produces: `RuntimeProviderRoute.credential_tier: Literal["platform", "byok", "both"]` in the signed/hash-addressed snapshot.
- Produces: `DEFAULT_RELEASE_CHAINS` or an equivalent immutable mapping for the approved en/ur/ar/ms chains.

- [ ] **Step 1: Write failing compiler and default-chain tests**

Test that `byok` and `both` require a non-empty `credential_ref`, `platform` rejects a tenant reference, client input cannot alter a compiled tier, the plan hash changes with the tier, all advertised providers declare `BOTH` capability after H07, and the approved four-language chains match the specification.

- [ ] **Step 2: Verify the tests fail**

Run: `py -3.12 -m pytest tests/agents/test_session_plan_compiler.py tests/providers/test_provider_catalog.py -q`

- [ ] **Step 3: Add typed route policy and compiler validation**

Add the fields above, validate tier/reference combinations before creating `RuntimeProviderRoute`, and keep all plaintext-secret rejection rules. Increment `SESSION_PLAN_SCHEMA_VERSION` because the authenticated snapshot shape changes.

- [ ] **Step 4: Encode the approved candidate chains**

Represent Gladia→Deepgram and Groq→Gemini for all four languages, Uplift→Cartesia for Urdu, and Cartesia→ElevenLabs for English/Arabic/Malay. OpenAI remains catalogued but absent from mandatory defaults.

- [ ] **Step 5: Run Task 2 tests**

Run: `py -3.12 -m pytest tests/agents/test_session_plan_compiler.py tests/providers/test_provider_catalog.py -q`

Expected: all pass, including snapshot integrity tests.

- [ ] **Step 6: Update the ignored execution checkpoint**

Record the schema version and passing command; do not commit.

### Task 3: Remove hidden API-key lookup and require factory injection

**Files:**
- Modify: `core/providers/factory.py`
- Modify: `core/providers/live_stt_factory.py`
- Modify: `core/providers/adapters/gladia_stt.py`
- Modify: `core/providers/adapters/gladia_live_stt.py`
- Modify: `core/providers/adapters/deepgram_stt.py`
- Modify: `core/providers/adapters/groq_llm.py`
- Modify: `core/providers/adapters/gemini_llm.py`
- Modify: `core/providers/adapters/openai_llm.py`
- Modify: `core/providers/adapters/uplift_tts.py`
- Modify: `core/providers/adapters/cartesia_tts.py`
- Modify: `core/providers/adapters/elevenlabs_tts.py`
- Modify: `tests/providers/test_llm_providers.py`
- Modify: `tests/providers/test_tts_provider_factory.py`
- Create: `tests/providers/test_provider_credential_injection.py`

**Interfaces:**
- Produces: `build_stt_provider(provider_id, *, api_key, model=None, mock_text="")`.
- Produces: `build_llm_provider(provider_id, *, api_key, model=None)`.
- Produces: `build_tts_provider(provider_id, *, api_key, model=None, speaking_config=None)`.
- Produces: `build_live_stt_session(provider_id, *, api_key, language, endpointing, receive_partials)`.

- [ ] **Step 1: Write failing injection tests**

Parameterize all eight provider adapters. Set matching provider-key environment variables to sentinel values, construct adapters with a different explicit key or `None`, and assert the sentinel is never loaded. Assert each factory passes the exact injected key and creates distinct primary/fallback objects.

- [ ] **Step 2: Verify the tests fail against current environment lookup**

Run: `py -3.12 -m pytest tests/providers/test_provider_credential_injection.py -q`

- [ ] **Step 3: Remove provider-key environment reads from adapters**

Keep non-secret endpoint, voice, audio-format, and test-mode configuration reads in scope. Adapter constructors may accept `None` for explicit mock tests, but factories require the `api_key` keyword with no default.

- [ ] **Step 4: Pass model selection through factories**

Use published route models for Deepgram, LLM, Cartesia, and ElevenLabs where their adapters support model selection. Do not silently substitute a different provider.

- [ ] **Step 5: Run Task 3 provider tests**

Run: `py -3.12 -m pytest tests/providers tests/listening/test_gladia_live_stt.py tests/latency/test_no_live_network.py -q`

Expected: all pass with live traffic disabled.

- [ ] **Step 6: Update the ignored execution checkpoint**

Record adapter/factory paths and passing command; do not commit.

### Task 4: Build independent routes and scoped circuit evidence

**Files:**
- Create: `core/providers/routing.py`
- Modify: `core/providers/failover.py`
- Modify: `core/providers/circuit_breaker.py`
- Modify: `core/providers/exceptions.py`
- Modify: `core/providers/__init__.py`
- Create: `tests/providers/test_provider_routing.py`
- Expand: `tests/e2e/scenarios/test_failover_e2e.py`

**Interfaces:**
- Consumes: `ResolvedCredential`, injected factories, and `RuntimeProviderRoute`.
- Produces: frozen `ProviderRouteIdentity(category, provider_id, model, region, tenant_id, credential_scope)`.
- Produces: generic frozen `ResolvedProviderRoute(identity, adapter)`.
- Produces: `ProviderRouteBuilder.build_chain(tenant_id, category, language, routes) -> tuple[ResolvedProviderRoute, ...]`.
- Produces: `ProviderInvocationError(failure: ProviderFailure)` for sanitized typed routing evidence.
- Produces: bounded half-open probe acquisition in `ProviderHealthState`.

- [ ] **Step 1: Write failing route construction and circuit-scope tests**

Test distinct adapter objects/provider IDs, catalog validation before credential resolution, two-usable-route enforcement, auth/quota isolation by credential scope, transient server sharing only within category/provider/model/region, category isolation, and exactly one concurrent half-open probe.

- [ ] **Step 2: Verify the tests fail**

Run: `py -3.12 -m pytest tests/providers/test_provider_routing.py tests/e2e/scenarios/test_failover_e2e.py -q`

- [ ] **Step 3: Implement immutable route identities and builder**

Build each route independently from its own resolved credential and published model. Credential scope is metadata derived from tenant/reference/source/version and contains no secret material.

- [ ] **Step 4: Split credential and provider health evidence**

Authentication, quota, and configuration failures update only the concrete route scope. Timeout and transient-server failures update the provider/model/region/category scope. Preserve the compatibility path for existing string-priority tests while production routes use identities.

- [ ] **Step 5: Bound half-open probes and sanitize aggregate errors**

Allow one probe per health key and release the lease on success, failure, timeout, or cancellation. `NoProviderAvailableError` names failed routes and typed categories without exception reprs or response bodies.

- [ ] **Step 6: Run Task 4 tests**

Run: `py -3.12 -m pytest tests/providers/test_provider_routing.py tests/e2e/scenarios/test_failover_e2e.py tests/hardening/test_remediation_r1_r7.py -q`

- [ ] **Step 7: Update the ignored execution checkpoint**

Record route and circuit evidence; do not commit.

### Task 5: Bind published provider chains before audio starts

**Files:**
- Create: `worker_raw/orchestration/provider_binding.py`
- Modify: `worker_raw/orchestration/session_config.py`
- Modify: `worker_raw/orchestration/pipeline.py`
- Modify: `worker_raw/main.py`
- Create: `tests/providers/test_session_provider_binding.py`
- Modify: `tests/listening/test_warm_stt_session.py`
- Modify: `tests/latency/test_pipeline_baseline.py`

**Interfaces:**
- Consumes: Task 4 route builder and the complete published `provider_chain` map.
- Produces: `BoundProviderChains` containing category-specific tuples of `ResolvedProviderRoute` and `aclose()` ownership.
- Produces: `ProviderSessionBinder.bind(config: PipelineSessionConfig) -> BoundProviderChains`.
- Changes: `PipelineOrchestrator.apply_provider_selection` binds complete chains once at session startup and category invocations select the adapter supplied by the router.

- [ ] **Step 1: Write failing startup binding tests**

Test that all six primary/fallback objects for one language are constructed before readiness, the router invokes the selected route's adapter rather than a single shared provider, unavailable credentials reject startup, and teardown closes every constructed adapter exactly once.

- [ ] **Step 2: Write production mock-safety tests**

With `UCVE_ENV=production`, `RUN_MOCK_PROVIDERS=0`, and `RUN_LIVE_PROVIDERS=0`, assert missing credentials and all-routes-down return typed failure and never synthesize the existing “I heard you say” mock response.

- [ ] **Step 3: Verify the tests fail**

Run: `py -3.12 -m pytest tests/providers/test_session_provider_binding.py tests/listening/test_warm_stt_session.py tests/latency/test_pipeline_baseline.py -q`

- [ ] **Step 4: Implement session binding and category routers**

Inject a `SecretVault`/route builder at the worker boundary, bind the selected language chains before audio readiness, and store category-specific routes/routers. Batch STT, LLM, and TTS callbacks use the adapter attached to the router-selected route. Live STT receives the primary route's injected key; unsupported live fallback remains the explicit batch path.

- [ ] **Step 5: Enforce owned teardown and production fail-closed behavior**

Close every bound adapter once. Retain synthetic replies only in explicit test/mock mode; production routing exhaustion surfaces the sanitized typed failure.

- [ ] **Step 6: Run Task 5 tests**

Run: `py -3.12 -m pytest tests/providers/test_session_provider_binding.py tests/listening tests/latency/test_pipeline_baseline.py -q`

- [ ] **Step 7: Update the ignored execution checkpoint**

Record worker integration evidence; do not commit.

### Task 6: Phase 07B regression, security review, and evidence

**Files:**
- Modify: `Codex Fix/phases/07b-tenant-credentials-and-routing.md`
- Modify: `Codex Fix/phases/07-provider-routing-and-credentials.md`
- Modify: `Codex Fix/EXECUTION_TRACKER.md`
- Create: `Codex Fix/evidence/phase-07b/VERIFICATION.md`
- Modify: `hamza_local/phase-07-continuation.md` (ignored)
- Modify: `hamza_local/phase-07b-execution/progress.md` (ignored)

**Interfaces:**
- Consumes: passing Tasks 1–5 and their checkpoint evidence.
- Produces: a reviewable Phase 07B diff and explicit Phase 07C starting point.

- [ ] **Step 1: Run focused Phase 07B verification**

Run with forced-offline environment:

`py -3.12 -m pytest tests/security/test_provider_credentials.py tests/providers tests/agents/test_session_plan_compiler.py tests/e2e/scenarios/test_failover_e2e.py tests/listening/test_warm_stt_session.py tests/latency/test_no_live_network.py -q`

- [ ] **Step 2: Run the full forced-offline suite**

Run: `py -3.12 -m pytest -q`

Expected: no new failure; record exact pass/skip/warning counts without hiding existing failures.

- [ ] **Step 3: Run static verification**

Run scoped Ruff, `python -m compileall -q` on modified Python packages/tests, `python voice_engine_plan/scripts/verify_plan_integrity.py`, and `git diff --check`.

- [ ] **Step 4: Run secret and forbidden-scope review**

Scan the Phase 07B diff for credential-shaped literals, authorization headers in logs, `.env`/raw-key paths, live-network enabling, edits under `legacy_codebases/`, `docs/blueprint/`, or `.github/workflows`, and accidental secret serialization.

- [ ] **Step 5: Write evidence and sync trackers**

Record commands/results, changed architecture, limitations, no-live-traffic statement, rollback base `d9e59f1`, and the explicit fact that durable credential persistence remains Phase 09. Set 07B to `READY FOR COMMIT APPROVAL`; leave 07C `NOT STARTED`.

- [ ] **Step 6: Stop for Hamzi's commit/push confirmation**

Do not stage, commit, or push until that confirmation is received.
