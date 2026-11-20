# MCP and RAG Setup

Tenant-scoped tooling (Phases 22–23).

## MCP servers (Phase 22)

Register HTTP or SSE MCP endpoints per agent:

| Transport | Config | Notes |
|---|---|---|
| HTTP | `mcp_url`, `auth_header_ref` | Standard request/response tools |
| SSE | `mcp_sse_url` | Streaming tool events |

- Tool results are **DATA-framed** — never merged into system prompt raw (Phase 22).
- Serial tool execution with 3 s timeout per call.
- Secrets via Phase 09 vault refs, not inline in agent config.

## Knowledge bases (Phase 23)

1. Upload documents via `POST /v1/knowledge-bases/{id}/sources` (file upload or URL; FAQs via `/faqs`).
2. Tier selects embedder:
   - **Standard:** hosted embedder route
   - **HIPAA:** tenant-approved embedder only after BAA gate
3. Retrieval runs speculative prefetch on turn start; results DATA-framed into LLM context.

## Studio setup

Agent Studio (Phase 27) exposes MCP + KB pickers on agent edit screen. Sandbox call validates tool wiring before publish.

## Security

- Validate MCP server TLS and allowlist domains per tenant.
- RAG poisoning defenses: chunk hash verification, tenant isolation (Phase 23).

## Related

- [COMPLIANCE_INTEGRATOR_GUIDE.md](COMPLIANCE_INTEGRATOR_GUIDE.md)
- [GLOSSARY.md](GLOSSARY.md) — DATA frame definition
