# UCVE Developer Documentation

External integrator docs for the Unified Core Voice Engine. For OpenAPI field detail, use the self-hosted control-plane `/docs` (Phase 28).

## Audience paths

| Role | Start here |
|---|---|
| Host-backend integrator | [QUICKSTART_HOST_BACKEND.md](QUICKSTART_HOST_BACKEND.md) |
| Tenant admin (Agent Studio) | [QUICKSTART_AGENT_STUDIO.md](QUICKSTART_AGENT_STUDIO.md) |
| Platform ops / on-call | [../runbooks/README.md](../runbooks/README.md) |

## Guides

- [QUICKSTART_HOST_BACKEND.md](QUICKSTART_HOST_BACKEND.md) — mint proxy, WS test call, TTS playback
- [QUICKSTART_AGENT_STUDIO.md](QUICKSTART_AGENT_STUDIO.md) — create agent, sandbox call, publish
- [INTEGRATION_PATTERNS.md](INTEGRATION_PATTERNS.md) — zero-secret embed, iframe widget, CRM webhooks
- [COMPLIANCE_INTEGRATOR_GUIDE.md](COMPLIANCE_INTEGRATOR_GUIDE.md) — tiers, BAA gate, retention
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — `UCVEErrorCode` → integrator actions
- [TELEPHONY_INTEGRATOR.md](TELEPHONY_INTEGRATOR.md) — inbound DID, webhooks, caller ID
- [MCP_AND_RAG_SETUP.md](MCP_AND_RAG_SETUP.md) — MCP HTTP/SSE, knowledge base upload
- [GLOSSARY.md](GLOSSARY.md) — UCVE terminology

## Environment template

- [env/.env.example](env/.env.example) — local dev vars (no secrets). Production secrets via Phase 09 vault.

## Related phase deliverables

- Phase 28: [../sdk/HOST_BACKEND_MINT_GUIDE.md](../sdk/HOST_BACKEND_MINT_GUIDE.md), `examples/host-backend/`
- Phase 27: Agent Studio UX flows in `agent-studio/`
- Phase 30: [../deploy/COMPOSE_QUICKSTART.md](../deploy/COMPOSE_QUICKSTART.md)
