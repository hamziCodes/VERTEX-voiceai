# UCVE Agent Studio — Screen Inventory

This inventory maps all features from Blueprint File 8 §5 to dedicated screens in the Agent Studio SPA.

| Screen ID | Screen Title | Route Path | Blueprint Reference | Description & Key Features |
|---|---|---|---|---|
| `SCR-01` | **Agent Directory** | `/agents` | File 8 §5.1 | List of all tenant agents, publish status indicators, version badges, last test call results, duplicate, and archive actions. |
| `SCR-02` | **Template Picker** | `/agents/new` | File 8 §5.1 | Choice between blank canvas and platform seed templates (`retail_customer_service`, `clinic_intake`). |
| `SCR-03` | **Persona Editor** | `/agents/:id/persona` | File 6 §1, File 8 §5.2 | System prompt editor featuring the mandatory **"Tenant DATA — Isolated from core prompts"** banner; greeting box; voice timbre selection. |
| `SCR-04` | **Languages & Vocal Timbre** | `/agents/:id/languages` | File 8 §5.3, Phase 15 | Multi-language toggles, per-language voice picker, live audio TTS sample preview button, and inline RTL validation alerts. |
| `SCR-05` | **Provider Priority Chains** | `/agents/:id/providers` | File 1 §3.6, Phase 06 | Visual drag-and-drop failover chain editor for STT, LLM, TTS, S2S. Enforces ≥ 2 enabled routes per critical category. |
| `SCR-06` | **Tools & MCP Servers** | `/agents/:id/tools` | Phase 22 | Tool registry, MCP server connector forms (HTTP/SSE), auth header inputs with masked secrets (`••••`), and live connectivity probe button. |
| `SCR-07` | **Knowledge Bases (RAG)** | `/agents/:id/knowledge` | Phase 23 | Document upload dropzone (PDF/Markdown/FAQ), chunking preview, embedding tier indicator, and pgvector collection sync status. |
| `SCR-08` | **Structured Extraction Builder** | `/agents/:id/extraction` | Phase 21 | Form-based schema editor, field validation, JSON Schema export, and field count counter with a hard cap warning at 50 fields. |
| `SCR-09` | **Telephony & DID Routing** | `/agents/:id/telephony` | Phase 18, 19 | Inbound DID phone number assignment, SIP trunk selection, direct sovereign SIP URI endpoint. Outbound campaigns explicitly excluded. |
| `SCR-10` | **Compliance & Governance** | `/agents/:id/compliance` | Phase 10, 11 | Compliance tier dropdown (`standard`, `hipaa`, `pci_reserved`), HIPAA BAA agreement checkbox with timestamp lock, retention policy defaults. |
| `SCR-11` | **Interactive Test Sandbox** | `/agents/:id/sandbox` | File 8 §5.4, Phase 14 | WebRTC/WebSocket live voice talking widget, remaining sandbox allowance counter (30 min/mo), waterfall latency telemetry panel. |
| `SCR-12` | **Human Review Queue** | `/agents/:id/review-queue` | Phase 21 | Filterable table of low-confidence extraction records, redacted transcript viewer, and field correction / approval actions. |
| `SCR-13` | **Live Monitor (Read-Only)** | `/agents/:id/monitor` | File 7 §5 | Read-only stub panel displaying concurrent calls, active session IDs, and real-time audio health status. |
