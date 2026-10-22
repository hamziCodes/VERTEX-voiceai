# Phase 07C — Stream-Safe Failover and Adapter Hardening

**Status:** READY FOR FINAL QA

**Depends on:** Phase 07B (`c6f43fc`).

## Goal

Make provider failover safe once streamed text, audio, or tool intent exists;
bound every routed stream; normalize LLM tools once; and prove failure behavior
without live provider traffic.

## Scope and implementation units

### 1. Stream commit contract

- Add one router-owned streaming API for STT, LLM, and TTS routes.
- Permit fallback only before the first meaningful output item.
- Treat text, tool calls, transcript hypotheses, and non-empty audio as commit
  evidence for their category.
- After commit, raise a typed interruption carrying sanitized provider/category
  evidence. Never replay output from the fallback route.
- Record circuit success only after clean stream completion and record the
  failing route when a stream ends with an error.

### 2. Deadlines and cancellation

- Enforce separate first-item, inter-item idle, and overall deadlines while
  iterating provider streams.
- Retain HTTP connect/write/pool limits in adapters; routed deadlines own
  first output, stream progress, and total duration.
- Close an abandoned async iterator on timeout, failure, or cancellation.
- Propagate caller cancellation without trying another provider.

### 3. Tool normalization

- Serialize `ToolDefinition` through one provider-neutral function.
- Accumulate fragmented OpenAI-compatible tool calls through one shared,
  deterministic implementation used by Groq, Gemini, and OpenAI.
- Reject malformed completed arguments as typed `invalid_output`; do not pass
  raw malformed arguments to tools.
- Remove the nonexistent OpenAI `LLMConfig.tool_choice` access and use the
  supported automatic selection policy when tools are present.

### 4. Side-effect safety and pipeline integration

- Route batch STT, streamed LLM, and streamed TTS through the stream-aware
  router.
- Do not synthesize an offline answer after committed LLM output.
- Suppress repeated tool calls in one turn using provider call ID when present,
  otherwise a stable name-and-arguments identity.
- Keep post-commit TTS interruption visible to the client and never replay
  already emitted audio.

### 5. Offline verification

- Test primary failure before commit, partial primary failure after commit,
  first/idle/overall timeout, cancellation, both-down behavior, and iterator
  cleanup.
- Contract-test schemas and fragmented multi-tool calls for all three LLM
  adapters.
- Test duplicate side-effect suppression and production no-mock behavior.
- Run focused tests, full forced-offline pytest, Ruff, compileall, plan
  integrity, diff checks, and secret/forbidden-scope scans.

## Files

- Modify: `core/providers/failover.py`, provider interfaces, Groq/Gemini/OpenAI
  adapters, and `worker_raw/orchestration/pipeline.py`.
- Create: shared stream deadline/commit and tool normalization contracts only
  where they reduce duplication.
- Add/expand: `tests/providers/`, `tests/listening/test_tool_loop.py`, and
  failover end-to-end scenarios.

## Boundaries

- No live providers, telephony calls, live databases, deployment, package
  publication, or paid traffic.
- Do not read `.env` or raw key files.
- Do not edit `.github/workflows`, `legacy_codebases/`, or `docs/blueprint/`.
- Live vendor quality and latency qualification remains a separately approved
  V5 activity.
- Durable credential persistence remains Phase 09.

## Verification

```powershell
$env:UCVE_ENV='test'
$env:RUN_MOCK_PROVIDERS='1'
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_LIVE_DB_TESTS='0'
py -3.12 -m pytest tests/providers tests/security/test_provider_credentials.py tests/e2e/scenarios/test_failover_e2e.py tests/listening/test_tool_loop.py -q
py -3.12 -m pytest -q
py -3.12 voice_engine_plan/scripts/verify_plan_integrity.py
```

## Exit criteria

- Primary output is never duplicated by a fallback.
- A fallback is demonstrably invoked before output commit.
- Tool schemas and fragmented calls are identical across supported LLM
  adapters, and a duplicate call cannot execute twice in one turn.
- Every routed stream has named first-item, idle, and overall bounds.
- Both-down and post-commit failures are typed, sanitized, and visible.
- Phase 07 is `READY FOR FINAL QA`; live qualification remains explicit.

## Human intervention

No human input is required for offline implementation. Final live vendor
qualification requires separate approval because it can incur provider cost.
