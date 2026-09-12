# UCVE Agent Studio — Wireflows & Interaction Architecture

## 1. Primary Agent Builder Wizard Wireflow

The Agent Studio guides developers and tenant admins through a sequential, state-validated creation and publishing journey.

```mermaid
flowchart TD
    A[Agent Directory / List View] -->|Click '+ New Agent'| B(Step 1: Template or Scratch)
    B --> C(Step 2: Persona & System Prompt)
    C --> D(Step 3: Languages & Vocal Timbre)
    D --> E(Step 4: Provider Resilience Chains)
    E --> F{Optional Integrations}
    F -->|Tools & MCP| G1[Configure MCP Servers]
    F -->|RAG Knowledge| G2[Upload Documents / FAQ]
    F -->|Structured Extraction| G3[Define Schema & Webhooks]
    G1 --> H(Step 5: Telephony & Trunks)
    G2 --> H
    G3 --> H
    F -->|Skip optional| H
    H --> I(Step 6: Compliance Tier & HIPAA Gate)
    I --> J(Step 7: Interactive Test Sandbox)
    J -->|Run Validation| K{AgentConfigValidator}
    K -->|Failures Detected| L[Display Inline Field Errors + Toasts]
    L -->|Fix Errors| J
    K -->|100% Passed| M[Publish Immutable Version Snapshot]
    M --> N[Active Published Runtime & Pinned Sessions]
```

---

## 2. Draft Autosave & Concurrent Edit State Flow

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Builder Engineer
    participant UI as Studio SPA
    participant CP as Control Plane (/v1/agents)
    participant Pin as Session Pin Engine
    participant Call as Live Voice Call

    Dev->>UI: Types modifications in Persona / Providers
    UI->>UI: Debounce Timer (30s window)
    UI->>CP: PATCH /v1/agents/{id}/autosave {patch}
    CP-->>UI: 200 OK {saved: true, updated_at}
    Note over Dev,UI: Draft is updated safely without interrupting active sessions

    Note over Pin,Call: Active call is running pinned to Version 1
    Dev->>UI: Clicks "Publish"
    UI->>CP: POST /v1/agents/{id}/publish
    CP->>CP: Run Invariant Validation (>=2 providers, RTL, HIPAA)
    CP-->>UI: 200 OK {version: 2, published_at}
    
    Note over Pin,Call: Live call remains pinned to Version 1 snapshot.
    Note over Pin,Call: Zero mid-call prompt or provider drift!
    Note over CP,UI: Future calls minting will load Version 2.
```

---

## 3. Human Review Queue Navigation Flow

```mermaid
flowchart LR
    A[CRM Dispatch / Post-Call Pipeline] -->|Confidence < Threshold| B[Human Review Queue Table]
    B -->|Select Call Record| C[Review Detail View]
    C --> D[Redacted Transcript Excerpt + Audio Snippet]
    C --> E[Extracted Key-Value Fields Form]
    E -->|Approve / Overwrite| F[Trigger Verified Webhook Dispatch]
    E -->|Reject As Hallucination| G[Mark Rejected & Archive]
```
