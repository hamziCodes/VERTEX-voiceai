# Active Context — VERTEX_voiceai

> Last crystallized: 2026-08-15.

## 1. Current Operational State

| Item | Status |
|------|--------|
| Forensic audit (4 repos) | **DONE** — `AUDIT_01`…`04` + `AUDIT_05` + `AUDIT_PROGRESS.md` |
| Source trees modified | **NO** — audits write-only to workspace root |
| Memory bank | **DONE** — this folder |
| Unified engine code | **NOT STARTED** |
| Claude architectural prompt pack | **NOT PREPARED** in prior session (no dedicated Claude architecture deliverable found; only in-repo `legacy_codebases/habiba-sdk-agent/docs/.clauderules` etc.) |
| Workspace git | Root repo `VERTEX-voiceai` on GitHub; nested gits still inside each legacy project |
| Legacy layout | Four inspiration trees live in `legacy_codebases/` (source tracked on git for Cursor Cloud) |
| Dirty trees | MULTI had **pre-existing** dirty tree; auditor did not write those files |

### What we know (do not re-search)
- AWAZ = CRM/dashboard/Retell — **not** voice PCM
- HAB telephony = Telnyx+LiveKit SIP — **not** Twilio/Asterisk
- V3 VAD = Silero only — **not** WebRTC VAD
- Best modularity: HAB 8/10 > MULTI 7/10 > AWAZ 5/10 > V3 3/10
- Harvest map: see `audit_synthesis.md` §3

### Long-form sources (token-expensive — use only when memory_bank insufficient)
```
AUDIT_01_AI_VOICE_AGENT_V3.md
AUDIT_02_AWAZLABS.md          # covers awaazlabs/
AUDIT_03_MULTILINGUAL_AGENT.md
AUDIT_04_HABIBA_SDK_AGENT.md
AUDIT_05_SYNTHESIS_AND_FEATURE_MATRIX.md
AUDIT_PROGRESS.md
```

---

## 2. Next Immediate Milestones (fresh session sprint)

1. **Scaffold** `unified_core/` (or agreed name) at workspace root — empty packages: `transport/`, `vad/`, `stt/`, `llm/`, `tts/`, `session/`, `crm/`, `control_plane/`
2. **Port VAD** from MULTI `vad_service.py` + V3 threshold defaults; unit-test frame sizes 512@16k
3. **Port WS transport** from V3/MULTI as `NativeWebSocket` adapter (auth token stub)
4. **Wire Gladia STT** using HAB ur CS=False policy + MULTI lang YAML
5. **Wire LLM+TTS** — persona isolation (HAB) + `tts_manager` failover (MULTI)
6. **Barge-in** MULTI verify loop + fix V3 D4 (barge final → next turn)
7. **Mint/session** slim HAB control plane (fix in-memory rate limit → Redis later)
8. **CRM hook** — adapt AWAZ extraction schema to own `call_ended` events
9. **Update memory_bank** after each milestone (paths, decisions, debt closed)

Out of scope until flagged: Dual S2S, TwilioMediaStream, MCP servers, Stripe, Vault.

---

## 3. Pending Claude Prompts

| Prompt / Task | Status | Notes |
|---------------|--------|-------|
| Claude architecture pack (system design dump) | **ABSENT** | User expected prompts; none produced in audit session |
| Process Claude output → refine `target_unified_engine.md` | **BLOCKED** on above |
| Generate Cursor build prompts from Claude output | **PENDING** |

When Claude pack arrives: paste/store under `memory_bank/claude_inbox/` (create on receipt), then distill into `target_unified_engine.md` + sprint checklist above.

---

## 4. Hard Constraints (carry forward)

- Do **not** modify the 4 legacy trees unless explicitly migrating/copying out
- Do **not** re-audit from scratch — trust AUDIT_* + this bank
- Do **not** read `.env` (secrets); use `.env.example` + source
- Prefer copy-forward of proven modules over rewrite
- Path with space: quote `"legacy_codebases/AI_voice_agent_v3 - gemini"`
