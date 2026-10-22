# Phase 08C — Session Mint and Token Lifecycle

**Status:** COMPLETE — COMMITTED AS `f2f861e`

## Contract

- API-key minting may mint only for the authenticated key tenant.
- Signed HMAC mint binds tenant, agent, timestamp, and nonce; tenant ownership
  and a published agent configuration remain mandatory outside unsafe local
  development.
- Nonces are consumed atomically with Redis `SET NX EX`; test/development uses
  a locked in-memory implementation. Protected environments fail closed when
  Redis is absent or unavailable.
- Session JWTs require issuer, audience, JTI, subject/session, tenant, agent,
  action, issued-at, expiry, and token type.
- A room token admits one WebSocket connection. Refresh is allowed once per JTI,
  revokes the old token for future admission, and issues a new one-use token.
  An already authenticated socket may finish until its token expiry.

## Verification

- Concurrent nonce consumers produce exactly one winner.
- Wrong issuer/audience/action and missing required claims fail closed.
- Reused WebSocket and refresh JTIs are rejected.
- API keys cannot mint for another tenant.
- Refresh verifies the persisted session tenant/agent before rotation.
