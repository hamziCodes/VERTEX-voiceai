# Phase 16: Text Normalization and Pronunciation Layer

## 1. Executive Summary & Core Logic

Add a deterministic text normalization stage between LLM output and TTS chunking: script consistency checks, numeral/date spoken-form conversion, markdown cleanup, and tenant pronunciation lexicon lookup. Gap in all legacy repos — v3 relied on prompt-only "no Latin script" instruction (`legacy_codebases/AI_voice_agent_v3 - gemini/backend/app/core/prompts/retail_prompt.md`) while STT emitted mixed script (AUDIT_01 §5). MULTI `prompt_builder.py` injects directives but has no normalizer (`legacy_codebases/Multilingual_AI_Voice_Agent_gittracked/backend/app/services/llm/prompt_builder.py`). Depends on Phase 15 active language profile and Phase 05 TTS native-rate output.

**English-in-Urdu:** Latin-script English tokens in Urdu turns are **pass-through** to TTS — not transliterated, not translated. Pakistani speech code-switches naturally (Minglish); forcing translation would be wrong.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| Pipeline stage `TextNormalizer.normalize(text, language)` | File 04 §3.1 |
| `num2words` or language-specific numeral maps | Urdu/Arabic digit reading |
| Tenant lexicon from Phase 08 agent JSONB | File 08 `pronunciation_lexicon` |
| Regeneration + provider fallback | Fail-safe before bad TTS; bounded retries |

**Reference docs:** blueprint File 04 §3; MULTI `groq_service.py` first-chunk 2-word TTFT split (lines 42–43 per File 04).

## 3. What / How / Why

- **What:**
  - `TextNormalizer` steps (ordered):
    1. Strip markdown artifacts (`**`, `` ` ``, bullet prefixes)
    2. Script consistency check — flag mixed-script tokens for regeneration **except** Latin English tokens in Urdu context (pass-through per decision above)
    3. Numeral/date/phone normalization to spoken form per active `language`
    4. Pronunciation lexicon substitution (grapheme → plain-text replacement for brand/SKU terms)
    5. **SSML hints to TTS:** `[LATER]` — not v1; plain text + lexicon only
  - `SentenceChunker` — port MULTI/v3 chunk-on-punctuation; first chunk **2 words** for TTFT (MULTI `groq_service.py`), subsequent chunks per language YAML `chunk_min_words`
  - `NormalizationResult`: `{text, warnings, needs_regeneration, regeneration_attempt}`
  - **Regeneration policy:** up to **2 regeneration retries** with stricter directive from Phase 15 profile; on third failure (`needs_regeneration` still true), escalate to Phase 06 `FailoverRouter` for next LLM provider in chain — **not** infinite loop, **not** silent pass-through of bad script
- **How:** Called in Phase 17 pipeline after LLM stream completes per sentence boundary, before TTS enqueue. Warnings → Phase 07 structured log. Regeneration re-invokes LLM with tightened directive; after 2 failed regenerations, `FailoverRouter.call_with_failover(category="llm", ...)` selects next provider. TTS receives plain text only in v1.
- **Why this approach:** Prompt-only mitigation failed in v3 when STT Minglish conflicted with Urdu-only LLM lock. Normalizer as code enforces what prompts cannot guarantee — but must respect real code-switching (English pass-through). Alternative: LLM asked to output IPA — unreliable across models.

## Deliverables

- `core/language/normalizer.py` — `TextNormalizer`, English pass-through rules for Urdu
- `core/language/chunker.py` — `SentenceChunker`
- `core/language/numerals.py` — per-language numeral spoken forms
- `core/language/lexicon.py` — tenant lexicon lookup
- `core/language/normalization_result.py`
- `core/language/regeneration.py` — retry counter + FailoverRouter handoff
- `tests/fixtures/normalizer/` — mixed-script, numeral, markdown, English-in-Urdu pass-through cases

## 4. Compute & Resource Profile (if applicable)

Normalizer: ~0.5–2 ms per sentence. Chunker: negligible. Lexicon lookup: O(entries) hash map — < 0.1 ms. Regeneration worst case: 2 extra LLM calls before fallback — post-call acceptable, real-time bounded.

## 5. Compliance Notes (if applicable)

Normalizer must not log pre-redaction PHI at INFO+ (Phase 07). Phone numbers in normalization output destined for TTS may be PHI — apply Phase 11 redaction policy before persistence if stored.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Regeneration retry count:** **2 retries**, then Phase 06 fallback provider — not infinite, not 1-only.
2. **SSML hints to TTS:** defer — mark `[LATER]`; plain text + lexicon for v1.
3. **English words in Urdu script/context:** **pass-through**, not transliteration or translation.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_16_text_normalization.py`
- **Asserts:** markdown stripped; `1234` → spoken ur/en forms; lexicon replaces brand term; mixed-script (non-English) triggers `needs_regeneration`; Latin English in Urdu pass-through without regeneration; 2 regeneration attempts then FailoverRouter invoked; chunker first chunk ≤2 words; subsequent chunks respect min words; no SSML emitted in v1.
- **Pass threshold:** 100% fixture cases.
- **Latency target:** normalize+chunk 100 sentences < 200 ms (excl. regeneration LLM calls).
