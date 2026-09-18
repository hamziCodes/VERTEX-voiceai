# Project Profile

> **Template.** Fill this in once, the first time anyone touches UI in this repository, then commit it. Every later session — human or agent — reads this instead of re-deriving the answers. That is what stops two reasonable people from making two different reasonable choices six months apart.
>
> Replace every `[ ]` with a real value. If a field does not apply, write `n/a` and why. Never leave a blank.

**Toolkit version in use:** `[ ]` (see `CHANGELOG.md`)
**Profile last reviewed:** `[ YYYY-MM-DD ]` by `[ name ]`

---

## 1. What this project is

| Field | Value |
| :--- | :--- |
| Product name | `[ e.g. VERTEX/care ]` |
| One-line purpose | `[ what it does, for whom ]` |
| Primary user | `[ e.g. non-technical clinic receptionist on a mid-range Android phone ]` |
| Secondary user | `[ or n/a ]` |
| Repository | `[ path or URL ]` |

**Why the primary user matters:** it settles arguments that the spec cannot. A receptionist on a 5-year-old Android needs bigger targets and a cheaper motion budget than a desk-bound analyst, and both are compliant with this toolkit.

---

## 2. Surfaces in scope

List every distinct surface and its archetype from [`spec/SURFACES.md`](./spec/SURFACES.md). One project commonly has several.

| Surface | Archetype | Density | Canvas | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `[ e.g. Public site ]` | `marketing` | `comfortable` | `--background` | |
| `[ e.g. Clinic dashboard ]` | `dashboard` | `compact` | `--app-canvas` | |
| `[ e.g. Staff phone app ]` | `mobile-app` | `comfortable` | `--app-canvas` | |
| `[ e.g. Booking wizard ]` | `form-flow` | `comfortable` | `--app-canvas` | |
| `[ e.g. Admin log viewer ]` | `console` | `dense` | `--app-canvas` | |

---

## 3. Stack

Fill from the repository, not from memory.

| Field | Value | How it was determined |
| :--- | :--- | :--- |
| Framework and version | `[ e.g. Next.js 15, App Router ]` | `[ package.json ]` |
| Language | `[ TypeScript strict / JavaScript ]` | `[ tsconfig.json ]` |
| Styling | `[ Tailwind v4 / Tailwind v3 / CSS Modules / styled-components / vanilla ]` | `[ ]` |
| Token delivery path | `[ tailwind-v4 / tailwind-v3 / plain-css / json ]` | `[ ]` |
| Motion library | `[ motion (motion/react) / framer-motion / CSS only / none ]` | `[ ]` |
| Icon library | `[ lucide-react / other / none ]` | `[ ]` |
| Font loading | `[ next/font Inter Tight / @import / self-hosted / system fallback ]` | `[ ]` |
| Theme mechanism | `[ html.dark class + pre-paint script / next-themes / prefers-color-scheme only ]` | `[ ]` |
| Target platforms | `[ e.g. mobile web first, desktop web, PWA ]` | `[ ]` |
| Browser floor | `[ e.g. last 2 versions, iOS Safari 16+ ]` | `[ ]` |

### Substitutions

If the stack lacks something the toolkit assumes, record the substitute here. This is normal and not a deviation.

| Toolkit assumes | This project uses | Consequence |
| :--- | :--- | :--- |
| `motion/react` | `[ ]` | `[ e.g. sticky stacks use CSS scroll-timeline; reveals use IntersectionObserver ]` |
| `lucide-react` | `[ ]` | `[ e.g. icons ported at 1.75 stroke equivalent ]` |
| Inter Tight | `[ ]` | `[ e.g. system stack; weight roles map to 800/700/500/300 ]` |
| Tailwind | `[ ]` | `[ e.g. CSS Modules consuming var(--token) directly ]` |

---

## 4. Content and locale

