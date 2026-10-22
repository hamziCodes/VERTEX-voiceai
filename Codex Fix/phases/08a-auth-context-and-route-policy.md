# Phase 08A — Auth Context and Route Policy

**Status:** VERIFIED — AWAITING COMMIT

## Decision

- Dashboard identity terminates at an injected, provider-neutral OIDC adapter.
- SDK and enterprise server operations use hashed, scoped tenant API keys.
- Every trusted identity becomes one immutable `AuthContext` containing subject,
  tenant, roles, scopes, key ID, and authentication method.
- Caller headers may assert context only for compatibility; they never create
  identity and a mismatch is rejected.

## Route classes

- Public: health, root redirect, favicon, version, local static demo, OpenAPI
  documents.
- Dedicated authentication: signed/API-key session mint and refresh (08C).
- Dedicated carrier authentication: Telnyx webhooks.
- Dedicated operations bearer: metrics.
- Tenant management: agents, knowledge status, extraction schemas, alerts,
  usage, audit, and secret rotation. These require `AuthContext`, tenant match,
  role permission, and API-key scope when the caller uses an API key.

## Work

- Create `AuthContext` and one FastAPI bearer dependency.
- Normalize API-key and injected OIDC claims into the same context.
- Replace default/caller-controlled tenant and actor headers on management
  routes.
- Publish a source-controlled route policy inventory and test every registered
  management route as authenticated or explicitly exceptional.

## Verification

- Unauthenticated management requests return 401.
- Wrong tenant/role assertion headers return 403.
- Tenant identity always comes from verified credentials.
- Public, carrier-authenticated, mint, and metrics routes remain explicitly
  classified.

## Result — 2026-10-22

- Added one immutable auth context and one shared dependency for API-key and
  injected OIDC identities.
- Removed management trust in tenant and actor headers; mismatched compatibility
  headers now fail with 403.
- Added a source-controlled route policy covering public, session, carrier,
  operations, and tenant-management surfaces.
- Protected agents, knowledge, extraction, alerts, usage, audit, and secret
  rotation. Telnyx webhooks keep their carrier-signature boundary.
- Phase 08C session mint/JWT work was not started.
