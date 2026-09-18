# Active Context — VERTEX_voiceai

> Last crystallized: 2026-09-08 (TTS playback resume).

## 0. TTS PLAYBACK (resume target)

**Doc:** `docs/developer/CHECKPOINT_TTS_PLAYBACK_2026-09-08.md`

**Finding:** Server PCM was fine (`peak_abs` up to 12227). Real bug: `pcm16-player` `instanceof Float32Array` dropped all chunks across worklet realm. Fixed + **Cartesia** added (demo default).

**Your check:** restart CP/worker yourself; hard-refresh demo; TTS=Cartesia; expect non-zero `peak=` and audible speech.

Demo: Gladia / Groq / Cartesia|Uplift|ElevenLabs · `UCVE_PIPELINE_V2=production` · `RUN_LIVE_PROVIDERS=1`

---

## 1. Current Operational State

| Item | Status |
|------|--------|
| Forensic audit (4 repos) | **DONE** — `AUDIT_01`…`04` + `AUDIT_05` + `AUDIT_PROGRESS.md` |
| Source trees modified | **NO** — audits write-only to workspace root |
| Memory bank | **DONE** — this folder |
| Unified engine code | **IN PROGRESS** — voice pipeline V2 + demo playback fix |
| Claude architectural prompt pack | **NOT PREPARED** in prior session |
| Workspace git | Root repo `VERTEX-voiceai` on GitHub; nested gits still inside each legacy project |
| Legacy layout | Four inspiration trees live in `legacy_codebases/` |

### What we know (do not re-search)
- AWAZ = CRM/dashboard/Retell — **not** voice PCM
- HAB telephony = Telnyx+LiveKit SIP — **not** Twilio/Asterisk
- V3 VAD = Silero only — **not** WebRTC VAD
- Best modularity: HAB 8/10 > MULTI 7/10 > AWAZ 5/10 > V3 3/10
- Harvest map: see `audit_synthesis.md` §3

---

## 2. Next Immediate Milestones

1. **Confirm audible TTS** in demo after playback worklet fix (human ear check)
2. If still silent: use worker `TTS PCM egress chunk peak_abs` vs client `rms=` to split server vs browser
3. Only then touch providers / AEC / barge thresholds

Out of scope until flagged: Dual S2S, TwilioMediaStream, MCP servers, Stripe, Vault.

---

## 3. Hard Constraints (carry forward)

- Do **not** modify the 4 legacy trees unless explicitly migrating/copying out
- Do **not** re-audit from scratch — trust AUDIT_* + this bank
- Secrets stay out of git; never open `API KEYS VOICESDK*` without explicit ask
