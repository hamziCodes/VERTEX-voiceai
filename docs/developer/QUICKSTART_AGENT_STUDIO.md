# Quickstart: Agent Studio (Tenant Admin)

Build and publish agents without writing backend code (Phase 27).

## Prerequisites

- Control plane + Agent Studio UI deployed
- Tenant admin role (Phase 13 RBAC)

## Steps

1. **Sign in** to Agent Studio at `/studio` with tenant admin credentials.

2. **Create agent** — name, default language (Phase 15 registry), voice profile, system prompt. Compliance tier selector shown (Phase 10).

3. **Configure tools** — optional MCP servers (Phase 22) and knowledge bases (Phase 23) from tenant-scoped pickers.

4. **Sandbox test call** — Studio launches in-browser WS session against draft config. No publish required.

5. **Legal review checkbox** — HIPAA tier requires BAA acknowledgment stub before publish (cross-link [COMPLIANCE_INTEGRATOR_GUIDE.md](COMPLIANCE_INTEGRATOR_GUIDE.md)).

6. **Publish** — creates pinned `agent_config_version` (Phase 26). Active sessions keep pinned config until disconnect.

## Verify

- Sandbox call completes STT → LLM → TTS on sovereign WS.
- Published agent appears in control-plane `GET /v1/agents/{id}`.

## Next

- [MCP_AND_RAG_SETUP.md](MCP_AND_RAG_SETUP.md)
- [COMPLIANCE_INTEGRATOR_GUIDE.md](COMPLIANCE_INTEGRATOR_GUIDE.md)
