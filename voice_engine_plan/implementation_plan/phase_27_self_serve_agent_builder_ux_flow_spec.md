# Phase 27: Self-Serve Agent Builder UX Flow Spec

## 1. Executive Summary & Core Logic

Specify the Agent Studio UI flows, screen inventory, and interaction contracts — **spec only, not full implementation** in this phase. Maps File 8 §5 feature checklist to wizard steps wired to Phase 26 domain model APIs. Grounded in habiba tenant portal patterns (`legacy_codebases/habiba-sdk-agent/tenant_portal_api/`, frontend SDK preview flows AUDIT_04 §1) and awaazlabs dashboard surface areas (knowledge, extraction UI folders AUDIT_02 §6 — UI without backend until Phases 21/23).

Delivers UX spec artifacts Studio engineers implement against: wireflow docs, component contracts, and acceptance criteria. Includes **Human Review Queue** UI stub (Phase 21) and **RTL voice validation** UX surfacing (Phase 15).

Depends on Phase 26 APIs, Phase 13 auth roles, Phase 25 error display patterns, Phase 14 metering (test-call allowance).

**Hosting:** **standalone SPA** (`agent-studio/`), not embedded in tenant portal. **Test calls:** **non-metered sandbox allowance** separate from production quota. **Outbound UI:** **not built** — Phase 19 deferred outbound server-side.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| React + TypeScript standalone SPA | Headless SDK + separate dashboard architecture (File 1) |
| OpenAPI-generated client types | Phase 28 alignment |
| Wizard with validation gates | Publish blocked until Phase 26 validator passes |
| Live TTS preview via control-plane proxy | habiba voice preview workflow (AUDIT_04 CI `refresh-voice-previews`) |
| Role-gated screens | Phase 13 RBAC — `tenant_admin` vs `tenant_editor` |
| Shared auth with control-plane | OIDC/session from Phase 13 — SPA on separate origin |

**Reference docs:** blueprint File 08 §5; habiba tenant portal routes; awaazlabs dashboard audit folders.

## 3. What / How / Why

- **What (screen inventory + flows):**
  1. **Agent list** — create, duplicate, archive; shows publish status + last test call result
  2. **Persona editor** — system prompt with visible "tenant DATA, isolated from core instructions" banner (File 6 §1 security surfacing)
  3. **Languages & voices** — per-language voice picker; **RTL validation error** inline for Arabic if voice fails Phase 15 gate; live TTS preview button
  4. **Providers** — drag-and-drop priority per STT/LLM/TTS; shows Phase 06 capability table status
  5. **Tools & MCP** — connect MCP server form (transport default HTTP/SSE per Phase 22); test connection button
  6. **Knowledge bases** — upload PDF/FAQ; ingestion status from Phase 23 worker
  7. **Extraction schema builder** — visual form over `TenantExtractionSchema`; field count vs tenant `max_fields` indicator
  8. **Telephony** — DID assignment, trunk list (Phase 19) inbound-only; **no outbound campaign UI** (Phase 19 `[LATER]`)
  9. **Compliance** — tier selector with HIPAA BAA acknowledgment gate (Phase 10)
  10. **Test call panel** — embed Phase 28 SDK widget; uses **sandbox test-call allowance** (see below)
  11. **Human review queue** — list low-confidence extractions (Phase 21 stub); approve/reject actions
  12. **Live monitor** — read-only active calls `[LATER]` full impl — stub panel spec (File 7 §5)
  - **Primary wizard flow:** Create → Persona → Languages → Providers → (optional MCP/KB/Extraction) → Compliance → Test → Publish
  - **`TestCallAllowance` UX:** display remaining sandbox minutes/calls (default **30 min/month/tenant**, non-metered against Phase 14 production quota — separate counter in Phase 14 `usage_kind=test_call_sec`)
  - **Error UX:** map Phase 25 generic codes to inline field errors + toast (no raw server traces)
  - **Accessibility:** RTL layout support for Arabic builder labels
  - **Outbound/campaign screens:** **excluded from v1 inventory** — document deferral in `OUTBOUND_UI_DEFERRED.md`
- **How:** Deliver `docs/agent-studio/` spec pack + `agent-studio/README.md` as standalone SPA spec. Auth: redirect to control-plane OIDC, return JWT to SPA. **No portal iframe embedding.**
- **Why this approach:** Building UI before domain model caused awaazlabs drift (AUDIT_02). Standalone SPA matches headless architecture. **Metered test calls rejected** — blocks iteration during agent build. **Outbound UI rejected** — no server capability in v1 (Phase 19).

## Deliverables

- `docs/agent-studio/WIREFLOWS.md` — mermaid/user-journey diagrams
- `docs/agent-studio/SCREEN_INVENTORY.md`
- `docs/agent-studio/COMPONENT_CONTRACTS.md` — props/events per screen
- `docs/agent-studio/ACCEPTANCE_CRITERIA.md` — testable UX gates
- `docs/agent-studio/HUMAN_REVIEW_QUEUE_UX.md` — Phase 21 queue screens
- `docs/agent-studio/RTL_BUILDER_NOTES.md` — Arabic builder UX requirements
- `docs/agent-studio/TEST_CALL_BILLING.md` — sandbox allowance vs production quota
- `docs/agent-studio/OUTBOUND_UI_DEFERRED.md` — explicit non-scope for v1
- `agent-studio/README.md` — standalone SPA spec index + future impl pointer

## 4. Compute & Resource Profile (if applicable)

Spec phase only — no runtime. TTS preview proxy (when implemented): ~200 ms per preview clip — rate-limited 10/min/tenant. Test sandbox: 30 min/month default — configurable platform-wide.

## 5. Compliance Notes (if applicable)

Studio must not display raw API keys — Phase 09 refs shown as masked `••••`. HIPAA tier selector requires explicit BAA checkbox with timestamp. Human review queue displays redacted transcript excerpts only (Phase 11).

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Studio hosting:** **standalone SPA** — shared Phase 13 auth; not portal-embedded.
2. **Test call billing:** **non-metered sandbox allowance** (default 30 min/month/tenant) — separate from Phase 14 production quota.
3. **Outbound campaign UI:** **not built in v1** — Phase 19 outbound deferred; no stub screen in primary inventory.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_27_agent_builder_ux.py`
- **Asserts:** all File 8 §5 checklist items mapped to a screen in `SCREEN_INVENTORY.md`; wizard steps reference Phase 26 API endpoints; human review queue flow documented; RTL validation UX references Phase 15 rule; acceptance criteria cover publish gate + test call sandbox billing; outbound explicitly excluded; standalone SPA documented; no implementation code required for pass.
- **Pass threshold:** 100% checklist coverage in spec docs.
- **Latency target:** N/A (documentation phase).
