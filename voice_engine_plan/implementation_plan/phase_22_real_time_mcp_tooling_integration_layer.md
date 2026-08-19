# Phase 22: Real-Time MCP Tooling Integration Layer

## 1. Executive Summary & Core Logic

Wire tenant-configurable MCP servers and built-in session-lifecycle tools into the Phase 17 pipeline at the LLM tool-calling boundary. Generalizes habiba's hardcoded `FIXED_TOOLS` (`legacy_codebases/habiba-sdk-agent/worker/tools.py:52–116` — `end_conversation_summary`, `escalate_to_human`) into an open MCP host while preserving those two tools as always-available defaults. Entire layer is `[NEW]` — AUDIT_05 §3 confirms zero MCP implementation across all four legacy repos — but injection point is evidenced: habiba passes tools to `Agent(...)` beside persona frame (`worker/main.py:71`), MULTI/v3 land before `generate_reply` / `build_messages` (AUDIT_01/03/04 §6).

Depends on Phase 05 `ToolDefinition`, Phase 03 FSM `TOOL_EXECUTING` state, Phase 07 tracing, Phase 09 credential vault for MCP endpoints, Phase 10 DATA-framing rules (File 6 §1).

**v1 execution policy:** **serial** tool calls only (Phase 03 parallel tools deferred); **3 s** hard timeout per tool with spoken fallback for longer operations; **HTTP/SSE** as default MCP transport for cloud multi-tenant deployment (`stdio` reserved for local dev).

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| `MCPHost` in `core/mcp/` | File 6 §2.1 — worker acts as MCP client/host |
| `sse` / `streamable_http` default; `stdio` local-dev only | Cloud tenants need remote tools; stdio is single-machine pattern |
| DATA-framed tool results | habiba persona isolation pattern — AUDIT_04 §1 |
| `asyncio.to_thread` for sync tool I/O | Fixes habiba sync `psycopg` in async handlers (AUDIT_04 §5) |
| `ConversationalFillerSynth` + timeout fallback utterance | File 6 §2.3 — filler during slow tools; 3 s cap prevents dead air |

**Reference docs:** blueprint File 06 §1–2; habiba `worker/tools.py`; File 02 §2.1 `TOOL_EXECUTING` state.

## 3. What / How / Why

- **What:**
  - `MCPServerConfig`: `{server_id, tenant_id, transport, endpoint, allowed_tools, credentials_ref}` — from Phase 26 **`AgentConfig.mcp_servers[]`** (published agent snapshot); **default transport `streamable_http`** (fallback `sse`); `stdio` only when `endpoint` is local subprocess path and env `UCVE_MCP_ALLOW_STDIO=true`
  - `MCPHost`: `connect`, `list_tools`, `call_tool` — returns `MCPToolResult {content, is_error}`; **`call_tool` timeout 3000 ms default** (`ToolTimeoutConfig.timeout_ms`)
  - **`ToolTimeoutFallback`:** on timeout → cancel in-flight call → return structured error to LLM **and** enqueue spoken fallback phrase via TTS (default: "Let me check on that and get back to you" — tenant-overridable in agent JSONB)
  - **`BUILTIN_TOOLS`** (always registered): `end_conversation_summary`, `escalate_to_human` — ported from habiba with **async DB** fix
  - `ToolOrchestrator`: merges builtin + tenant MCP tools; injects `ToolDefinition[]` into LLM request (Phase 05); **serializes tool calls** — one `TOOL_EXECUTING` at a time in v1
  - **Injection point:** after Phase 15 router + persona frame, before LLM `generate` — matches File 6 §1 message order: `[system_instructions] → [persona_frame DATA] → [retrieved_context DATA]` → history → user
  - `ConversationalFillerSynth`: if tool execution > `FillerConfig.trigger_after_ms` (default 400), play language-specific filler via TTS while FSM in `TOOL_EXECUTING`; emit `tool.filler_started` (File 8 §3)
  - Tool results framed as `role=tool` turns — **never** merged into system instructions (poisoning defense, File 6 §5)
  - Phase 12 audit: `tool_call`, `tool_result`, `mcp_connect`, `tool_timeout_fallback`
