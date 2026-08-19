# Phase 32: Security Hardening and Threat Controls

## 1. Executive Summary & Core Logic

Execute a structured security hardening pass against the File 9 §5 consolidated anti-pattern checklist (20 items) and cross-phase security controls from Phases 09–13 — verifying fixes are implemented, not merely documented. Adds threat-model documentation and pre-release security verification matrix. Harvests habiba webhook signature patterns (`telephony_webhooks.py`, AUDIT_04 §3) and awaazlabs fail-open secret lessons (AUDIT_02 §6) as explicit regression tests.

Depends on all prior security phases (09 vault, 10 classification, 11 redaction, 12 audit, 13 auth), Phase 25 error opacity, Phase 22 MCP DATA-framing, Phase 23 RAG poisoning defenses.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| STRIDE-lite threat model doc | Industry standard for B2B voice SaaS |
| Anti-pattern checklist → automated tests | File 9 §5 — each item must be verifiable |
| OWASP ASVS L1 mapping for API surface | Control-plane + WS gateway |
| Dependency scanning in CI | Supply chain baseline |
| Pen-test readiness checklist | Pre-prod gate without mandating vendor in v1 |

**Reference docs:** blueprint File 09 §5 (items 1–20); File 06 §5 poisoning defense; habiba telephony webhook verify.

## 3. What / How / Why

- **What:**
  - **`docs/security/THREAT_MODEL.md`** — assets (PHI, API keys, call audio), trust boundaries (client/host-backend/worker/providers), STRIDE per boundary
  - **`docs/security/ANTI_PATTERN_CHECKLIST.md`** — File 9 §5 table with UCVE phase fix column + verification test link
  - **`tests/security/test_anti_patterns.py`** — automated checks for top 10 load-bearing items:
    - #8 fail-open secrets (Phase 21 webhook, Phase 13 mint)
    - #4 secrets in URLs (Phase 13 WSS token not logged — Phase 07 redaction)
    - #12 distributed rate limit (Phase 13 Redis)
    - #17 zero-retention path (Phase 11)
    - #18 ≥2 provider routes (Phase 06)
    - MCP/RAG DATA-framing not in system prompt (Phases 22–23)
    - Generic client errors (Phase 25)
    - HIPAA BAA gate (Phase 10)
    - Caller ID required telephony path (Phase 18)
    - LiveKit not required (Phase 18/30 compose default)
  - **`SecurityHeadersMiddleware`** — control-plane: HSTS, CSP baseline, `X-Content-Type-Options`
  - **`WSSecurityPolicy`** — max frame size (Phase 01), rate limit per connection (Phase 13), JWT expiry enforcement
  - **`DependencyAudit` CI step** — `pip-audit` / `uv pip compile --generate-hashes` stub
  - **`docs/security/PENTEST_READINESS.md`** — scope, OOS, known limitations (Urdu regex redaction Phase 15)
- **How:** Map each File 9 §5 row to a pytest in `tests/security/`. Threat model reviewed against Phase 10 tiers. Security headers on control-plane only in v1 (worker-raw WS uses binary protocol). Document residual risks: script-aware NER `[FUTURE]`, S2S `[LATER]`.
- **Why this approach:** Static blueprint listed fixes — this phase proves them in CI. awaazlabs fail-open and habiba sync-DB-in-async were production incidents in audit. Alternative: manual security review only — insufficient for 36-phase system.

## Deliverables

- `docs/security/THREAT_MODEL.md`
- `docs/security/ANTI_PATTERN_CHECKLIST.md`
- `docs/security/PENTEST_READINESS.md`
- `tests/security/test_anti_patterns.py`
- `tests/security/conftest.py`
- `control-plane/middleware/security_headers.py`
- `worker-raw/security/ws_policy.py` — `WSSecurityPolicy`
- `.github/workflows/security-audit.yml` — dependency scan stub

## 4. Compute & Resource Profile (if applicable)

Security test suite: ~30 s CI. WS frame size enforcement: negligible overhead. Rate limit: Redis increment — < 1 ms.

## 5. Compliance Notes (if applicable)

Threat model must document PHI flows: STT→LLM→persist→extraction→webhook. Pentest readiness lists HIPAA/GDPR control mappings. Security docs classify which logs may contain correlation_id only vs forbidden transcript content.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Automated vs manual verification:** **automated pytest for top 10 anti-patterns** — full 20-item manual sign-off checklist in PENTEST_READINESS for release gate.
2. **External pentest vendor:** **not required for phase exit** — readiness doc only; vendor engagement `[LATER]` pre-enterprise GA.
3. **WAF/CDN:** **documented optional `[LATER]`** — not v1 blocker; control-plane SecurityHeaders sufficient for MVP.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_32_security_hardening.py`
- **Asserts:** THREAT_MODEL.md exists with ≥3 trust boundaries; ANTI_PATTERN_CHECKLIST covers all 20 File 9 items; test_anti_patterns.py has ≥10 test functions; security headers middleware registered; ws_policy enforces max frame size; PENTEST_READINESS mentions Urdu redaction limitation.
- **Pass threshold:** security anti-pattern tests pass when implementation exists; structural pass always.
- **Latency target:** N/A for doc checks; ws_policy check < 0.1 ms per frame.
