# UCVE Agent Studio — Test Call Billing & Sandbox Policy

## 1. Core Principle: Frictionless Developer Iteration
Building high-fidelity voice agents requires extensive test dialing, prompt tuning, and barge-in experimentation.
To prevent builder hesitation, **Studio Test Calls do not consume commercial production call quotas.**

---

## 2. Sandbox Allowance Specifications
- **Monthly Allowance**: 30 minutes (1,800 seconds) per tenant per billing cycle.
- **Metering Classification**: Recorded in Phase 14 usage records under `usage_kind = 'test_call_sec'`.
- **Production Quota Isolation**:
  - Phase 14 hard caps (80% warning / 100% suspension) apply strictly to `usage_kind = 'prod_call_sec'`.
  - An agent under active construction can run test calls in the Studio even if production minutes are paused.

---

## 3. Studio UI UX Surfacing
- **Header Counter**: Displays `Sandbox Test Time: 24m remaining (resets Oct 1)`.
- **Exhaustion Behavior**:
  - If the 30-minute sandbox pool reaches 0, a modal is displayed:
    > **Sandbox Limit Reached**: You have used your 30 minutes of free monthly studio testing. Click below to request a sandbox extension from your administrator or upgrade your developer tier.
  - The live microphone button in the Test Sandbox is safely disabled to prevent accidental charges.
