# Phase 06: Provider Registry, Circuit Breakers, and Fallback Router

## 1. Executive Summary & Core Logic

Build the runtime provider selection layer: capability-table lookup, priority chains, per-provider health state, circuit breakers, and cross-provider failover. Harvests habiba `registry.py` no-silent-fallback rule (`legacy_codebases/habiba-sdk-agent/worker/providers/registry.py`) and MULTI `tts_manager.py` timeout/breaker pattern (`legacy_codebases/Multilingual_AI_Voice_Agent_gittracked/backend/app/services/tts/tts_manager.py`). Enforces File 03 §6: fewer than two enabled routes per critical category/language is a startup error.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| `ProviderRegistry` + `FailoverRouter` | Blueprint File 03 §4–5 |
| In-memory `ProviderHealthState` per worker | MULTI 2-fail/60s cooldown; extensible to Redis in Phase 17 |
| YAML/JSON priority chains in agent config | File 03 §5.2 example |
| Startup validation pass | Fixes habiba model remap drift (AUDIT_04 §6) |

**Reference docs:** blueprint File 03 §4–6; habiba `capabilities.py`.

## 3. What / How / Why

- **What:** `ProviderRegistry` (register/resolve/validate), `FailoverRouter.call_with_failover()`, `ProviderHealthState`, `CircuitBreakerConfig`:
  - **Open circuit when:** 5 consecutive failures **OR** ≥50% error rate over rolling window of last 10 requests
  - **Half-open retry:** after 30 s cooldown (not MULTI's 60 s — tuned for faster recovery while avoiding flapping)
  - **Provider call timeouts:** first-chunk 3.5 s / subsequent 1.5 s (MULTI `tts_manager.py` defaults)
  - **Latency demotion:** **not enabled by default in Phase 06** — priority reorder on latency is owned by Phase 24 `SLOPolicy` / `LatencyDemotionRule` (warn-only v1; `enforce_demotion` opt-in; rolling **p50**; default **N=5** turns). Phase 06 exposes `ProviderHealthState` hooks (`last_latency_ms`, priority index) that Phase 24 updates when opt-in demotion fires; demotion does **not** open circuit or hard-fail
  - **No automatic canary/traffic-splitting** — provider promotion is manual/admin-only (Phase 13 gates)
  `resolve_chain(category, language) -> list[str]` returns ordered provider IDs; rejects `testing` status unless explicit `allow_testing_providers: true` on tenant (Phase 08 schema).
- **How:** Registry populated at worker boot from config + registered adapter classes. FailoverRouter wraps invoke_fn with timeout, in-provider retry (v3 TTS retry pattern in `legacy_codebases/AI_voice_agent_v3 - gemini/backend/app/services/uplift_service.py`), then next provider on hard fail or open circuit. Rolling error window stored in `ProviderHealthState.recent_results: deque[bool]` (maxlen=10). Latency-based priority reorder is applied only when Phase 24 `SLOPolicy.enforce_demotion=true` (see Phase 24 §3).
- **Why this approach:** Per-provider try/except scattered in orchestrator failed in v3/MULTI for STT/LLM (AUDIT_05 matrix). Central router matches product mandate: no single-vendor throat. Alternative: service mesh retries — overkill for Phase 6.

## Deliverables

- `core/providers/registry.py` — `ProviderRegistry`, startup validation
- `core/providers/failover.py` — `FailoverRouter`, `ProviderHealthState`
- `core/providers/circuit_breaker.py` — breaker open/close logic
- `core/providers/chain_resolver.py` — priority chain + capability table join
- `core/providers/config_schema.py` — Pydantic model for agent provider chains
- `core/providers/exceptions.py` — `NoProviderAvailableError`, `ConfigurationError`
- `tests/fixtures/provider_chains/minimal_valid.yaml` — example two-deep chains per category

## 4. Compute & Resource Profile (if applicable)

Health state: ~200 bytes per provider instance per worker. Failover adds one retry latency window (up to 3.5 s first-chunk TTS timeout) before switching — budgeted in Phase 24 SLO. Memory flat O(providers × languages).

## 5. Compliance Notes (if applicable)

Registry must not log resolved provider chains with embedded secrets. Failover events log provider_id + error class only, not request payloads.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Circuit breaker:** trip on 5 consecutive failures OR 50% errors over rolling 10 requests; half-open after 30 s.
2. **Latency demotion:** deferred to Phase 24 `SLOPolicy` — warn-only v1; `enforce_demotion` opt-in; rolling p50; N=5. Phase 06 exposes health-state hooks only.
3. **Canary/traffic-split:** none for v1 — manual provider promotion only.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_06_provider_registry.py`
- **Asserts:** single-provider chain fails startup validation; simulated primary failure routes to secondary within cooldown; circuit opens after N failures; closed circuit recovers after cooldown; Phase 24 opt-in demotion can reorder via health-state hooks (no always-on demotion in Phase 06).
- **Pass threshold:** 100% router tests; forced primary kill completes turn via secondary in integration stub.
- **Latency target:** failover decision overhead < 5 ms excluding provider timeouts.
