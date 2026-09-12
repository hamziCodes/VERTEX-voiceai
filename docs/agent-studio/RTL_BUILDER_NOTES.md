# UCVE Agent Studio — RTL & Arabic Builder UX Specifications

## 1. Overview
Arabic language agents present unique UX requirements in text directionality, typography, and vocal timbre validation (Phase 15).

---

## 2. Dynamic Directionality & Typography
- **Input Directionality**:
  - Persona system prompt and greeting textareas dynamically switch to `dir="rtl"` when the active editing language is Arabic (`ar`).
  - Font stack incorporates `Noto Sans Arabic` or `IBM Plex Sans Arabic` to prevent character clipping or incorrect ligature shaping.
- **Bilingual Interface**:
  - Technical labels (e.g. `STT Provider`, `Max Tokens`, `LLM TTFT`) remain LTR, while Arabic conversational prompts and lexicon entries render RTL.

---

## 3. Inline Phase 15 Voice Validation Surfacing
- When Arabic (`ar`) is enabled in the agent's language checklist:
  1. The voice selection dropdown filters and prioritizes verified Arabic RTL voices (`ar-sa-naima`, `ar-ae-fatima`, `cartesia-arabic-v1`, `orpheus-arabic-saudi`).
  2. If a non-RTL voice is selected, the UI immediately surfaces an inline warning banner:
     > **⚠️ RTL Voice Invariant**: Arabic conversational agents require an RTL-capable voice model with proper pharyngeal and emphatic consonant synthesis. Publishing with an English-only voice is blocked by Phase 15/26 policy.
  3. A **"Preview Arabic Sample"** button plays a pre-synthesized audio greeting clip to verify acoustic realism.
