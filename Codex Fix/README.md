# Codex Fix

This folder is the execution system for turning the audited Wavia/UCVE codebase into a measurable production release. Its source of truth is [`../AUDIT.md`](../AUDIT.md), checked against the current working tree and working legacy implementations.

## Read in this order

1. [`EDUCATION.md`](EDUCATION.md) — why the current engine feels slow and what the legacy engines do differently.
2. [`IMPLEMENTATION.md`](IMPLEMENTATION.md) — phase order, dependencies, release gates, and operating rules.
3. [`VERIFICATION.md`](VERIFICATION.md) — offline-first verification contract and commands.
4. [`HUMAN_INPUT.md`](HUMAN_INPUT.md) — decisions, credentials, paid actions, and staging work requiring Hamzi.
5. [`EXECUTION_TRACKER.md`](EXECUTION_TRACKER.md) — authoritative phase status and evidence index.
6. [`TRACEABILITY.md`](TRACEABILITY.md) — every audit finding mapped to phases.
7. [`phases/`](phases/) — detailed executable phase plans.

## Status rules

- `NOT STARTED`: no implementation work has begun.
- `IN PROGRESS`: code is changing; acceptance has not passed.
- `BLOCKED — HAMZI`: a decision, credential, account action, paid test, or production access is required.
- `BLOCKED — TECHNICAL`: an upstream phase or reproducible defect prevents progress.
- `VERIFICATION NEEDED`: implementation is complete but required evidence is missing.
- `COMPLETE`: every automated check and human gate passed.

Only one phase may be `IN PROGRESS` unless `IMPLEMENTATION.md` explicitly says otherwise. Code written is not phase completion; the exit gate must pass.

## Execution rule

Before a risky multi-file phase, create a rollback commit preserving existing user changes. Do not touch `.github/workflows`, deploy, publish, place calls, use paid providers, or reveal secret values without Hamzi's explicit approval. Environment files may be inspected only for variable names unless Hamzi explicitly authorizes more.
