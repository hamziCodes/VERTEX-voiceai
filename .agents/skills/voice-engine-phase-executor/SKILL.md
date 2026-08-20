---
name: voice-engine-phase-executor
description: >-
  Executes UCVE voice engine phases 00–35 from voice_engine_plan/ with strict tracker sync, pytest verification, and integrity checks. Use when the user asks to execute, implement, or complete a phase, start Phase 00, continue the build, or run phase tests.
---

# Voice Engine Phase Executor

Deterministic workflow for implementing phases 00–35 of the Unified Core Voice Engine (UCVE).

## When to Use

- User says: "Execute Phase XX", "Start Phase 00", "Continue build", "Implement phase_XX"
- User references `voice_engine_plan/implementation_plan/phase_*.md`
- User wants tracker updates after phase work

## Pre-Flight Checklist

- [ ] Identify phase number XX (00–35)
- [ ] Read phase spec §2, §3, §7
- [ ] Confirm read-only paths untouched (`legacy_codebases/`, `docs/blueprint/`)
- [ ] Set `EXECUTION_TRACKER.md` → `IN_PROGRESS`

## Execution Workflow

### 1. Ingest Spec

Open `voice_engine_plan/implementation_plan/phase_XX_*.md`.

Extract:

- **Deliverables** — exact file paths from §3
- **Dependencies** — prior phases that must be COMPLETED
- **Env vars** — from §7 and `TEST_TRACKER.md` row for XX
- **§6 flags** — if any unresolved `? —`, set `READY_FOR_MANUAL_TEST` and ask user

### 2. Implement

Write code only in §3 deliverable paths under:

`core/`, `control-plane/`, `worker-raw/`, `post-call/`, `infra/`, root workspace files as specified.

Rules:

- Zero placeholder stubs for in-scope deliverables
- Production-ready: typed, tested, matches phase contracts
- Port from `legacy_codebases/` read-only; adapt to UCVE types (Phase 01+)

### 3. Verify Phase Test

```bash
python -m pytest voice_engine_plan/tests/phase_tests/test_phase_XX_*.py -v
```

On failure: fix implementation, re-run until 0 failures.

Common env (Phases 08+):

```bash
# Example — check TEST_TRACKER.md for exact phase needs
export DATABASE_URL=postgresql://localhost/ucve_dev
export REDIS_URL=redis://localhost:6379/0
```

### 4. Integrity Check

```bash
python voice_engine_plan/scripts/verify_plan_integrity.py
```

Must print `OK: 36 phases, tests, and trackers verified.`

### 5. Sync Trackers

**EXECUTION_TRACKER.md** — update row for phase XX:

- Status: `COMPLETED` (or `READY_FOR_MANUAL_TEST`)
- Sign-off Date: `YYYY-MM-DD` when completed

**TEST_TRACKER.md** — append execution note if format allows, or ensure run command matches.

**CHANGELOG_PLAN.md** — if deliverable paths or behavior diverged from spec:

```markdown
## YYYY-MM-DD — Phase XX adjustment
- [what changed and why]
```

Re-run integrity script.

### 6. Report (Concise)

Return to user:

1. Phase XX status
2. Deliverables created/modified (paths only)
3. Pytest summary (passed/failed/skipped counts)
4. Integrity script result
5. Next recommended phase (XX+1 if sequential)

## Phase 00 Quick Start

Spec: `voice_engine_plan/implementation_plan/phase_00_monorepo_planning_baseline.md`

Deliverables:

- `pyproject.toml` (uv workspace, ruff, mypy)
- `uv.lock`, `.python-version` (3.12)
- `core/`, `control-plane/`, `worker-raw/`, `tests/` skeletons
- `core/compliance/__init__.py` placeholder
- Root `README.md` stub

Verify:

```bash
python -m pytest voice_engine_plan/tests/phase_tests/test_phase_00_monorepo_baseline.py -v
python voice_engine_plan/scripts/verify_plan_integrity.py
```

## Terminology Lock

| Use | Not |
|-----|-----|
| `tenant_editor` | tenant_admin, editor |
| `agent_config_published` | config_published, agent_published |
| `hipaa`, `gdpr_strict` | HIPAA tier variants |
| `test_call_sec` | test_seconds, sandbox_sec |

## Halt Conditions

Stop and ask user when:

- §6 contains open ambiguity (`? —`)
- Spec requires vendor choice not resolved in EXECUTION_TRACKER
- Phase test needs external credentials not documented in TEST_TRACKER
- Deliverable would require editing read-only paths

## MCP Setup

For recommended MCP servers to accelerate this workflow, see [mcp-setup.md](mcp-setup.md).

## Additional Resources

- Phase index: `voice_engine_plan/README.md`
- Full test suite: `pytest voice_engine_plan/tests/phase_tests/ -v`
- Antigravity rule: `.agents/rules/voice_engine_builder.md`
