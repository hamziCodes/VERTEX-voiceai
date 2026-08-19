# UCVE Glossary

| Term | Definition |
|---|---|
| **mint** | Short-lived, HMAC-signed session token issued by control plane via host-backend proxy; replaces long-lived API keys in browser clients (Phase 13/28) |
| **pin** | Immutable published `agent_config_version` bound to active sessions until disconnect (Phase 26) |
| **DATA frame** | WS/content envelope marking untrusted external data (MCP tool output, RAG chunks) isolated from system instructions (Phase 22/23) |
| **caller_id** | E.164 calling party number on inbound PSTN legs; required for telephony normalization (Phase 18) |
| **sovereign plane** | In-process worker-raw pipeline on native WS without LiveKit dependency (Phase 17) |
| **correlation_id** | Opaque request ID for log lookup; safe for integrator support tickets (Phase 07/25) |
| **publishableKey** | Public client identifier paired with server-side mint; zero-secret embed pattern (habiba/Phase 28) |
| **DirectSIP** | Primary SIP trunk transport adapter; default telephony path (Phase 18) |
| **DLQ** | Dead-letter queue for failed post-call jobs; 30-day retention (Phase 25) |
| **Runtime profile** | Named scaling config: `dev`, `standard`, `high_density` (Phase 31) |
