# Phase 08D — Auth Endpoint Hardening

**Status:** COMPLETE — COMMITTED AS `f2f861e`

## Contract

- Demo mint is available only in explicit local development/test modes and can
  never be enabled in staging or production.
- Staging and production reject missing or shipped/default JWT, mint-HMAC, and
  metrics secrets.
- Mint and refresh requests have bounded headers/body fields, an 8 KiB request
  limit, and a direct-peer rate limit. Forwarded identity headers do not select
  the limiter key.
- Authentication errors returned to HTTP/WebSocket clients are stable and do
  not expose token parser, database, provider, or internal exception details.
- Redis-backed replay/rate controls fail closed in protected environments.

## Verification

- Protected-environment demo/default-secret attempts fail.
- Oversized auth requests return 413.
- Direct-peer rate limiting cannot be bypassed with `X-Forwarded-For`.
- Invalid refresh and WebSocket tokens return sanitized failures.
