# Phase 13J progress — platform management security foundation

**Branch:** `wavia-fixv1` (local; not pushed — Hamzi asked not to push until the program is complete)
**Plan:** `Codex Fix/phases/13j-platform-management-security-implementation-plan.md` (`d32c320`)
**Status:** Tasks 1–7 complete; close gate passed locally on 2026-11-12. Stopped before Phase 13K.

## Approval

Hamzi asked to start Phase 13J on 2026-11-12 ("Start Phase 13J"). Nothing is pushed.

## Commits

| Task | Commit | Outcome |
| ---: | :--- | :--- |
| Plan | `d32c320` | Audit of every platform-admin authorization path and a seven-task plan. |
| 1 | `111b153` | `platform_admin: {"*"}` and `resource:*` matching removed; explicit platform matrix; no platform bypass on tenant, member, review or webhook paths; API keys cannot carry a platform role. |
| 2 | `b115593` | Migration 032 (`platform_memberships`, append-only `platform_audit_events`, one-time backfill); repository staff, directory, summary and audit methods. |
| 3 | `a5389eb`, `6999faa` | `require_platform_permission` and `/v1/platform/*`; `/v1/me` reports the durable platform role. Import-order fix. |
| 4 | `ecf0c5c` | Studio platform schemas, `platform` request scope, `requirePlatform` gate, staff server actions, offline fixture platform routes. |
| 5 | `40e4b34` | `(admin)` route group, shared `SidebarShell`, overview, bounded tenant directory, safe tenant summary, staff entry on `/workspaces`. |
| 6 | `f2ccc1d` | `/admin/staff` (grant, change, revoke with reasons) and `/admin/audit`. |
| 7 | close-gate commit | Admin shell QA, visual fixes from capture review, evidence, tracker. |

## Security behaviour change (deliberate)

Before 13J, `users.is_platform_admin = true` let a user act as `platform_admin` in **any** tenant named in `X-Tenant-Id`, with a `*` permission set, no membership, reason, expiry or audit. That is now removed:

- Tenant routes accept only a durable membership; a platform role never satisfies a tenant permission (`tests/auth/test_studio_identity.py::test_legacy_platform_flag_grants_no_tenant_access`, `..._keeps_only_membership_permissions`).
- `enforce_tenant_access`, post-call review decisions and webhook management no longer skip the tenant check for `platform_admin`.
- API keys whose stored role is not a tenant role fail closed (401), and new keys cannot be issued with a platform role.
- Two tests asserted the old wildcard and were inverted in Task 1's RED step: `test_durable_platform_admin_requires_explicit_tenant` (now `test_legacy_platform_flag_grants_no_tenant_access`) and the phase-13 plan test `test_rbac_matrix_enforcement` (now asserts `platform_admin` cannot write agents).

Cross-tenant support access with reason, scope and expiry (support sessions) is Phase 13K; until then staff can read only the safe directory and summary.

## Defects found and fixed

1. **API keys could carry the wildcard role.** `RBACManager.roles()` included `platform_admin`, so key issuance accepted it. Fixed in Task 1.
2. **Concurrent last-admin revocation.** A naive row-by-row check could deadlock or let two administrators revoke each other. Staff mutations now lock the whole active-administrator set in a fixed order first; the disposable-database proof runs the mutual revocation concurrently and keeps exactly one administrator.
3. **Visual review of the captures** found four problems, all fixed: the long role label in the sidebar footer collided with **Sign out** (now the short form "platform admin", matching "tenant admin"); setup-step tokens showed list bullets; on mobile the last-admin hint and the second action button fell into the label column of the staff card.

## Decisions

- **Two roles only** (`platform_admin`, `platform_support`) with four enumerated permissions. Operations health and support sessions arrive in 13K with their own permissions.
- **Platform tables are not granted to `ucve_app`.** Like `external_identities`, they are reached only through `platform_transaction`, which already relies on the platform database role for cross-tenant identity reads. RLS is enabled and forced with no `ucve_app` policy as defence in depth.
- **`users.is_platform_admin` is kept** (no destructive schema change) but is no longer read for authorization. `/v1/me` still returns `is_platform_admin`, now derived from the durable role, so existing clients keep parsing.
- **Audit rows are append-only and keep plain identifiers** (no foreign keys), so they survive later user or tenant changes and never need rewriting.
- **Revocation endpoint is `POST /v1/platform/staff/{id}/revoke`** with a JSON reason, rather than `DELETE` with a body as first sketched in the plan, to avoid request-body semantics on `DELETE`.
- **Customers get a plain not-found for `/admin`**, so the area is not advertised. Staff lacking a capability are redirected to the overview with a denial and no data is loaded.
- **In-memory repository reports agent counts as unknown** (`null`, shown as "Not available") because it does not track agents; it never reports a fake zero. `bootstrap_platform_admin` exists only there; production bootstrap is the migration backfill or an operator SQL procedure.
- **Shared `SidebarShell`.** The collapse, drawer, Escape and focus logic moved out of `WorkspaceNavigation` so the internal area reuses it; the customer shell renders identical markup (all 13H/13I shell QA still passes).

## Not done here (later phases)

- Support sessions (reasoned, scoped, expiring cross-tenant access with banner and audit) and `/admin/operations` — Phase 13K.
- MFA or step-up for platform staff, staff session lifetime and break-glass procedure — need an identity-provider decision (H14/H15).
- Platform audit pagination beyond the latest 50 events and audit export.
- Mapping audit actor and target IDs to emails in the audit table (IDs are shown truncated).

## Next exact action

Report Phase 13J to Hamzi and wait. Phase 13K (operations, support sessions and final QA) starts with its own plan only after he says to continue.
