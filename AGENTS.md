# AGENTS.md

## Cursor Cloud specific instructions

This repository is **documentation-only**. It is the planning/blueprint workspace for the
"Unified Core Voice Engine" (UCVE / VERTEX_voiceai). There is **no application code, no
tests, no build system, and no dependencies to install** — the engine code is explicitly
`NOT STARTED` (see `memory_bank/active_context.md`).

Contents:
- `docs/blueprint/` — the 9-file design suite (`01`…`09`) plus `FINALIZATION_LOG.md`.
- `auit_docs/` — forensic audit dossiers (`AUDIT_01`…`05` + `AUDIT_PROGRESS.md`), kept as a
  permanent provenance record. (Directory name is `auit_docs`, note the spelling.)
- `memory_bank/` — condensed agent context; read this first.

### Build / test / run / lint
There is nothing to build, run, lint, or test. No package manager manifests exist
(`package.json`, `requirements.txt`, `pyproject.toml`, etc.), so the startup update script is
a no-op. Do not add tooling or dependencies unless a task explicitly asks you to start
implementing the engine.

To sanity-check the doc set is intact and cross-referenced, you can run an ad-hoc,
dependency-free check with the pre-installed Python 3 (`python3`) — no packages required.

### Agent bootstrap read order (from `memory_bank/cursor_rules_and_skills.md`)
1. `memory_bank/active_context.md` — current state + next milestones
2. `memory_bank/codebase_maps.md` — paths/aliases
3. `memory_bank/audit_synthesis.md` — harvest map + debt IDs (D1–D14)
4. `memory_bank/target_unified_engine.md` — target architecture
5. Open full `auit_docs/AUDIT_0N_*.md` only when a claim needs line-level proof

### Gotchas
- The four legacy "inspiration" codebases referenced throughout the audits are **git-ignored
  and not present** in this repo (see `.gitignore`); do not expect to find or run them here.
- When engine implementation begins, the intended monorepo layout is specified in
  `docs/blueprint/09_DEVELOPER_IMPLEMENTATION_ROADMAP_AND_AUTONOMY_RULES.md` (§1). That is
  when build/test tooling would first be introduced.
- Never read or commit `.env` / secrets.
