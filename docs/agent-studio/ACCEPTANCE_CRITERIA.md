# UCVE Agent Studio — Acceptance Criteria & Validation Gates

## Gate 1: Publish Invariant Enforcement
- **AC-1.1**: The "Publish" button triggers client-side pre-validation followed by `POST /v1/agents/{id}/publish`.
- **AC-1.2**: If any provider category (`stt`, `llm`, `tts`) has `< 2` enabled routes, publish fails with code `INSUFFICIENT_PROVIDER_ROUTES` and highlights the invalid category in red.
- **AC-1.3**: If Arabic (`ar`) is selected with an English-only voice, publish fails with code `ARABIC_RTL_VOICE_REQUIRED` and displays a guided voice recommendation dropdown.
- **AC-1.4**: If compliance tier is `hipaa` without the BAA acknowledged checkbox checked, publish is blocked with code `HIPAA_BAA_REQUIRED`.
- **AC-1.5**: Upon successful publish, the agent status badge changes to `PUBLISHED`, the version counter increments, and an immutable snapshot is archived.

---

## Gate 2: Draft Autosave & Session Pinning
- **AC-2.1**: User keystrokes in the Persona editor or form inputs trigger a debounced `PATCH /v1/agents/{id}/autosave` request after 30 seconds of inactivity.
- **AC-2.2**: The top navigation displays an autosave status indicator: `Saving...` -> `Saved as draft (HH:MM:SS)`.
- **AC-2.3**: If a voice call is active during a draft save or new publish, the ongoing call's audio, prompts, and provider chain do not change (pinned snapshot integrity).

---

## Gate 3: Test Call Sandbox Allowance
- **AC-3.1**: The Test Sandbox widget displays the remaining monthly test call allowance (default: 30 minutes/month).
- **AC-3.2**: Test calls in the studio use `usage_kind=test_call_sec` in Phase 14 metering, which does NOT deduct from the tenant's commercial production billing quota.
- **AC-3.3**: When the 30-minute allowance reaches 0, the studio disables the test microphone button and prompts the admin to request a sandbox extension.

---

## Gate 4: Security & Credential Masking
- **AC-4.1**: Under no circumstances does the Studio UI display raw external API keys.
- **AC-4.2**: MCP connection credentials and webhook secrets are rendered as masked placeholders (`••••••••••••`) referencing Phase 09 credential vault keys.
- **AC-4.3**: System prompt text area features a prominent security badge: *"Tenant DATA Layer — Isolated from core engine system prompt instructions"*.

---

## Gate 5: Scope Boundaries (Outbound Exclusion)
- **AC-5.1**: There is NO UI for outbound campaigns, predictive dialers, or contact list uploads.
- **AC-5.2**: Telephony configuration is strictly scoped to Inbound DIDs and SIP trunk registration.
