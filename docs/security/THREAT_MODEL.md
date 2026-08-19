# UCVE Threat Model (STRIDE-lite)

Phase 32 security documentation. Assets: PHI, API keys, call audio, tenant configs.

## Trust boundaries

```text
[End-user client] ←→ [Host backend / tenant portal] ←→ [UCVE control-plane]
                                                              ↓
                                                        [worker-raw WS]
                                                              ↓
                                                   [External providers + MCP/RAG]
                                                              ↓
                                                   [Telephony PSTN / SIP trunks]
```

### Boundary 1: Client ↔ Host backend

| STRIDE | Risk | Control |
|---|---|---|
| Spoofing | Fake mint requests | HMAC + publishableKey (Phase 13) |
| Tampering | Token replay | Short TTL, single-use mint |
| Info disclosure | API key in browser | Zero-secret embed (Phase 28) |

### Boundary 2: Host backend ↔ UCVE control-plane

| STRIDE | Risk | Control |
|---|---|---|
| Spoofing | Stolen tenant API key | Vault rotation, RBAC (Phase 09/13) |
| Denial of service | Mint flood | Redis rate limits (Phase 13/14) |
| Elevation | Cross-tenant access | Tenant isolation (Phase 08) |

### Boundary 3: Worker ↔ Providers / MCP / RAG

| STRIDE | Risk | Control |
|---|---|---|
| Tampering | MCP prompt injection | DATA framing (Phase 22/23) |
| Info disclosure | PHI in provider logs | Redaction + tier gates (Phase 10/11) |
| Repudiation | Missing audit trail | Phase 12 access logging |

### Boundary 4: Telephony gateway ↔ PSTN

| STRIDE | Risk | Control |
|---|---|---|
| Spoofing | Unsigned webhooks | HMAC verify (Phase 18, habiba pattern) |
| Info disclosure | Caller metadata leak | Generic errors (Phase 25) |

## PHI flow summary

STT → LLM → optional persist → extraction → webhook. Each hop classified per Phase 10 tier.

## Residual risks

- Script-aware NER redaction: `[FUTURE]`
- S2S provider path: `[LATER]`
- Urdu regex redaction gaps: see [PENTEST_READINESS.md](PENTEST_READINESS.md)
