# Phase 06 — Published Agent Session Compiler

**Status:** READY FOR FINAL QA

**Goal:** Make an immutable published AgentConfig the authoritative source of runtime persona, language, provider chains, voice, tools, knowledge, extraction, telephony, and compliance policy.

**Depends on:** Phase 05.

**Audit coverage:** F01, A02 config half, P03/P04 context, deployment-model foundation.

## Human gate before implementation

Resolve H06: whether token holders may alter prompt/provider/language or all such fields are pinned at publish. Recommended: published config is authoritative; local demo can use an explicit unsafe override flag.

## Files and interfaces

- Create: `core/runtime/session_plan.py` with immutable `RuntimeSessionPlan`.
- Create: `control_plane/agents/compiler.py` with `compile_agent_version(tenant_id, agent_id, version) -> RuntimeSessionPlan`.
- Modify: agent repo/pin, session mint, JWT claims/reference, worker config loader and orchestrator constructors.
- Test: `tests/agents/test_session_plan_compiler.py`, `tests/e2e/test_published_agent_runtime.py`.

## Tasks

- [x] Define one schema/version for runtime plan; include no plaintext credentials, only credential references.
- [x] Compile and validate published snapshot: supported languages, provider capability chains, voice mapping, tool allowlists, KB IDs, compliance, limits and telephony policy.
- [x] Pin the plan/version with the minted in-memory session and expose a signed hash/reference to the worker. Phase 09 owns durable transactional persistence.
- [x] Load the plan tenant-scoped in worker; reject absent/unpublished/mismatched/hash-invalid plans.
- [x] Remove defaults/query parameters that silently override persona/language/providers/voice outside explicit local unsafe mode.
- [x] Materialize language, tool, RAG/extraction identifiers, telephony, compliance, limits, and provider policy from the plan. Phase 10 owns actual RAG/tool integrations and Phase 12 owns carrier enforcement.
- [x] Preserve active version pins across later publishes. Rollout must drain pre-Phase-06 tokens for their 120-second TTL; workers never reinterpret legacy or invalid snapshots.
- [x] Test second-worker loading through a shared repository, publish during call, rollback to prior version, invalid chain, cross-tenant lookup, hash tampering and override isolation. Durable process restart waits for Phase 09 storage.

## Verification

```powershell
python -m pytest tests/agents/test_session_plan_compiler.py tests/e2e/test_published_agent_runtime.py -q
```

Expected: a changed published persona/provider/voice affects new sessions only; active session remains pinned; wrong tenant/unpublished config fails; restart retains configuration once Phase 09 durability is available.

## Human verification

Hamzi approved on 2026-10-20 that published configuration is authoritative in
production. Sessions may choose only options explicitly allowed by that
published version; unrestricted prompt/provider/language/voice overrides are
local-development-only behind an explicit unsafe flag. No UI is built here.

## Exit criteria

- Browser, packaged SDK, enterprise, and future Studio consume the same runtime plan.
- No production session silently falls back to dataclass persona/provider defaults.

Automated evidence is recorded in `../evidence/phase-06/VERIFICATION.md`.
