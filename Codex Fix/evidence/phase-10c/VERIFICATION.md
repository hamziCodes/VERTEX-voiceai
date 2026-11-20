# Phase 10C Verification — 2026-10-24

## Outcome

Phase 10C replaces fake text ordering and silent lexical fallback with an offline local embedding boundary, a durable parse-to-embed worker stage, real 384-dimensional pgvector persistence, and retrieval constrained to an authenticated tenant and an exact agent-bound knowledge-base revision.

Implementation commit: `5dc1c02` (`feat: add agent scoped pgvector retrieval`).

## Implemented contracts

- `LocalONNXEmbedder` loads only a pre-provisioned local bundle containing `model.onnx`, `tokenizer.json`, and reviewed metadata. Runtime model downloads are absent.
- The approved model contract is `intfloat/multilingual-e5-small`, 384 dimensions, with separate E5 query and passage prefixes, attention-mask mean pooling, normalization, bounded inputs, and inference moved off the event loop.
- Compliance policy keeps local embeddings as the default and rejects an unconfigured cloud adapter. HIPAA and strict GDPR tiers cannot select a cloud embedder.
- Parsing hands sources to a durable `embedding` job stage. Workers claim leases, embed bounded batches, validate vector count, dimensions, finite values, and stable model metadata, then atomically complete source/job state.
- PostgreSQL retrieval uses cosine distance over pgvector and requires exact tenant, agent binding, knowledge base, revision, embedding model, and embedding version. Results expose citations and scores.
- Production database errors and missing scope fail explicitly. The lexical retriever remains only as an explicitly seeded in-memory compatibility path for tests.
- Speculative retrieval includes tenant, agent, base, and revision in its reuse scope, so revision changes invalidate prior results.

## Fresh verification

### Focused offline regression

```powershell
$env:UCVE_ENV='test'
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_LIVE_DB_TESTS='0'
$env:RUN_LIVE_REDIS_TESTS='0'
& 'hamza_local/phase10-venv/Scripts/python.exe' -m pytest tests/rag tests/db/test_knowledge_repository.py voice_engine_plan/tests/phase_tests/test_phase_23_realtime_rag.py tests/e2e -q -p no:cacheprovider --basetemp hamza_local/pytest-phase10c-focused
```

Result: **109 passed**, exit 0.

### Disposable PostgreSQL/pgvector

The Phase 09 Docker compose test stack was started with a generated local password. The Phase 10A, 10B, and 10C integration tests ran against a fresh local `pgvector/pgvector:pg16` database.

```powershell
& 'hamza_local/phase10-venv/Scripts/python.exe' -m pytest tests/db/test_phase10a_live_integration.py tests/db/test_phase10b_live_ingestion.py tests/db/test_phase10c_live_pgvector.py -q -p no:cacheprovider --basetemp hamza_local/pytest-phase10c-disposable
```

Result: **3 passed**, exit 0. Coverage includes migrations, durable parse-to-embed handoff, vector persistence, restart/no-reclaim behavior, similarity order, citations/scores, unbound-agent denial, cross-tenant denial, and revision switching. Containers, network, volumes, and generated environment variables were removed afterward.

### Full forced-offline regression

```powershell
$env:UCVE_ENV='test'
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_LIVE_DB_TESTS='0'
$env:RUN_LIVE_REDIS_TESTS='0'
& 'hamza_local/phase10-venv/Scripts/python.exe' -m pytest -q -p no:cacheprovider --basetemp hamza_local/pytest-phase10c-full
```

Result: **731 passed, 6 skipped, 2 warnings**, exit 0. The warnings are existing short test-HMAC warnings.

### Static, packaging, and integrity checks

- Ruff format and lint over all Phase 10C source and tests: **passed**.
- Strict mypy over the changed runtime modules: **passed**, 11 source files.
- `compileall` over `core` and `worker_jobs`: **passed**.
- `uv lock --check`: **passed**, 78 packages resolved.
- Plan integrity: **OK — 36 phases, tests, and trackers verified.**
- `git diff --check`, staged secret-pattern scan, and protected-path review: **passed**.

## Safety and deployment intervention

- No `.env` or raw key file was read.
- No secret value was printed, stored, staged, or committed.
- No live STT, LLM, TTS, telephony, cloud embedding, MCP, or external business-system call occurred.
- No shared or production database was changed.
- `.github/workflows`, `legacy_codebases`, and `docs/blueprint` were untouched.
- Before production deployment, Hamzi or the deployment operator must provision the reviewed local model bundle outside Git, pin its upstream revision, verify artifact checksums and license, and set `UCVE_EMBEDDING_MODEL_PATH`. The application intentionally fails closed when that bundle is absent.

## Next exact action

Start Phase 10D with failing tests for untrusted prompt framing, pinned runtime knowledge scope, bounded citations/context, soft and hard retrieval deadlines, cancellation, degraded no-knowledge continuation, revision-aware caching, and latency telemetry. Do not begin lifecycle actions from 10E until 10D is verified and committed.
