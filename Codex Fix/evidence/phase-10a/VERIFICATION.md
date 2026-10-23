# Phase 10A Verification — 2026-10-24

## Outcome

Phase 10A implements the durable knowledge domain and management API. It replaces the fixed `ready`/`42` response with tenant-owned records, real source/chunk counts, bounded lifecycle states, revision activation, failed-source retry, and knowledge binding through a new immutable agent configuration version.

Implementation commit: `b2b75a7` (`feat: add durable tenant knowledge workflow`).

## Implemented

- Migration 022 creates knowledge bases, sources, ingestion jobs, agent bindings, tenant-composite foreign keys, checks, indexes, grants, and forced RLS.
- The legacy 1536-dimensional empty scaffold is converted to the declared 384-dimensional local embedding profile. A non-empty legacy chunk table blocks conversion with `legacy_knowledge_chunks_require_reingestion` rather than discarding data.
- PostgreSQL and local/test repositories share tenant and lifecycle contracts.
- Knowledge create/list/detail/status, source status, retry, activation, and agent binding routes derive tenant identity from authenticated context.
- Binding requires both `knowledge:write` and `agent:write` and publishes a new agent configuration version.
- Active revision data remains available while the next revision is processing or failed.
- Internal object references are omitted from source-status API responses.
- External systems, uploads, parsers, embeddings, retrieval, MCP, and live providers remain disabled/out of scope for 10A.

## Test-first evidence

The initial Phase 10A run failed with two missing-migration failures and four missing-repository/API errors. Additional red tests caught and then proved fixes for:

- a PostgreSQL filter appended after `GROUP BY`;
- missing `agent:write` authorization and uncaught missing-agent errors;
- a failed pending revision disabling an already active revision;
- internal object references exposed in a management response;
- missing binding idempotency uniqueness.

## Automated verification

### Focused and compatibility

```text
pytest tests/db/test_knowledge_migration.py tests/db/test_knowledge_repository.py
       tests/rag/test_knowledge_api.py tests/auth/test_route_matrix.py
       tests/e2e/test_system_endpoints_e2e.py tests/agents
Result: 50 passed, 1 dependency deprecation warning
```

### Disposable PostgreSQL/pgvector

```text
pytest tests/db/test_phase09_live_integration.py
       tests/db/test_phase10a_live_integration.py
Result: 2 passed
```

The disposable test proved clean migrations, migration idempotency, `vector(384)`, RLS tenant reads, denied cross-tenant writes, real PostgreSQL repository create/list/get, and binding persistence. Containers, network, tmpfs data, and volumes were removed after the run.

### Full forced-offline regression

```text
pytest tests voice_engine_plan/tests/phase_tests
Result: 701 passed, 4 skipped, 3 warnings
```

The warnings are one Starlette/httpx dependency deprecation and two existing short test-key warnings.

### Static gates

```text
Ruff: passed
Strict mypy on changed production modules: passed
compileall: passed
Plan integrity: OK — 36 phases, tests, and trackers verified
git diff --check: passed
Protected paths: passed
Mock/fake-count/credential-pattern scan: passed
```

The Microsoft Store Python 3.12 launcher was unavailable because its package logon session had ended. Verification ran in a disposable gitignored `hamza_local/phase10-venv` using Python 3.14.2 and project dependencies. No dependency or source manifest was changed.

## Safety

- No environment or raw key file was read.
- No secret value was printed, stored, staged, or committed.
- No live STT, LLM, TTS, telephony, cloud embedding, MCP, or business-system call occurred.
- Migration 022 ran only against generated disposable local PostgreSQL/pgvector instances.
- No shared or production database was changed.
- `.github/workflows`, `legacy_codebases`, and `docs/blueprint` were untouched.

## Next exact action

Start Phase 10B by writing failing validation/parser tests for bounded PDF, DOCX, TXT, Markdown, CSV, XLSX, and FAQ ingestion. Do not begin embeddings or realtime retrieval until 10B is verified and committed.
