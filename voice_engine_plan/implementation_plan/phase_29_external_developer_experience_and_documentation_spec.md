# Phase 29: External Developer Experience and Documentation Spec

## 1. Executive Summary & Core Logic

Define the external developer documentation pack, onboarding paths, and integration guides that sit alongside Phase 28 OpenAPI/SDK artifacts — turning the monorepo into something a B2B integrator can adopt without reading 36 phase specs. Harvests habiba's client-facing integration patterns (`legacy_codebases/habiba-sdk-agent/client-submission_v2/docs/INTEGRATION_GUIDE.md`, `sdk/@awaazlabs-uva/voice/README.md`, AUDIT_04 §2 zero-secret mint) and awaazlabs dashboard API consumption gaps (frontend mocks without backend docs, AUDIT_02 §6). Does **not** duplicate OpenAPI field lists — links to Phase 28 self-hosted `/docs` as source of truth.

Depends on Phase 28 SDK/OpenAPI, Phase 13 mint guide, Phase 26 agent config schema, Phase 10 compliance tiers (docs must surface HIPAA BAA gate), Phase 25 generic error codes for integrator-facing troubleshooting.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| Markdown docs in `docs/developer/` | Versioned with code; portable with `voice_engine_plan/` |
| Diátaxis structure (tutorial/how-to/reference/explanation) | Industry standard DX layout |
| Copy-paste quickstarts with env templates | habiba INTEGRATION_GUIDE pattern |
| Compliance callouts per tier | Phase 10 — integrators must see BAA/retention implications |
| Cross-links to phase deliverables | Self-contained navigation without repo archaeology |

**Reference docs:** blueprint File 08 §4–5; habiba `client-submission_v2/docs/INTEGRATION_GUIDE.md`; File 09 §6.3 living-doc principle.

## 3. What / How / Why

- **What:**
  - **`docs/developer/README.md`** — entry index: who this is for (host-backend integrator vs tenant admin vs platform ops)
  - **`QUICKSTART_HOST_BACKEND.md`** — 15-minute path: mint proxy → WS test call → hear TTS (uses `examples/host-backend/`, Phase 28)
  - **`QUICKSTART_AGENT_STUDIO.md`** — tenant admin path: create agent → test sandbox call → publish (Phase 27 flows)
  - **`INTEGRATION_PATTERNS.md`** — zero-secret embed (habiba publishableKey pattern), iframing SDK widget, server-side CRM webhook (Phase 21)
  - **`COMPLIANCE_INTEGRATOR_GUIDE.md`** — tier selection, BAA acknowledgment, retention/redaction summary (Phases 10–11), subprocessor list pointer
  - **`TROUBLESHOOTING.md`** — maps Phase 25 `UCVEErrorCode` to integrator actions (no internal stack traces); correlation_id lookup in logs
  - **`TELEPHONY_INTEGRATOR.md`** — inbound DID setup, webhook URLs, caller ID (Phase 18/19); outbound explicitly `[LATER]`
  - **`MCP_AND_RAG_SETUP.md`** — tenant MCP HTTP/SSE config (Phase 22), KB upload (Phase 23), tier embedder rules
  - **`GLOSSARY.md`** — UCVE terms: mint, pin, DATA frame, sovereign plane, etc.
  - **`docs/developer/env/.env.example`** — documented vars only (no secrets); links Phase 09 vault for production
- **How:** Documentation-only phase — no new runtime services. Each guide references exact phase deliverable paths. Include mermaid diagrams for mint→WS→pipeline flow. Compliance guide requires legal review checkbox stub in Studio (Phase 27) cross-link.
- **Why this approach:** Habiba shipped integration guides late; awaazlabs had UI without integrator docs (AUDIT_02). OpenAPI alone insufficient for voice realtime (binary audio + event protocol). Alternative: external SaaS doc portal — rejected (Phase 28 self-hosted posture).

## Deliverables

- `docs/developer/README.md`
- `docs/developer/QUICKSTART_HOST_BACKEND.md`
- `docs/developer/QUICKSTART_AGENT_STUDIO.md`
- `docs/developer/INTEGRATION_PATTERNS.md`
- `docs/developer/COMPLIANCE_INTEGRATOR_GUIDE.md`
- `docs/developer/TROUBLESHOOTING.md`
- `docs/developer/TELEPHONY_INTEGRATOR.md`
- `docs/developer/MCP_AND_RAG_SETUP.md`
- `docs/developer/GLOSSARY.md`
- `docs/developer/env/.env.example`

## 4. Compute & Resource Profile (if applicable)

Documentation-only — no runtime compute. Quickstart local stack: docker compose from Phase 30 (~4 GB RAM).

## 5. Compliance Notes (if applicable)

Integrator guides must state PHI boundaries: host backend responsible for consent before session; never log mint tokens; HIPAA tier requires BAA before cloud LLM. Docs must not embed real API keys or tenant IDs from legacy repos.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Doc hosting:** **in-repo Markdown** versioned with code — not external SaaS; OpenAPI detail via Phase 28 self-hosted `/docs`.
2. **Audience split:** **three paths** — host-backend integrator, tenant admin (Studio), platform ops (runbooks Phase 34) — separate entry quickstarts.
3. **Legacy repo references:** **citation links only** — guides describe UCVE paths, not habiba/awaazlabs install steps.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_29_developer_experience.py`
- **Asserts:** all deliverable markdown files exist; README links every guide; QUICKSTART references Phase 28 mint guide + examples/host-backend; COMPLIANCE guide mentions HIPAA BAA gate; TROUBLESHOOTING lists ≥10 UCVEErrorCode entries; TELEPHONY guide states outbound `[LATER]`; GLOSSARY defines mint, DATA frame, caller_id; .env.example has no literal secrets.
- **Pass threshold:** 100% structural doc coverage checks.
- **Latency target:** N/A (documentation phase).
