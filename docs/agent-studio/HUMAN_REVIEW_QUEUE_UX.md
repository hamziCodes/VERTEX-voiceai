# UCVE Agent Studio — Human Review Queue UX Spec

## 1. Objective
When post-call extraction confidence drops below tenant threshold (Phase 21 §2), structured records are routed to the **Human Review Queue** (`/agents/:id/review-queue`) instead of automated CRM dispatch.

---

## 2. Screen Layout & Components

### A. Review Queue Table (`SCR-12A`)
- Columns: `Call Timestamp`, `Caller ID (Masked)`, `Overall Confidence (%)`, `Pending Fields`, `Actions`.
- Badges:
  - `Red (< 0.70)`: High ambiguity, full verification needed.
  - `Amber (0.70 - 0.85)`: Minor field clarification needed.
- Bulk actions: `Bulk Dismiss Hallucinations`.

### B. Verification Workspace (`SCR-12B`)
- **Left Panel: Evidence Stream**
  - Scrubbable dual-channel audio player synced to transcript.
  - PII-redacted transcript (Phase 11: credit cards, SSNs, and passwords masked as `[REDACTED]`).
  - Highlighted sentence segments that contributed to extracted fields.
- **Right Panel: Structured Fields Form**
  - Editable form inputs mapped to the agent's `TenantExtractionSchema`.
  - Confidence meter per field.
  - Buttons:
    - **"Approve & Dispatch CRM Webhook"**: Finalizes extraction and dispatches HMAC-signed payload to tenant webhook URL.
    - **"Reject as Hallucination"**: Discards extraction and flags LLM prompt hallucination telemetry.

---

## 3. Compliance & Security
- Reviewers see only redacted PII transcripts unless granted `compliance_officer` role.
- All approval/rejection events are logged to the Phase 12 audit trail with actor ID.
