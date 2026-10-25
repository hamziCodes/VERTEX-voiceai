# Phase 10F Verification — 2026-10-25

## Outcome

Phase 10F replaces the placeholder MCP behavior with a tenant-owned, disabled-by-default registry and a bounded protocol boundary. Streamable HTTP now completes MCP initialize, inventory, call, and close exchanges against a local server. The voice tool loop exposes only the intersection of server inventory, server allowlist, and immutable agent allowlist, routes each name to one owner, forwards a stable idempotency key for side effects, and closes transports during session teardown.

Implementation commit: `460311d` (`feat: add secure mcp server boundary`).

## Implemented contracts

- Migration 023 stores tenant server metadata, credential references, allowlists, cached tool schemas, health state, indexes, ownership constraints, and forced RLS. It has no credential-value column and enables no server by default.
- The in-memory and PostgreSQL registries enforce tenant ownership, unique server names, unique tool owners, enabled-only inventory, and side-effect idempotency declarations.
- Streamable HTTP requires HTTPS, validates and re-resolves DNS on every request, pins the connection to the approved address, preserves the original host/SNI, rejects redirects and reserved credential headers, bounds time and bytes, and sanitizes failures.
- Loopback, private, link-local, metadata-service, non-global, user-info, fragment, and DNS-rebinding destinations fail closed unless a specific enterprise private-host allowlist permits the hostname.
- The MCP protocol path negotiates initialization and session IDs, lists tools, performs JSON-RPC calls, supports bounded JSON and SSE response framing, propagates cancellation, and sends session close.
- Stdio uses structured executable/argument arrays without a shell, requires test/development mode plus an explicit feature flag and executable allowlist, bounds line I/O, and terminates its subprocess on close. Legacy SSE explicitly reports unavailable.
- Tool definitions and arguments use bounded JSON Schema. Calls are capped at 8 KiB arguments, 16 KiB results, and 3 seconds. Side-effecting tools require server-declared support and a `session_id:turn_id:tool_call_id` idempotency key.
- The runtime rejects duplicate tool owners, exposes only agent-authorized external tools, returns raw results only to the LLM continuation, and closes all hosts during normal session teardown.

## Test-first evidence

The initial focused test collection failed because the secure registry, transport policy, and typed unavailable error did not exist. After implementing the boundary, integration review found that the voice pipeline still loaded only synchronous lifecycle tools and did not close external transports. Tests were extended before wiring asynchronous inventory, exact-owner routing, per-call idempotency, and teardown cleanup.

## Fresh verification

### Focused offline suite

```powershell
$env:UCVE_ENV='test'
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_PROVIDERS='0'
py -3.12 -m pytest tests/mcp/test_registry.py tests/mcp/test_streamable_http.py tests/mcp/test_ssrf_policy.py tests/mcp/test_stdio_policy.py tests/mcp/test_host_policy.py tests/mcp/test_tool_authorization.py tests/listening/test_tool_loop.py voice_engine_plan/tests/phase_tests/test_phase_22_mcp_tooling.py -q -p no:cacheprovider --basetemp hamza_local/pytest-phase10f-focused
```

Result: **54 passed**, exit 0. This covers registry isolation, duplicate ownership, inventory filtering, JSON-RPC/session flow, IP pinning, SSRF/DNS rebinding, redirects, malformed and oversized responses, timeouts, cancellation, credential redaction, stdio policy/protocol, idempotency forwarding, and cleanup.

### Disposable PostgreSQL proof

Migration 023 and its repository ran against the generated-credential Phase 09 disposable pgvector PostgreSQL container. Result: **1 passed**, exit 0. The test proves migration application, reference-only persistence, cross-tenant repository denial, and direct RLS isolation. The container, network, and volume were removed afterward.

### Full forced-offline regression

```powershell
$env:UCVE_ENV='test'
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_LIVE_DB_TESTS='0'
$env:RUN_LIVE_REDIS_TESTS='0'
py -3.12 -m pytest tests voice_engine_plan/tests/phase_tests -q -p no:cacheprovider --basetemp hamza_local/pytest-phase10f-full-rerun
```

Result: **796 passed, 7 skipped, 2 warnings**, exit 0. The warnings are the existing tests that intentionally exercise short fake HMAC keys. An earlier full run had one scheduler-sensitive Phase 10D RAG timing failure; the isolated test and the clean full rerun both passed.

### Static and integrity checks

- Ruff over all Phase 10F source and test files: **passed**.
- Strict mypy over the seven core MCP/tool-handler files with imports skipped: **passed**.
- `compileall` over MCP and runtime packages: **passed**.
- Plan integrity: **OK — 36 phases, tests, and trackers verified.**
- `git diff --check`, staged secret-pattern scan, and protected-path review: **passed**.

## Safety and limits

- No `.env` or raw key file was read.
- No secret value was printed, stored, staged, or committed.
- No live STT, LLM, TTS, carrier, external MCP, or business-system call occurred.
- The only MCP network tests used local fake transports; they incurred no charge.
- No shared or production database was changed.
- `.github/workflows`, `legacy_codebases`, and `docs/blueprint` were untouched.
- Real external integrations remain disabled until separately configured and approved.

## Next exact action

Start Phase 10G by implementing the focused local Knowledge Setup tab over the existing authenticated APIs. Verify keyboard use, responsive layouts, loading/error states, source progress, preview citations, activation, and clear offline/live labeling with Playwright screenshots. Do not collect provider or MCP credentials in that surface, and do not begin the Phase 10H close until the walkthrough is understandable without editing code or environment files.
