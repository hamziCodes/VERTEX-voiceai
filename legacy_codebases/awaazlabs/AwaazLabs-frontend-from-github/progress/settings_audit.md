# Settings sub-tabs audit — §16.3–§16.6

Six sub-tabs built inside `src/app/(dashboard)/settings/`. Each `page.tsx` is a server
component delegating to a `'use client'` child; `members` and `billing` keep their
`<RouteGuard>`. Verification: `npx tsc --noEmit` clean, `npx eslint "src/app/(dashboard)/settings"`
clean, no literal colors, no `any`, suppression phones masked, no literal `90` in billing.

## §16.3 Members (Owner only)
- ✅ User list with role, last active, MFA status — from `fixture.members`.
- ✅ Invite by email with role assignment (Owner only) — form + optimistic pending-invite row.
- ✅ "No email service" stated plainly; no fake sent email.
- ✅ Role changes audited via `recordPermissionChange(session, memberId, from, to)`, wrapped in try/catch for `PermissionDeniedError`.
- ✅ "MFA required for Owner and Manager in PHI mode" rendered as a standing compliance statement; Owner/Manager rows with `mfaEnabled: false` flagged non-compliant with icon (`ShieldAlert`) + text, never color alone.
- ✅ `<RouteGuard capability="members" surface="Members">` preserved.

## §16.4 Usage and Billing (Owner only)
- ✅ Minutes consumed vs plan (`fixture.minutesConsumed` / `org.planMinutes`), current cycle, with projection to cycle end. Projection method stated in a tooltip and labeled an estimate.
- ✅ Consumption breakdown by agent and by location (two single-hue bar charts + tables). Footnoted as derived from recorded call activity.
- ✅ Chat sessions metered separately (`fixture.chatSessionsConsumed` / `org.planChatSessions`) — TWO distinct meters, never merged.
- ✅ Overage indicator; `USAGE_BANNER_THRESHOLD` imported, never hardcoded 90.
- ✅ History of past cycles — invoice table doubles as billing-cycle history.
- ✅ Invoice list with download — client-side CSV blob (honest mock), no 404 link.
- ✅ No plan/price editor built; explicit banner that plan changes are an account-manager workflow.
- ✅ `<RouteGuard capability="billing" surface="Usage and Billing">` preserved.

## §16.5 Organization and Locations
- ✅ Org profile (name, location count).
- ✅ Average appointment value config; current value shown; UI states explicitly it drives the Overview §4.3 revenue estimate; Cedar (`null`) shows the revenue card is hidden until set. Editing is optimistic local state only — stated plainly.
- ✅ Location list with timezone, business hours (minutes-from-midnight rendered as readable clock times), holiday calendar per location.

## §16.5 Lines and Numbers
- ✅ Connected phone numbers and WhatsApp senders per location (`fixture.lines`).
- ✅ Per-line health indicator with last-checked timestamp. Health is icon + text label, never color alone; failing uses reserved `destructive`, healthy is neutral chip + check icon (theme has no green/success token). Northside `ln_ns_004` unhealthy.
- ✅ Escalation forwarding target (`MockLocation.escalationForwardingNumber`).
- ✅ Recording-consent mode per location (one-party / two-party). `loc_north` = two_party.

## §16.5 Consent and Do-Not-Call
- ✅ Suppression list: masked phone (`maskPhone(entry.phoneE164)`), source (`SUPPRESSION_SOURCE_LABELS`).
- ✅ Manual add and remove — audited via `recordConsentListChange(session, phoneMasked, 'add'|'remove')`, gated on `canEditConsentList(session)`, try/catch on `PermissionDeniedError`.
- ✅ Consent basis field per entry where captured.
- ✅ Quiet-hours configuration for outbound calling windows (local demo state, stated).

## §16.6 Notifications
- ✅ Full matrix: 8 event types × 3 channels × 3 roles = 72 cells.
- ✅ Event types (exact 8): escalation unacknowledged · VOB needs-attention aging · line health failure · usage threshold · weekly report · monthly report · knowledge request status change · flag resolution.
- ✅ Channels: email · SMS · in-app. Roles: the three from `ROLES`.
- ✅ Owner × escalation-unacknowledged locked on structurally: checkbox `disabled` + always `checked`, handler refuses to mutate locked cells, lock icon + explanatory note.

## Degraded / empty states
- ✅ Viewer: cannot reach Members/Billing (RouteGuard). Organization/Lines/Consent/Notifications read-only — no suppression add/remove, no avg-value edit, no quiet-hours edit.
- ✅ Manager: no Members/Billing; can edit consent list.
- ✅ NON-PHI: all six surfaces render (no patient-level rows); suppression list holds masked phones only.
- ✅ Cedar: 1 location, 2 members, 2 lines, 2 suppression entries, `avgAppointmentValueUsd: null` — renders without crashing; revenue-card-hidden note shown.

No UI element exists in this scope that cannot be traced to a §16.3–§16.6 bullet.
