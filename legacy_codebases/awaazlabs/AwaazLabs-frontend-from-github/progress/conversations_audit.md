# §10 Conversations — self-audit

Bullet-by-bullet against spec §10.1–§10.4 (plus §12.3 inline and §2.8 consent). ✅ done · ⚠ done with a noted interpretation · ❌ not done.

## §10.1 Calls sub-view

### Table columns (exactly ten, in order)
✅ timestamp · ✅ direction (inbound/outbound) · ✅ agent (Receptionist, VOB, Verifier, Review Taker, Reengagement) · ✅ patient name where matched · ✅ phone (masked, via `MaskedValue`) · ✅ duration · ✅ disposition (all 10 from `CALL_DISPOSITIONS`) · ✅ triage flag · ✅ QA grade (numeric badge) · ✅ location.
- Agent labels from `AGENT_LABELS`; disposition/triage via `CallDispositionChip`/`TriageChip` (status-models). No hardcoded status/label.
- ⚠ Location column is always rendered (it is one of the ten spec columns). §2.4 hides the location *filter* for single-location orgs, which is honored; it does not call for hiding the column.

### Row detail drawer (`call-drawer.tsx`)
✅ Audio player — native `<audio controls>` on `media.recordingUrl`; rendered only when `media !== null`. Viewer/NON-PHI → `media: null` → nothing rendered (no disabled player, no faked waveform). `playRecording(session, id)` audited on first play.
✅ Full transcript with speaker labels + PII redaction markers — redaction char ranges rendered via `RedactedText` (slice-based, plain React text nodes, no raw-HTML injection API). `viewTranscript(session, id)` audited on drawer open (guarded on `media`).
✅ Recording-consent disclosure event — rendered only when `media.consentDisclosureAtUtc` is set; the fixture sets it only for `loc_north` (two-party), so it appears only there.
✅ QA grade breakdown inline — `<GradeBreakdown grade={call.grade} />` imported from `@/app/quality/grade-breakdown` (not duplicated), shown when graded.
✅ Linked objects — appointment→/appointments, VOB→/vob-queue, review request→/reviews, campaign→/campaigns; only non-null ids from `call.linked` render.
✅ Flag this interaction — writes to the shared `flag-store` (`submitFlag`), which feeds the §12.5 inbox; shows optimistic flagged state via `isFlagged`. Does NOT write an audit event (no `flag` type in the frozen 12-type `AuditEventType`).

### Deep-link
✅ `/conversations/calls?interaction={id}` read via `useSearchParams`; auto-opens that row's drawer when the id matches a loaded call. (A chat-origin id that matches no call is a graceful no-op.)

## §10.2 Chats sub-view

### Thread list (five columns)
✅ patient name where matched · ✅ channel · ✅ last message time · ✅ session outcome (contained/resolved/escalated/booked) · ✅ message count.
- ⚠ `ChatSessionOutcome` and the message-speaker union live in `@/mock/schema` with no canonical `*_LABELS` map anywhere; display labels are keyed by the imported enum in `chats/chat-display.ts` (enum stays the single source of truth; label text matches §10.2 verbatim). Same class of decision as grade bands.

### Thread detail (`chat-drawer.tsx`)
✅ Full transcript with timestamps.
✅ Handoff markers — `ChatMessage.isHandoffMarker` renders a clear "Handed off to staff" divider.
✅ Linked appointment — `chat.linked.appointmentId` → /appointments.
✅ Flag button — shared `flag-store`, same as calls.
✅ Same audit rules — `viewTranscript` on open (guarded on `messages`); `messages: null` for Viewer/NON-PHI → transcript not rendered.

## §10.3 Filters (shared)
✅ One filter bar in `_components/filter-bar.tsx`, state lifted to `ConversationsProvider` (mounted by `layout.tsx`), so it genuinely persists across the Calls ↔ Chats tab switch (App Router keeps the layout mounted).
✅ Date range · agent · channel · direction · disposition · triage · QA grade band · location · free-text search.
- ⚠ QA grade band has no canonical enum; buckets defined once in `_components/filters.ts` (90–100 / 80–89 / 70–79 / below 70). Ungraded records match only "all".
- ⚠ Call-only dimensions (agent, direction, disposition, triage) and the chat-only dimension (channel) all live in the one shared bar; each sub-view applies the subset its records carry (BUILD_NOTES B2).
✅ Free-text search audited — debounced `recordPatientSearch` in the provider (audits once regardless of active sub-view; no-ops outside PHI / on empty input).
✅ Location filter surfaced only when multi-location (§2.4).

## §10.4 NON-PHI degradation
✅ `listCalls`/`listChats` return `{ kind: 'aggregate', total, reason: 'NON_PHI_MODE' }`; both clients branch on `kind` (discriminated union — rows are unrepresentable), render the count + an explanatory panel; the shared filter bar is hidden by the layout in non-PHI mode.

## Degraded / empty states
✅ Viewer in PHI: rows + names load; `MaskedValue` shows masked phone with no reveal control (`phoneE164` absent); drawer shows no audio player and no transcript (`media`/`messages` null) — confirmed by reading the projection in `data-access.ts` and gating drawer sections on `media`/`messages`.
✅ Cedar org (6 calls, 4 chats, single-location): location filter hidden; nothing crashes.
✅ Filter yields nothing → `EmptyState`.

## Cross-cutting checks
✅ `npx tsc --noEmit` — zero errors (whole repo).
✅ `npx eslint src/app/conversations` — clean.
✅ No color literals, no `any`/`as any`, no raw-HTML injection API in `src/app/conversations/`.
✅ No 13th audit event type added; flagging writes to `flag-store`, not the audit log.

No UI element in this scope exists that cannot be traced to a §10 (or §12.3/§2.8) bullet.
