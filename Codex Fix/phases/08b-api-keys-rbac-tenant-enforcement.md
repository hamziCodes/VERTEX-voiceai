# Phase 08B — API Keys, RBAC, and Tenant Enforcement

**Status:** COMPLETE — COMMITTED AS `bf52744`

## Work

- Store only API-key hashes and non-secret metadata.
- Add key subject, tenant, role, scopes, creation, expiry, revocation, and
  last-used fields plus a durable migration.
- Make verification fail closed for invalid, expired, or revoked keys and
  update last-used metadata without exposing a key hash.
- Require both API-key scope and role permission for management actions.
- Enforce authenticated tenant ownership in agents, knowledge, extraction,
  alerts, usage, audit, and secret rotation.
- Keep the in-memory store explicitly development/test only; production must
  inject a durable store.

## Verification

- Test valid, expired, revoked, wrong-scope, wrong-role, and cross-tenant keys.
- Test two-tenant access attempts across every management route family.
- Confirm response/log/error data never includes raw keys or hashes.
- Run focused auth/security tests, full forced-offline pytest, Ruff, compile,
  plan integrity, diff, secret, and forbidden-scope checks.

## Follow-on status

- Mint binding, JWT issuer/audience/JTI, one-use socket policy, atomic nonce,
  refresh, and token revocation were completed in Phase 08C/08D as `f2f861e`.
- External user provisioning and a specific OIDC vendor: deployment choice;
  no external call is required for 08A/08B.

## Result — 2026-10-22

- Raw API keys are returned once and only their SHA-256 lookup hash is used by
  the store; list responses contain non-secret metadata only.
- Keys now carry subject, tenant, role, scopes, timestamps, expiry, revocation,
  creator, and last-used metadata.
- Role permission and API-key scope are both required for management actions.
- Added migration `016_api_key_auth_context.sql` for durable metadata and
  indexes. The in-memory store is rejected in staging and production; deployment
  must inject its durable adapter after applying the migration.
- Focused auth tests, related security/E2E tests, and the full forced-offline
  suite pass. No live provider, database, IdP, or telephony traffic was used.