- **How:** Phase 17 pipeline on LLM `tool_call` event → FSM → `TOOL_EXECUTING` → `MCPHost.call_tool` with **3 s** timeout. **Serial queue:** if LLM requests multiple tools, execute in order; do not fan-out in v1. HTTP/SSE MCP: aiohttp with Phase 09 resolved secrets. stdio MCP: `asyncio.create_subprocess_exec` only when explicitly allowed for dev. On timeout → `ToolTimeoutFallback` TTS + error result to LLM. On `end_conversation_summary`: set disposition stub for Phase 20. On `escalate_to_human`: emit telephony warm-transfer stub `[LATER]` event. Filler cancels on tool completion, timeout, or barge-in (Phase 04).
- **Why this approach:** Enterprises need live DB/API access during calls. Habiba proved two lifecycle tools but locked domain tools out. MCP standardizes extension without per-tenant code forks. **8 s timeout rejected** — dead air on live calls causes hang-ups. **Parallel tools rejected for v1** — determinism and latency predictability outweigh marginal speed gain when tools already exceed File 1 §4 pipeline budget.

## Deliverables

- `core/mcp/__init__.py`
- `core/mcp/host.py` — `MCPHost`, `MCPServerConfig`, `MCPToolResult`, `ToolTimeoutConfig`
- `core/mcp/builtin_tools.py` — `BUILTIN_TOOLS` + async handlers
- `core/mcp/orchestrator.py` — `ToolOrchestrator` (serial execution)
- `core/mcp/filler.py` — `ConversationalFillerSynth`, `FillerConfig`
- `core/mcp/timeout_fallback.py` — `ToolTimeoutFallback`
- `core/mcp/transports/stdio.py` — local-dev only, gated
- `core/mcp/transports/sse.py` — default cloud transport
- `core/mcp/transports/streamable_http.py` — default cloud transport
- `worker-raw/orchestration/tool_handler.py` — pipeline hook
- `tests/fixtures/mcp/` — mock MCP server responses

## 4. Compute & Resource Profile (if applicable)

MCP HTTP connect: ~20–100 ms warm. Tool call latency: tenant-dependent; filler triggers at 400 ms; **hard cap 3 s**. stdio spawn (dev only): ~50–200 ms cold start. Memory: ~10 MB per stdio MCP subprocess — cap concurrent MCP servers per session (default 3).

## 5. Compliance Notes (if applicable)

MCP tool results are untrusted DATA — Phase 10 classification `ArtifactType.provider_payload`. Tool arguments may contain PHI — Phase 07 must not log at INFO+. Tenant MCP endpoints are subprocessors — Phase 10 registry entry per configured server. HIPAA: block MCP servers without BAA when tool may return PHI. Timeout fallback utterance must not echo tool arguments.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **MCP transport default:** **`streamable_http` / `sse` for cloud** — stdio local-dev only with explicit env gate.
2. **Tool call timeout:** **3 s hard cap** per call with spoken fallback utterance for longer operations — not 8 s.
3. **Parallel tool calls:** **serial for v1** — one tool at a time; Phase 03 parallel deferred.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_22_mcp_tooling.py`
- **Asserts:** builtin tools always present; default transport is HTTP/SSE not stdio; MCPHost lists tenant tools; tool result DATA-framed not in system prompt; filler fires after 400 ms mock delay; sync handler uses to_thread; barge-in cancels filler; `end_conversation_summary` sets disposition; **3 s timeout triggers fallback TTS + error result**; **multiple tool_calls execute serially**; audit events emitted.
- **Pass threshold:** 100% unit tests; mock MCP round-trip in pipeline integration stub.
- **Latency target:** builtin tool call < 50 ms p99 (mock DB); filler trigger within ±50 ms of threshold; timeout fires at 3000 ms ±100 ms.