| Field | Value |
| :--- | :--- |
| Primary locale | `[ e.g. en-PK ]` |
| Additional locales | `[ e.g. ur-PK, or none ]` |
| Text direction | `[ ltr / rtl / both ]` |
| Currency | `[ e.g. PKR ]` |
| Currency format | `[ e.g. PKR 184,250 — see DESIGN.md money rules ]` |
| Decimal policy | `[ whole units in lists and metrics; 2dp in reconciliation only ]` |
| Date format | `[ e.g. Monday, 24 August ]` |
| Number format | `[ e.g. en-PK grouping ]` |

**If direction includes `rtl`:** all directional spacing uses logical properties (`ps-`/`pe-`, `ms-`/`me-`, `start`/`end`), the offset shadow mirrors to `-3px 4px 0`, and chevrons flip. Record it here so nobody has to rediscover it.

---

## 5. Motion and performance budget

| Field | Value |
| :--- | :--- |
| Motion budget | `[ full / reduced / minimal ]` |
| Reason | `[ e.g. reduced — primary users on low-end Android ]` |
| Lighthouse targets | `[ default: Perf >=90 mobile / >=95 desktop, SEO >=95, A11y >=95 ]` |
| Core Web Vitals | `[ default: LCP <2.5s, CLS <0.1, INP <200ms ]` |
| Bundle ceiling | `[ or n/a ]` |

Budget definitions live in `spec/SURFACES.md`. `minimal` means opacity-only transitions and no scroll-linked transforms; it is a legitimate choice, not a failure.

---

## 6. Accessibility commitment

| Field | Value |
| :--- | :--- |
| Conformance target | `[ default: WCAG 2.1 AA ]` |
| Known gaps | `[ list, or none ]` |
| Assistive tech tested | `[ e.g. VoiceOver iOS, NVDA, or not yet ]` |
| Minimum touch target | `[ default: 44x44px ]` |

---

## 7. Deviation register

**The most important section in this file.** Any departure from the toolkit goes here. An undocumented deviation is drift; a documented one is a decision the next session can trust or revisit.

A deviation needs all five columns. If you cannot write the reason, you do not have a deviation — you have a mistake to fix.

| # | Deviation | Reason | Scope | Review by |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `[ e.g. Legacy tables keep 4px radii ]` | `[ e.g. shared with an unconverted reporting module ]` | `[ e.g. src/legacy/reports/** only ]` | `[ YYYY-MM-DD ]` |

### Not deviations

These are always violations, never negotiable, and must not be entered above:

- A second accent colour
- A single-theme surface
- `--brand-primary` used as text on a dark canvas
- A removed focus indicator
- A missing empty, loading or error state
- Invented reviews, logos, metrics, SLAs or addresses
- Any word from the banned list

### Optional product signal — the one scoped escape hatch

A product line may carry a single identity tint, `--product-signal`, which defaults to `var(--brand-primary)`. It is permitted **only** on the product identity chip and the nav mark, and only on areas under roughly 40×40px. It is banned on CTAs, links, focus rings, large fills, charts and text. Using it requires an entry here.

| Field | Value |
| :--- | :--- |
| `--product-signal` in use | `[ no / yes ]` |
| Value if yes | `[ hex, light and dark ]` |
| Contrast measured | `[ ratio against its own background ]` |
| Approved by | `[ name and date ]` |

---

## 8. Adoption status

Retrofits convert one surface at a time. Track it, so nobody has to guess how far along the project is.

| Surface | Tokens installed | Converted | Both themes verified | Gate passed | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` |

---

## 9. Project-specific decisions

Anything a future session would otherwise have to reverse-engineer. Keep it short and factual.

- `[ e.g. Money always renders through formatMoney(); no inline toLocaleString anywhere ]`
- `[ e.g. Bottom nav has exactly 4 tabs; a 5th requires an IA change, not an overflow menu ]`
- `[ e.g. Charts use the navy ramp 300/500/700 in that order for series 1-3 ]`
