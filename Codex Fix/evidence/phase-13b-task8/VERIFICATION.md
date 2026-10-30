# Phase 13B Task 8 Verification

Date: 2026-10-30

Branch: `wavia-fixv1-phase13b`

Base: `72974c7273f4dfc40254ae8a9289942071b724c5`

## Scope

- Added the standalone Next.js 16 Studio scaffold.
- Added a server-only FastAPI control-plane client with a strict outbound-header allowlist.
- Added safe Zod DTO parsing and sanitized, typed upstream error mapping.
- Added request timeout, request-ID propagation, selected-workspace enforcement, and same-origin path enforcement.
- Did not add OIDC integration, live providers, carrier traffic, calls, deployment, or paid activity.

## Test-first evidence

The initial DAL run failed because `@/data/control-plane` did not exist. After the minimal implementation, 12 boundary tests passed. A security mutation check then added absolute/protocol-relative/relative-path credential-exfiltration cases; all three failed before same-origin path enforcement and passed afterward.

Final focused result:

```text
Test Files  1 passed (1)
Tests       15 passed (15)
```

Covered behavior:

- missing server session and missing selected workspace fail before network access;
- stalled upstream requests time out;
- invalid success payloads fail safe at the Zod boundary;
- upstream 401, 403, 409, 422, 429, and 503 responses map to sanitized errors;
- request IDs are preserved;
- caller headers cannot override authorization, tenant, or request-ID headers;
- tokens and raw upstream bodies do not appear in errors;
- non-local paths cannot receive server credentials.

## Dependency and build evidence

Exact versions are locked in `studio/package-lock.json`. Next.js is `16.4.3` and React is `19.3.1`. TypeScript `6.0.3` and ESLint `9.39.5` are the newest installed major lines compatible with the current Next.js 16 lint stack; ESLint 10 and TypeScript 7 were rejected after peer/runtime validation.

```text
npm audit --omit=dev --audit-level=high
found 0 vulnerabilities

npm run typecheck
exit 0

npm run lint
exit 0, 0 warnings

npm run test
15 passed

npm run build
compiled successfully; / and /_not-found statically generated
```

## Browser evidence

Playwright loaded `http://127.0.0.1:3100` at 1440×900:

```json
{"status":200,"errors":[],"metrics":{"title":"Wavia Studio","scrollWidth":1440,"clientWidth":1440,"scrollHeight":900,"clientHeight":900,"h1":"Your voice-agent workspace"}}
```

The shell is intentionally minimal and unstyled in Task 8. It renders truthful setup-state copy and no overflow; final visual design remains in the later Phase 13 Studio design task after Hamzi supplies/approves visual direction.

## Repository baseline

Forced-offline baseline before Studio implementation:

```text
965 passed, 14 skipped, 2 known short-HMAC fixture warnings
```

The first baseline attempt had 26 setup errors because the ignored `hamza_local` parent did not exist in the new worktree. Creating that disposable parent and rerunning the identical command produced the clean result above; no product test failed in the first attempt.

## Remaining gate

Task 9 has not started. Hamzi must choose/provision the external OIDC provider and confirm only that its required environment variable names are locally configured. Secret values must never be pasted, printed, logged, or committed.
