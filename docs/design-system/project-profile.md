# Project Profile

**Toolkit version in use:** `1.0.0`
**Profile last reviewed:** `2026-11-12` by `Claude, Phase 13H customer foundation close gate`

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

The Phase 13G pilot covered `SCR-01` Agent Directory and `SCR-03` Persona Editor. Phase 13H extended Theme B to the customer foundation routes: sign-in, workspace selection, dashboard, onboarding, agent creation, `/test`, `/settings` and `/settings/members`. Operational routes (knowledge, channels, API keys, providers, conversations, usage, audit) are still pre-pilot and convert in Phase 13I. The public Wavia website is out of scope.

`docs/DESIGN.md` and `docs/design/design-tokens.json` (Wavia Ripple, supplied by Hamzi on 2026-11-10) govern future dashboard frontend work. Their §9 keeps this Theme B Studio untouched until a deliberately approved migration, and the suggested Theme B → Ripple mapping there is not yet approved. Phase 13H therefore stayed on Theme B.

## 3. Stack

| Field | Value | How it was determined |
| :--- | :--- | :--- |
| Framework and version | Next.js `16.4.3`, App Router; React `19.3.1` | `studio/package.json`, `studio/src/app/` |
| Language | Strict TypeScript | `studio/tsconfig.json` |
| Styling | Plain CSS in `studio/src/app/globals.css`; no styling framework | Phase 13G implementation and `studio/package.json` |
| Token delivery path | Plain CSS custom properties installed in the pilot | No Tailwind dependency; repository toolkit plain-CSS guidance |
| Motion library | None | `studio/package.json` |
| Icon library | None | `studio/package.json` |
| Font loading | `next/font/google` with Bricolage Grotesque, Instrument Sans, Space Mono and Instrument Serif | `studio/src/app/layout.tsx`; Hamzi approved free Google Fonts delivery |
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
| Known gaps | The shared focus system and loading/error/empty treatment now cover the Phase 13G pilot screens and the Phase 13H foundation routes. The Phase 13I operational routes still use inline browser-default styling and hardcoded colours. |
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
| Contrast measured | Automated Axe reported no serious or critical findings on both pilot screens after the active-navigation contrast fix. |
| Approved by | Pending Hamzi pilot review. |

## 8. Adoption status

| Surface | Tokens installed | Converted | Both themes verified | Gate passed | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Shared Studio shell | Yes | Yes | n/a, current Studio has no theme mechanism | Yes | Responsive collapse, active routes, role filtering and focus order verified in unit and Chromium tests. |
| `SCR-01` Agent Directory | Yes | Yes | n/a | Yes | Ready, empty-by-data, empty-by-filter, loading and error treatments implemented; desktop/390px/320px checked. |
| `SCR-03` Persona Editor | Yes | Yes | n/a | Yes | Route `/agents/[agentId]/build`; validation, autosave, readiness, view-only, loading and error treatments verified. |
| Entry and workspace selection (`/`, `/sign-in`, `/workspaces`) | Yes | Yes | n/a | Yes | Phase 13H Task 4; invitation, empty and error states, including the expired, used and wrong-email invitation messages added in Task 7. |
| Dashboard, onboarding, agent creation | Yes | Yes | n/a | Yes | Phase 13H Task 5; desktop and 390px checked in the Task 8 shell QA journey. |
| `/test` selector | Yes | Yes | n/a | Yes | Phase 13H Task 6. |
| `/settings`, `/settings/members` | Yes | Yes | n/a | Yes | Phase 13H Task 7; only existing `--studio-*` tokens. Members are shown by account ID because the control-plane list exposes no name or email. |
| Operational routes (knowledge, channels, API keys, providers, conversations, usage, audit) | No | No | n/a | No | Phase 13I scope. Inline styles and hardcoded hex values remain in `channels/*`, `api-key-manager.tsx`, `provider-credential-manager.tsx` and the channel views. |

## 9. Project-specific decisions

- Instrument Sans is the operational UI face. Space Mono is restricted to code, IDs, logs, latency and technical values. Bricolage Grotesque is restricted to the wordmark and major screen titles. Instrument Serif never appears in controls or data.
- Marigold is the only brand accent. Green, amber, red and blue are functional status colors and always include text or an icon signal.
- Application radii never exceed 24px. No gradients, glass cards, decorative blobs, marketing heroes, giant display sections or scroll animation.
- Lists do not replay entrance animation when a filter or tab changes.
- All list, table and panel components must define ready, empty, loading and error states.
- Studio behavior, routes, API contracts, roles and test selectors are preserved by the visual pilot.
- Temporary Playwright captures belong under a gitignored QA directory and are never committed unless Hamzi asks.
