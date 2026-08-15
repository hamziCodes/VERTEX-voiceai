# Cursor Rules & Skills — VERTEX_voiceai

## 1. Agent Operational Guidelines

### Session bootstrap (mandatory order)
1. Read `memory_bank/active_context.md` — state + next milestones
2. Skim `memory_bank/codebase_maps.md` — paths/aliases only as needed
3. Skim `memory_bank/audit_synthesis.md` — harvest + debt IDs
4. Read `memory_bank/target_unified_engine.md` — if building architecture
5. Open full `AUDIT_0N_*.md` **only** when a claim needs line-level proof

### Do
- Prefer harvesting proven code from MULTI/HAB/V3/AWAZ over greenfield
- Cite exact paths when changing or porting modules
- Keep memory_bank updated when decisions, paths, or debt status change
- Quote paths with spaces: `"legacy_codebases/AI_voice_agent_v3 - gemini"`
- Use alias table: V3 / MULTI / HAB / AWAZ=`awaazlabs` under `legacy_codebases/`

### Don't
- Re-audit the four repos from scratch
- Treat AWAZ as a voice engine
- Assume Twilio/Asterisk/WebRTC-VAD/MCP exist in legacy code
- Modify legacy trees unless user asks to migrate
- Read or commit `.env` / secrets
- Invent features as “existing” — use ABSENT if not in audits

### Debt IDs to respect during build
Fix or explicitly defer: D1–D14 in `audit_synthesis.md` (esp. D5 torch missing, D9 sync psycopg in async, D12 fail-open webhook, D13 client role headers).

---

## 2. Freedom of Implementation Protocol

Architecture specs in `target_unified_engine.md` are **living blueprints**, not frozen contracts.

**Authorized without waiting for user re-approval:**
- Adapt JSON Agent Builder schemas (add/rename fields)
- Refactor class/module boundaries if transport/session clarity improves
- Swap provider defaults if latency/quality evidence warrants
- Choose package layout names (`unified_core/` vs `vertex_engine/`, etc.)
- Update any file under `memory_bank/` when reality diverges from the bank
- Drop or defer Dual S2S / Twilio / MCP until MVP cascaded path works

**Still require user confirmation:**
- Destructive changes to the 4 legacy repos
- New paid vendor lock-in beyond already-used stacks (Gladia/Gemini/Groq/Uplift/LiveKit/Telnyx/Clerk)
- Commits / PRs / pushes (only when user asks)
- Broad scope expansion (billing, KMS, self-hosted SFU) before MVP

### Memory bank maintenance rule
After each meaningful build milestone:
```
active_context.md     ← progress + next tasks
codebase_maps.md      ← new module paths
audit_synthesis.md    ← mark debt CLOSED / NEW
target_unified_engine.md ← sync if schema/arch changed
```

### Token discipline
- Start sessions from memory_bank (≤~2k tokens/file target)
- Avoid dumping full AUDIT_* into context unless debugging a specific claim

---

## 3. Quick Reference Card

| Need | File |
|------|------|
| What to do now | `active_context.md` |
| Where is X? | `codebase_maps.md` |
| What to copy / what is broken | `audit_synthesis.md` |
| What we are building | `target_unified_engine.md` |
| How agents must behave | this file |
| Line-level proof | `auit_docs/AUDIT_01`…`05` |
