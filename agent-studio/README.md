# UCVE Agent Studio (Standalone SPA)

The **UCVE Agent Studio** is a standalone single-page application (SPA) providing visual self-serve agent configuration, persona design, provider resilience tuning, and live audio testing for the Unified Core Voice Engine.

---

## 1. Specification Architecture

This folder provides the engineering blueprint and interface contracts for the standalone Agent Studio SPA.

### Core Documentation
- **[Wireflows & User Journeys](file:///d:/PROJECTS/PASSION%20PROJECTS/VERTEX_voiceai/docs/agent-studio/WIREFLOWS.md)**: Sequential builder wizard, autosave debounce, and session pinning state machines.
- **[Screen Inventory](file:///d:/PROJECTS/PASSION%20PROJECTS/VERTEX_voiceai/docs/agent-studio/SCREEN_INVENTORY.md)**: Detailed breakdown of screens `SCR-01` through `SCR-13` mapping Blueprint File 8 §5 features.
- **[Component Contracts](file:///d:/PROJECTS/PASSION%20PROJECTS/VERTEX_voiceai/docs/agent-studio/COMPONENT_CONTRACTS.md)**: TypeScript interfaces, React props, and event signatures.
- **[Acceptance Criteria](file:///d:/PROJECTS/PASSION%20PROJECTS/VERTEX_voiceai/docs/agent-studio/ACCEPTANCE_CRITERIA.md)**: Testable validation gates covering invariant checks, autosave, and test call sandbox rules.
- **[Human Review Queue UX](file:///d:/PROJECTS/PASSION%20PROJECTS/VERTEX_voiceai/docs/agent-studio/HUMAN_REVIEW_QUEUE_UX.md)**: Phase 21 low-confidence extraction verification workflow.
- **[Arabic & RTL Builder Notes](file:///d:/PROJECTS/PASSION%20PROJECTS/VERTEX_voiceai/docs/agent-studio/RTL_BUILDER_NOTES.md)**: RTL input switching and Phase 15 voice validation surfacing.
- **[Test Call Billing & Sandbox](file:///d:/PROJECTS/PASSION%20PROJECTS/VERTEX_voiceai/docs/agent-studio/TEST_CALL_BILLING.md)**: 30 min/month free test-call allowance separated from production quota.
- **[Outbound UI Deferral](file:///d:/PROJECTS/PASSION%20PROJECTS/VERTEX_voiceai/docs/agent-studio/OUTBOUND_UI_DEFERRED.md)**: Explicit scope boundary documentation.

---

## 2. Technical Stack & Deployment Strategy

- **Framework**: React 18+ with TypeScript, Vite, Tailwind CSS / Vanilla Design Tokens.
- **Hosting**: Standalone SPA hosted on separate CDN origin (e.g. `studio.voiceai.domain`).
- **Auth**: Shared OIDC / JWT with control-plane (`x-tenant-id` + bearer token). No portal iframe embedding.
- **Backend API**: Connects directly to Control Plane endpoints at `/v1/agents` (Phase 26).
