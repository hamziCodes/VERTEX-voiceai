# Project Profile

**Toolkit version in use:** `1.0.0`
**Profile last reviewed:** `2026-11-06` by `Codex, revised direction approved by Hamzi`

## 1. What this project is

| Field | Value |
| :--- | :--- |
| Product name | Wavia Studio |
| One-line purpose | An authenticated SaaS workspace for non-technical operators and developers to build, test, connect and operate Wavia web and telephony voice agents. |
| Primary user | A non-technical business owner or operator configuring and monitoring a voice agent from a desktop or tablet. |
| Secondary user | Tenant administrators, enterprise implementers, SDK developers and read-only workspace viewers. |
| Repository | `D:\PROJECTS\PASSION PROJECTS\VERTEX_voiceai` |

## 2. Surfaces in scope

| Surface | Archetype | Density | Canvas | Notes |
| :--- | :--- | :--- | :--- | :--- |
| Wavia Studio shell and task screens | `dashboard` | `compact` | Wavia Theme B paper field | Persistent collapsible sidebar, contextual top bar and fluid content capped near 1280px. |
| Conversation, audit and monitoring data | `console` inside the dashboard shell | `dense` | Wavia warm paper field | Technical values use Space Mono; tables become cards below 800px. |
| Agent and onboarding editors | `form-flow` inside the dashboard shell | `comfortable` form regions | Wavia warm paper field | Single-column field reading order with sticky save/status controls where useful. |

The Phase 13G pilot covers only `SCR-01` Agent Directory and `SCR-03` Persona Editor. It does not restyle the public Wavia website or roll the design across the other Studio screens.

## 3. Stack

| Field | Value | How it was determined |
| :--- | :--- | :--- |
| Framework and version | Next.js `16.4.3`, App Router; React `19.3.1` | `studio/package.json`, `studio/src/app/` |
| Language | Strict TypeScript | `studio/tsconfig.json` |
| Styling | No styling framework or global stylesheet currently installed | Studio source inspection |
| Token delivery path | Plain CSS custom properties, to be introduced in the pilot | No Tailwind dependency; repository toolkit plain-CSS guidance |
| Motion library | None | `studio/package.json` |
| Icon library | None | `studio/package.json` |
| Font loading | `next/font/google` in the pilot; current Studio has no font loader | Next.js framework confirmed from `studio/package.json`; Hamzi approved free Google Fonts delivery |
| Theme mechanism | None in the current Studio | No theme provider, class strategy, toggle or media-query theme found |
| Target platforms | Desktop web primary; responsive tablet and mobile web required | Phase 13 requirements and pilot brief |
| Browser floor | Current Chromium for automated evidence; Safari and real-device coverage not yet established | `studio/playwright.config.ts` and current test evidence |

### Substitutions

| Toolkit assumes | This project uses | Consequence |
| :--- | :--- | :--- |
| `motion/react` | CSS only | Motion remains reduced and functional; no scroll animation or replaying list entrances. |
| `lucide-react` | No icon dependency | Pilot controls use text and existing semantic HTML unless an icon source is approved later. |
| Inter Tight | Instrument Sans for operational UI; Bricolage Grotesque for wordmark/major titles; Space Mono for technical values; Instrument Serif excluded from controls/data | This is an explicit Wavia brand override. |
| Tailwind | Plain CSS custom properties and component class names | Tokens live in one Studio stylesheet and components consume variables directly. |

## 4. Content and locale

| Field | Value |
| :--- | :--- |
| Primary locale | `en-PK` |
| Additional locales | Agent content may include any supported language; Urdu/RTL behavior remains a product capability but is outside this two-screen visual pilot. |
| Text direction | Studio chrome is `ltr`; agent content may be `ltr` or `rtl`. |
| Currency | n/a for this pilot; Studio does not perform billing or charging. |
| Currency format | n/a |
| Decimal policy | Technical latency and usage values preserve server-provided precision. |
| Date format | Human-readable locale dates in operational UI; exact timestamps in Space Mono where technically necessary. |
| Number format | `en-PK` grouping; IDs and technical values use tabular numerals. |

