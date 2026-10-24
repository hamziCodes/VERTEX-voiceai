# Phase 10B Verification — 2026-10-24

## Outcome

Phase 10B replaces the binary `str(content_raw)` and process-memory ingestion path with bounded byte validation, structure-aware parsing, tenant object storage, durable leased jobs, traceable chunks, safe retry/restart behavior, and authenticated upload, FAQ, and deletion APIs.

Implementation commit: `0c8ab9a` (`feat: ingest common business documents safely`).

The supported matrix is PDF, DOCX, TXT, Markdown, CSV, XLSX, and FAQ JSON. Legacy `.doc`, PowerPoint, archives, images, audio/video, OCR, URLs, and crawling remain unsupported. A PDF with no extractable text returns `pdf_no_extractable_text` because OCR is outside this phase.

Parsed sources stop at `embedding`. Phase 10C owns local embeddings, vector completion, and real pgvector retrieval; Phase 10B does not report a source as ready.

## Implemented contracts

- Uploads are read in bounded chunks and capped before parsing. Extension, declared media type, signatures, safe normalized names, byte limits, binary-text rejection, and SHA-256 integrity are enforced.
- ZIP-based Office documents are bounded by entry count, expanded bytes, per-entry bytes, compression ratio, nested-archive rejection, expected structure, and macro/binary rejection.
- PDF parsing rejects encrypted files, caps pages and extracted characters, and reports image-only files without pretending OCR occurred.
- DOCX extracts paragraphs and tables. XLSX uses `read_only=True`, `data_only=True`, and `keep_links=False`; formulas, macros, scripts, and remote resources are not executed.
- CSV/XLSX row, column, and cell bounds and FAQ item/question/answer bounds are enforced.
- Chunks preserve source IDs and citations for page, heading/line, paragraph/table row, sheet/row, CSV row, or FAQ item.
- Local/test objects use atomic bounded filesystem writes under opaque tenant keys. Protected environments require configured S3-compatible storage and fail closed; S3 support is the explicit `knowledge-s3` package extra.
- Upload duplicates in the pending revision reuse the existing durable source and remove the redundant raw object.
- PostgreSQL workers claim queued or expired jobs with `FOR UPDATE SKIP LOCKED`, bounded leases, idempotent chunk replacement, safe terminal errors, and retryable failed jobs.
- Deletion removes the raw object idempotently before the database source; a retry can finish safely if the database step is interrupted.

## Test-first evidence

The first focused run failed during collection with four missing-module errors for validation, parsers, and object storage. After the first implementation, a Markdown test failed because a heading appeared only in citation metadata; the parser was corrected to keep the heading in searchable text as well.

The first full-suite run exposed two regressions. The legacy phase test still passed pre-extracted PDF text, and installing `boto3` by default changed an existing KMS fail-closed test. The compatibility path now accepts only explicit pre-extracted PDF text without stringifying binary input, and S3 dependencies moved to the optional `knowledge-s3` extra. The next full run was green.

## Fresh verification

### Focused offline suite

```powershell
& 'hamza_local/phase10-venv/Scripts/python.exe' -m pytest tests/rag/test_file_validation.py tests/rag/test_ingestion_formats.py tests/rag/test_ingestion_limits.py tests/rag/test_knowledge_object_store.py tests/rag/test_knowledge_api.py tests/db/test_knowledge_repository.py -q -p no:cacheprovider --basetemp hamza_local/pytest-phase10b-final-focused
```

Result: **27 passed**, one third-party Starlette deprecation warning, exit 0.

Coverage includes safe names/traversal, MIME/signature mismatch, binary text, unsupported formats, Office macro/archive bounds, TXT/Markdown/CSV/DOCX/XLSX/FAQ extraction, formulas not executed, malformed DOCX, encrypted and image-only PDFs, file/row/cell/FAQ limits, parser timeout, retry, duplicate upload, tenant API behavior, restart, local object round trip, idempotent cleanup, and protected-storage refusal.

### Disposable PostgreSQL/pgvector

```powershell
py -m pytest tests/db/test_phase10a_live_integration.py tests/db/test_phase10b_live_ingestion.py -q
```

Executed against generated local Docker credentials and a disposable `pgvector/pgvector:pg16` database. Result: **2 passed**, exit 0. The test proves migrations, tenant repository access, durable source/job creation, leased claim, parsing, chunk persistence, terminal job state, and no second claim after restart. Containers, network, volumes, and generated environment variables were removed afterward.

### Full forced-offline regression

```powershell
$env:UCVE_ENV='test'
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_LIVE_DB_TESTS='0'
$env:RUN_LIVE_REDIS_TESTS='0'
py -m pytest -q -p no:cacheprovider
```

Result: **721 passed, 5 skipped, 3 warnings**, exit 0. The warnings are the existing Starlette TestClient deprecation and two short test-HMAC warnings.

### Static, packaging, and integrity checks

- Ruff format check over all Phase 10B source/tests: **passed**.
- Ruff changed-scope lint: **passed**. Repository-wide Ruff remains outside this checkpoint because older untouched files have pre-existing violations.
- Strict mypy over the changed runtime modules: **passed**, 20 source files.
- `compileall` over `core`, `control_plane`, and `worker_jobs`: **passed**.
- `uv lock --check` against the regenerated valid lock: **passed**, 68 packages resolved.
- Plan integrity: **OK — 36 phases, tests, and trackers verified.**
- `git diff --check`, staged credential-pattern scan, and protected-path review: **passed**.

## Safety and limits

- No `.env` or raw key file was read.
- No secret value was printed, stored, staged, or committed.
- No live STT, LLM, TTS, telephony, cloud embedding, MCP, S3, or business-system call occurred.
- No shared or production database was changed.
- `.github/workflows`, `legacy_codebases`, and `docs/blueprint` were untouched.
- The Microsoft Store Python 3.12 launcher remains unavailable. Verification used the existing gitignored `hamza_local/phase10-venv` with Python 3.14.2.

## Next exact action

Start Phase 10C with failing tests for deterministic embedding policy, persisted 384-dimensional vectors, tenant/agent/revision-scoped pgvector retrieval, citations/scores, restart behavior, dimension mismatch, and removal of production mock fallback. Do not begin realtime prompt injection or latency work from 10D until 10C is verified and committed.
