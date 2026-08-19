# Integration Patterns

## 1. Zero-secret embed (habiba pattern)

Browser holds only a **publishableKey**. All secrets stay on the host backend.

```
Browser  →  HostBackend /mint  →  ControlPlane  →  short-lived token  →  WSS
```

- Never embed `sk-*` provider keys or tenant API keys in front-end bundles.
- Mint tokens are single-use, short TTL (Phase 13).
- Reference: habiba `publishableKey` + server signing (`legacy_codebases/habiba-sdk-agent/client-submission_v2/docs/INTEGRATION_GUIDE.md` — citation only).

## 2. Iframe SDK widget

Embed Agent Studio test widget or `@ucve/voice` demo in tenant portal:

- Parent page loads SDK with `publishableKey`.
- Iframe origin must match allowed origins list (Phase 13).
- PostMessage bridge for call state only — no audio PHI in messages.

## 3. Server-side CRM webhook (Phase 21)

Post-call structured extraction dispatches to tenant webhook:

- HMAC-signed payloads (`X-UCVE-Signature`).
- Fail-closed secret validation — missing secret rejects dispatch (Phase 21).
- Retry via DLQ on failure (Phase 25); integrator must return 2xx within 10 s.

## 4. Self-hosted sovereign path

Default integration uses native WebSocket + Direct SIP telephony. LiveKit is optional (`@ucve/voice-livekit`), not required (Phase 18/28).

## Anti-patterns

| Do not | Do instead |
|---|---|
| Ship API keys to browser | Host-backend mint proxy |
| Log mint tokens | correlation_id only in logs |
| Pass PHI in webhook query strings | POST body + HMAC header |