## 5. Motion and performance budget

| Field | Value |
| :--- | :--- |
| Motion budget | Reduced |
| Reason | Studio is an operational application; transitions must communicate state and never distract or replay on filters/tabs. |
| Lighthouse targets | Performance >=90 mobile / >=95 desktop; Accessibility >=95; SEO is not a meaningful release gate for authenticated Studio routes. |
| Core Web Vitals | LCP <2.5s, CLS <0.1, INP <200ms |
| Bundle ceiling | No new runtime UI or motion dependency in the pilot without explicit justification. |

## 6. Accessibility commitment

| Field | Value |
| :--- | :--- |
| Conformance target | WCAG 2.2 AA |
| Known gaps | Current browser-default Studio has no shared focus system, route loading UI or complete per-container state treatment. These are pilot work, not accepted behavior. |
| Assistive tech tested | Automated Axe coverage exists; manual screen-reader testing has not yet been evidenced. |
| Minimum touch target | 44x44px |

## 7. Deviation register

| # | Deviation | Reason | Scope | Review by |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Wavia Studio uses Wavia Theme B and the named Wavia type system; Brand Kit v1.1, the later steel-blue website theme and the older VERTEX navy/Inter system are superseded for this surface. | Hamzi explicitly selected Theme B (`#FFF6E5`, `#FFFBF2`, `#FBEACD`, `#F6E6C8`, `#1C1408`, `#B45309`) and approved free Google Fonts delivery. | `studio/**` only; compatible dashboard composition, state and accessibility rules still come from the repository design documents. | Pilot review |
| 2 | The two-screen pilot does not add a new theme switcher solely to satisfy the older toolkit's two-theme rule. | The current Studio has no theme mechanism and the brief requests both-theme QA only if Studio already supports both. Adding a preference and persistence behavior would exceed a visual-only pilot. | Phase 13G pilot only | Pilot review |
| 3 | Toolkit shadow and navy component prescriptions are not adopted. | The pilot forbids generic template output and uses Wavia's solid paper surfaces, ink borders and marigold accent. | `SCR-01`, `SCR-03` and shared shell/primitives used by them | Pilot review |

### Optional product signal

| Field | Value |
| :--- | :--- |
| `--product-signal` in use | No separate signal; marigold is the single brand accent. |
| Value if yes | n/a |
| Contrast measured | Pending implemented-token verification. |
| Approved by | Pending pilot approval. |

## 8. Adoption status

| Surface | Tokens installed | Converted | Both themes verified | Gate passed | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Shared Studio shell | No | No | n/a, current Studio has no theme mechanism | No | Revised reference direction approved; ready for pilot implementation. |
| `SCR-01` Agent Directory | No | No | n/a | No | Pilot target. |
| `SCR-03` Persona Editor | No | No | n/a | No | Pilot target; current route is `/agents/[agentId]/build`. |
| Remaining Studio screens | No | No | n/a | No | Explicitly outside the pilot until Hamzi approves it. |

## 9. Project-specific decisions

- Instrument Sans is the operational UI face. Space Mono is restricted to code, IDs, logs, latency and technical values. Bricolage Grotesque is restricted to the wordmark and major screen titles. Instrument Serif never appears in controls or data.
- Marigold is the only brand accent. Green, amber, red and blue are functional status colors and always include text or an icon signal.
- Application radii never exceed 24px. No gradients, glass cards, decorative blobs, marketing heroes, giant display sections or scroll animation.
- Lists do not replay entrance animation when a filter or tab changes.
- All list, table and panel components must define ready, empty, loading and error states.
- Studio behavior, routes, API contracts, roles and test selectors are preserved by the visual pilot.
- Temporary Playwright captures belong under a gitignored QA directory and are never committed unless Hamzi asks.
