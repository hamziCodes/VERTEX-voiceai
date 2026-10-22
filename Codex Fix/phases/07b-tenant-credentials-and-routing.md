# Phase 07B — Tenant Credentials and Independent Routing

**Status:** SPEC APPROVED — IMPLEMENTATION PLAN REVIEW

**Depends on:** Phase 07A (`cdb2741`) and H07, resolved 2026-10-22.

## Goal

Resolve every published provider route to an explicitly authorized credential,
construct independent provider instances, and isolate cache and circuit state so
one tenant, credential, category, or model cannot corrupt another route.

## Approved H07 product policy

WAVIA supports three explicit credential tiers:

- `platform`: use only the WAVIA-managed provider credential. A tenant secret
  does not override it.
- `byok`: use only the tenant credential. Missing, revoked, or undecryptable
  tenant credentials fail closed with no platform fallback.
- `both`: prefer the tenant credential and use the platform credential only
  when the tenant configuration explicitly allows fallback.

Deployment defaults:

- Self-serve dashboard and packaged SDK sessions default to `platform`.
- Done-for-you enterprise agents may use `platform`, `byok`, or explicit
  `both`, selected in their published configuration.
- A session token or client request cannot elevate or change the published
  credential tier.

Approved candidate release chains:

| Language | STT | LLM | TTS |
|---|---|---|---|
| `en` | Gladia → Deepgram | Groq → Gemini | Cartesia → ElevenLabs |
| `ur` | Gladia → Deepgram | Groq → Gemini | Uplift → Cartesia |
| `ar` | Gladia → Deepgram | Groq → Gemini | Cartesia → ElevenLabs |
| `ms` | Gladia → Deepgram | Groq → Gemini | Cartesia → ElevenLabs |

OpenAI remains an optional selectable LLM and is not required in the default
resilience chain. These are configuration candidates until separately approved
live qualification proves account access, model availability, latency, voice
quality, and language quality. Phase 07B makes no live-quality claim.

## Architecture

### Credential contracts

- Add a typed credential policy and resolved-credential descriptor. The
  descriptor carries tenant, provider, credential type, source tier, and
  rotation/version metadata but never serializes or logs the secret.
- Keep plaintext credentials in memory only for adapter construction. Runtime
  session plans continue to contain references, never secret values.
- Make platform-secret lookup an injected port. Environment access is allowed
  at the application boundary, not inside provider adapters.
- Keep the existing in-memory repository as an explicit development/test
  implementation. Durable credential persistence remains Phase 09 and must not
  be claimed by Phase 07B.

### Resolution and cache isolation

- Resolve the published route's `credential_ref` and credential tier before
  constructing its adapter.
- Cache identity includes tenant ID, provider ID, credential type, source tier,
  credential reference, and rotation/version. It must never be only
  `tenant:provider`.
- Rotation and revocation evict every cache entry derived from the affected
  credential. Expiration uses a bounded configurable TTL.
- Resolution emits metadata-only audit events. Hooks must not receive or log
  secret values.

### Provider construction

- Factories require an injected credential for live adapters and do not read a
  provider key from the environment internally.
- Construct one adapter instance per resolved route. Primary and fallback
  routes must be distinct objects with their own provider/model configuration.
- Test and mock providers remain explicit test-mode choices. Missing live
  credentials never select mock behavior in production.
- Validate provider category and language through the Phase 07A catalog before
  resolving credentials or constructing adapters.

### Health and circuit scope

- Route health identity includes category, provider, model, region, and the
  non-secret credential scope needed to prevent cross-tenant poisoning.
- Authentication, configuration, and tenant quota failures affect only the
  credential/tenant route that produced them.
- Provider timeouts and transient server failures may contribute to shared
  provider/model/region health, without merging LLM, STT, and TTS evidence.
- Half-open probes are bounded so concurrent sessions cannot stampede a
  recovering provider.

### Session flow

1. Load and verify the pinned Phase 06 runtime plan.
2. Select the published language routes.
3. Validate route capability using the Phase 07A catalog.
4. Resolve credentials according to the published tier and reference.
5. Construct independent adapters for every usable route.
6. Build category-specific routing state from those concrete routes.
7. Refuse a production resilience claim when fewer than two independently
   usable routes exist. Return a typed configuration error before audio starts.

## Error behavior

- Unknown provider, category mismatch, and language mismatch retain the Phase
  07A typed failures.
- Missing BYOK, forbidden fallback, revoked reference, decryption failure, and
  unresolved platform credential are distinct configuration/auth failures.
- Error messages may include tenant ID, provider ID, credential reference, and
  failure category. They must never include secret values, ciphertext, provider
  response bodies, or authorization headers.
- Credential failures do not open a provider-wide circuit.

## Implementation scope

- `core/secrets/`: typed policy, repository/lookup ports, resolver, isolated
  cache keys, rotation/revocation eviction, metadata-only audit hooks.
- `core/providers/`: credential-injected factories, concrete route identity,
  independently constructed chains, and scoped health/circuit state.
- `core/runtime/` and `worker_raw/`: resolve and build published routes before
  starting the audio pipeline.
- `control_plane/agents/`: validate tier and credential references during
  compilation without resolving or embedding secrets.
- Tests covering policy, isolation, construction, failure scope, and session
  startup. No live providers or paid traffic.

## Excluded

- Durable PostgreSQL credential storage, database migrations, and distributed
  cache invalidation (Phase 09).
- Stream commit/repair, tool-call normalization, and adapter deadline behavior
  (Phase 07C).
- Live provider qualification, paid calls, deployment, or production secret
  migration.

## Verification

Focused offline coverage must prove:

- platform, BYOK, and explicit `both` resolution semantics;
- strict fail-closed behavior and no implicit platform fallback;
- no cache leakage across tenants, references, types, tiers, or rotations;
- adapter constructors receive the resolved key while session plans and logs do
  not contain it;
- primary and fallback are distinct instances and invoke distinct providers;
- authentication/quota evidence stays credential-scoped;
- transient provider evidence is category/provider/model/region scoped;
- bounded half-open probes;
- production startup rejects fewer than two independently usable routes;
- the approved language chains pass catalog validation.

Run focused tests, the full forced-offline suite, Ruff, compileall, plan
integrity, a secret-shape scan, and `git diff --check`.

## Exit criteria

- H07 policy is represented by typed runtime contracts and enforced consistently.
- Every production route is constructed with an explicitly resolved credential.
- Cache and circuit evidence cannot leak or poison unrelated tenants/routes.
- Published default chains are representable and validated offline.
- All verification passes with live providers and live databases disabled.
- Phase 07C remains unstarted until Phase 07B is independently verified.
