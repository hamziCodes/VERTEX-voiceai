# Wavia Host Backend Mint Guide

This is the zero-secret client architecture: secrets remain in the host backend.

Browser and mobile clients receive only a short-lived session token. HMAC mint
secrets, platform API keys, and provider credentials stay in the authenticated
host backend.

## Production contract

The host backend sends `POST /v1/session` to the control plane with:

| Header | Value |
|---|---|
| `X-Tenant-Id` | Tenant identifier |
| `X-Timestamp` | Current Unix timestamp in seconds |
| `X-Nonce` | New random nonce for replay protection |
| `X-Agent-Id` | Published agent identifier |
| `X-Signature` | HMAC produced by `expected_signature` |
| `Origin` | Host origin when the tenant allowlist requires it |

The successful response contains `session_id`, `token`, `ttl_sec`, and
`ws_url`. The current TTL is reported by the response; clients must not hardcode
it. The browser connects to `ws_url` with the token and performs the v1
`protocol.hello` handshake.

[`examples/host-backend/app.py`](../../examples/host-backend/app.py) implements
this contract without embedding a secret. The host must provide
`UCVE_MINT_HMAC_SECRET` through its secret manager or local environment.

## Local demo contract

`POST /mint` and `POST /v1/session/mint` are convenience routes. They work
without caller authentication only when the control plane is explicitly in
development/test demo mode. `examples/host-backend/main.py` is labelled and
implemented as a local demo HMAC proxy. Neither route is the production browser
integration.

## Refresh

The host may call `POST /v1/session/refresh` with the current ephemeral token.
The realtime worker emits `session.token_expiring` before expiry and closes with
a retryable `session.close` at expiry. Public clients surface the signal to the
host application; they never receive the HMAC secret.
