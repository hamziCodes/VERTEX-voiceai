# AwaazLabs Client Dashboard
# By Mehlab
Voice-AI operations for multi-location clinics: appointments, insurance verification,
conversations, and the Qualicall quality loop.

A **frontend-only** build: no application backend, and every screen reads from
version-controlled fixtures. Built to `qualicall_dashboard_spec.md`.

Authentication is real. Clerk guards every route; the only network calls this app makes are
to Clerk, and `connect-src` in the CSP enforces that.

```bash
npm install
cp .env.example .env.local   # then fill in your Clerk keys
npm run dev                  # http://localhost:3001
```

Without `.env.local` the app will not build. See `.env.example` for what each variable does.

| Script | What it does |
|---|---|
| `npm run dev` | Development server |
| `npm run build` | Production build (runs type-check **and** lint; fails on either) |
| `npm start` | Serve the production build |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` | ESLint |

## Stack

Next.js 15 (App Router) · React 19 · TypeScript strict · Tailwind CSS 3.4 · Radix primitives.
Charts are hand-rolled SVG — no charting library.

## Deploying to Vercel

Zero configuration. Import the repository, or:

```bash
npx vercel
```

Vercel auto-detects Next.js. **Two environment variables are required**
(`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`) plus `NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in`.
For a production Clerk instance also set `NEXT_PUBLIC_CLERK_FRONTEND_API_URL`, or CSP will
block Clerk's scripts.

27 routes. Pages remain statically prerendered; `clerkMiddleware` runs per request at the
edge, and only `/sign-in` is dynamic.

## Security posture

This dashboard renders patient-level data in PHI mode. The frontend reflects that:

- **Authentication** is enforced in `src/middleware.ts`. Every route except `/sign-in`
  redirects an anonymous request to the login page, preserving the deep link. There is no
  `/sign-up` route, and sign-up is disabled in the Clerk dashboard (§16.3: members are added
  by invitation only).
- **Roles come from Clerk** `publicMetadata.role`, validated against the canonical `ROLES`
  union. An unknown or missing role **fails closed to `VIEWER`**. The demo role/mode
  switchers are compiled out of production builds, so nobody can self-promote.
- **Security headers** are set in `next.config.mjs` — CSP, HSTS, `X-Frame-Options: DENY`,
  `Referrer-Policy`, `Permissions-Policy`. `X-Powered-By` is disabled. The CSP allows exactly
  Clerk's hosts — never a bare wildcard — and `frame-ancestors 'none'`, `object-src 'none'`,
  and `form-action 'self'` were not weakened to accommodate it.
- **`robots: noindex, nofollow`** — this must never be indexed.
- **Gating is structural, not cosmetic.** A Viewer does not receive a hidden phone number;
  `src/mock/data-access.ts` returns `phoneE164: null`, so there is nothing on the client to
  reveal. NON-PHI mode returns a discriminated `{ kind: 'aggregate' }` variant, so a page
  cannot render rows without branching. Attempting a gated action throws
  `PermissionDeniedError`.
- **`NoPhi<T>`** in `src/mock/schema.ts` makes it a *compile error* to add a `dob`, `ssn`,
  `diagnosis`, or `clinicalNotes` field to any patient-bearing type (spec §2.5).
- **Every gated action writes an immutable audit event** (spec §2.3, twelve event types).
- `npm audit`: **0 vulnerabilities.**
- No `any`, no `dangerouslySetInnerHTML`, no literal colors anywhere in `src/`. Enforced by
  ESLint and by the checks in `spec_coverage_audit.md`.

## Layout

```
src/
  app/            routes; each page.tsx is a server component delegating to a client child
  components/
    ui/           shared primitives (Button, Table, Drawer, StatCard, MaskedValue, …)
    charts/       12 hand-rolled SVG chart primitives, all gated through ChartFrame
  i18n/           §2.7 locale framework — en + es catalogues, compile-checked for completeness
  lib/            format.ts (timezone-correct rendering), metrics.ts (cross-tab derived numbers)
  mock/           schema.ts (the wire format), data-access.ts (the gating seam), fixtures/
  shared/         status-models.ts (§17 canonical enums), audit.ts, flag-store.ts, nav.ts
```

Two files carry most of the load:

- **`src/shared/status-models.ts`** — spec §17's canonical status models, declared exactly
  once. Every chip, filter, and badge imports from here. A duplicate status string anywhere
  else is a defect.
- **`src/mock/data-access.ts`** — the single seam a real backend replaces. Every screen reads
  through it, and it is where role and mode gating is enforced.

## Where the documentation lives

| File | What it is |
|---|---|
| [`PROGRESS.md`](./PROGRESS.md) | **Start here.** What is done, what is under construction, how to wire a backend |
| [`spec_coverage_audit.md`](./spec_coverage_audit.md) | Every spec bullet, ✅/⚠️/🔜/❌, with evidence |
| [`BUILD_NOTES.md`](./BUILD_NOTES.md) | Every decision and every spec ambiguity, with the reading chosen |
| [`THEME_NOTES.md`](./THEME_NOTES.md) | The frozen design tokens. The only allowed source of color |
| [`discovery_report.md`](./discovery_report.md) | What existed before this build, and what was removed |
| `progress/*_audit.md` | Per-section self-audits |

## Contributing

Read `.claude/skills/awaazlabs-theme/SKILL.md` first. It encodes the token rules, the
primitive inventory, and the composition constraints — including the one that has already
caused a real bug: base UI tokens are HSL *triples* (`hsl(var(--destructive))`) while chart
tokens are complete colors (`var(--chart-1)`). Mixing them yields an invalid SVG `fill`,
which paints the mark black without erroring.
