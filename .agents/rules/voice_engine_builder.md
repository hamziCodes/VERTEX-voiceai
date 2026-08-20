# Voice Engine Builder — Master Operational Rule

Active build authority: `voice_engine_plan/` (phases 00–35). Strategic reference only: `docs/blueprint/`.

## 1. Read-Only Boundaries

**Never edit** (read for harvest/provenance only):

- `legacy_codebases/` and `memory_bank/legacy_codebases/`
- `docs/blueprint/`

**Implement only in** approved source paths:

- `core/`, `control-plane/`, `worker-raw/`, `post-call/`
- `infra/db/migrations/`, `infra/docker/`, `infra/scaling/`
- Root workspace files (`pyproject.toml`, `README.md`, `.python-version`) when Phase 00+ requires
- `tests/` (repo root harness), `docs/developer/`, `docs/runbooks/` when a phase spec names them

**Plan folder edits** (trackers, changelog) are allowed only during phase execution steps 4–5 below.

## 2. Phase Execution Protocol (00 → 35)

When executing Phase `XX`, follow this sequence **in order**. Do not skip steps.

### Step 1 — Read & Align

Read `voice_engine_plan/implementation_plan/phase_XX_*.md`:

- §2 Tech Stack & Best Practices
- §3 What / How / Why + **Deliverables**
- §7 Test Spec

Set `EXECUTION_TRACKER.md` status → `IN_PROGRESS` before coding.

### Step 2 — Implement

- Write **complete, production-ready** code in §3 target paths.
- **No placeholder stubs**, `# TODO`, or skipped logic for in-scope deliverables.
- Harvest patterns from `legacy_codebases/` (read-only); do not copy wholesale without adaptation to UCVE contracts.
- Match existing conventions in the target directory once established.

### Step 3 — Verify

```bash
python -m pytest voice_engine_plan/tests/phase_tests/test_phase_XX_*.py -v
```

- **Pass threshold:** 0 failures; previously skipped checks for this phase must turn green.
- If human intervention is required per §6, set status → `READY_FOR_MANUAL_TEST` and stop with explicit ask.

### Step 4 — Structural Integrity

After any spec or tracker touch:

```bash
python voice_engine_plan/scripts/verify_plan_integrity.py
```

Must exit 0 before marking complete.

### Step 5 — Tracker Synchronization (Mandatory)

| File | Action |
|------|--------|
| `voice_engine_plan/implementation_plan/EXECUTION_TRACKER.md` | `COMPLETED` + sign-off date when green; else `IN_PROGRESS` or `READY_FOR_MANUAL_TEST` |
| `voice_engine_plan/tests/phase_tests/TEST_TRACKER.md` | Record run command, result (pass/fail/skip counts), date |
| `voice_engine_plan/CHANGELOG_PLAN.md` | Log any deliverable boundary shift vs spec |

Re-run integrity script after tracker edits.

## 3. Guardrails

- **Concise output:** Summarize deliverables and paste CLI test summary — do not dump full diffs/files unless asked.
- **No unilateral assumptions:** Unmapped edge cases or vendor ambiguity → halt and present tradeoffs; do not guess.
- **One phase per task** unless user explicitly requests a batch.
- **Commits & Push:** Automatically commit and push to branch `hamza` after completing every phase (NO COAUTHORS).


## 4. Resolved Terminology (Strict)

| Concept | Canonical value |
|---------|-----------------|
| RBAC role | `tenant_editor` |
| Publish audit event | `agent_config_published` |
| Compliance tiers | `hipaa`, `gdpr_strict` |
| Metering usage kind (sandbox) | `test_call_sec` |

## 5. Phase Index Quick Reference

| Phase | Focus |
|------:|-------|
| 00 | Monorepo baseline (`uv`, `core/`, lint) |
| 01–04 | Audio types, buffering, FSM, barge-in |
| 05–07 | Providers, registry, observability |
| 08–14 | Multi-tenant, vault, compliance, auth, metering |
| 15–17 | Multilingual (en/ur/ar/ms), normalization, pipeline |
| 18–19 | Telephony/SIP (Telnyx + DirectSIP) |
| 20–21 | Post-call records, CRM dispatch |
| 22–23 | MCP tooling, RAG |
| 24–25 | Latency SLO, error taxonomy |
| 26–28 | Agent builder, UX spec, SDK/API |
| 29–35 | DX docs, deploy, scale, security, E2E, release, finalization |

Full index: `voice_engine_plan/README.md`.

## 6. Session Bootstrap (Optional Context)

Before Phase 00+ work, skim (read-only):

1. `voice_engine_plan/implementation_plan/EXECUTION_TRACKER.md` — current status
2. `memory_bank/active_context.md` — session state (do not treat as override of phase specs)

For deep phase execution workflow, invoke skill: **voice-engine-phase-executor**.
