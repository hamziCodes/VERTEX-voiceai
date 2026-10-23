# Phase 13 — Self-Serve Agent Studio

**Status:** NOT STARTED

**Goal:** Let a nontechnical user securely onboard a business, configure/test/publish an agent, attach knowledge/tools/telephony, and inspect conversations using the same production contracts.

**Depends on:** Phases 05–12 for whichever features are included in v1.

**Audit coverage:** self-serve deployment gap, I08 surfaces, missing current Studio runtime.

## Human gate before implementation

Resolve H13. This is a separate product/design project. Before UI code, use the design process and obtain Hamzi's approval for scope, flows, visual direction and billing boundary.

## Proposed v1 workflow

1. Account/organization and role.
2. Business identity, use case, language and compliance questions.
3. Persona/prompt with safe structured fields and preview.
4. Provider/voice choice limited to eligible capabilities.
5. Knowledge and tools using the Phase 10 wizard API, durable states, preview results and citations.
6. Web test using packaged realtime contract and test quota.
7. Publish/version/rollback.
8. Optional inbound number assignment after telephony qualification.
9. Conversations, transcripts, recordings, extraction/review, usage and failures.

## Tasks

- [ ] Write approved product/design spec and route/API matrix; do not use current README-only Studio as proof of implementation.
- [ ] Implement authenticated organization/role navigation and tenant-scoped API client.
- [ ] Generate forms/validation from AgentConfig/runtime capability contracts where practical.
- [ ] Surface draft/autosave/publish version, validation failures and immutable active version clearly.
- [ ] Build voice test with honest test/live badge, latency panel, usage budget, interruption and error states.
- [ ] Turn the Phase 10 local Knowledge Setup flow into the production Studio experience without changing its durable API/state contract; never accept provider secret values in browser logs or URLs.
- [ ] Build telephony setup only for qualified scope; mark deferred outbound explicitly.
- [ ] Build conversation/history/review/usage screens from durable APIs, including pending/degraded/failed states.
- [ ] Add accessibility, responsive behavior, empty/loading/error states and audit-visible admin actions.
- [ ] After every visual change, run real Playwright screenshots and critique against the approved brief as required by `AGENTS.md`.

## Verification

- Component/unit tests for form and authorization states.
- API contract tests against generated/open schema.
- Playwright happy path and failure paths for two tenants/roles.
- Real screenshots at target desktop/mobile widths and accessibility scan.
- Offline create→test→publish→new session proves runtime behavior changes.

## Human intervention

Hamzi reviews design and critical screenshots, and completes any provider/carrier account provisioning himself. No publish/deploy in this phase.

## Exit criteria

- A nontechnical test user completes the approved v1 flow without code or environment editing.
- Studio never claims success for unfinished ingestion, call, recording, extraction, or delivery.
- Tenant isolation and usage controls pass end-to-end.
