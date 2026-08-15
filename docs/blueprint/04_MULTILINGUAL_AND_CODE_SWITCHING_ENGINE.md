# 04 — Multilingual & Code-Switching Engine

File 4 of 9. This is the domain where the four legacy repos most directly disagree with each other, which makes it the most important place in the whole blueprint to be explicit about *why* UCVE picks what it picks rather than silently averaging conflicting approaches.

---

## 1. The Core Disagreement (state it plainly)

Two of the four repos enable acoustic code-switching for Urdu; one deliberately disables it with a measured rationale:

| Repo | Urdu code-switching | Rationale given | Citation |
|---|---|---|---|
| v3 | `code_switching=True`, `languages=["ur","en"]` | None documented — just the config | AUDIT_01 §2 STT |
| Multilingual | `code_switching=True`, `languages=["ur","en","ar","ms"]` | None documented beyond enabling 4-way CS | AUDIT_03 §2 STT |
| Habiba | `code_switching=False`, single language | **Measured**: code comment cites CER 0.14 (CS off) vs 0.43 (CS on) for Urdu | AUDIT_04 §2 VAD/STT, §5 |

**UCVE's decision:** code-switching is a **per-language, per-tenant configuration flag**, not a global architectural stance — because habiba's data point is the only one of the three that's actually *measured*, not assumed. The default for Urdu is `code_switching=False` following habiba's evidence, but v3/multilingual's `True` configuration remains available and is likely correct for tenants whose callers genuinely mix scripts mid-sentence more than Finova's retail context did. This is exactly the kind of decision the `[NEW]` provider config in File 3 §2 (`STTConfig.code_switching: bool`, default `False`) exists to make tenant-overridable rather than hardcoded either way.

**Required follow-up work (not yet done by any audited repo):** none of the four repos ran a controlled CER comparison outside Urdu. Before defaulting Arabic or Malay code-switching on or off, UCVE's implementation team should run the same measurement habiba ran for Urdu, per-language, rather than copying multilingual's blanket `True` for all four languages (AUDIT_03 §2 lists `["ur","en","ar","ms"]` all with `code_switching=True` with no per-language justification shown in the audit).

---

## 2. Code-Switching Pipeline

### 2.1 Acoustic layer (STT-side)

Handled entirely by the STT provider adapter's `code_switching` flag (File 3 §2). No in-house acoustic language-ID model is built here — Gladia streaming STT is used by three of four repos (AUDIT_01/03/04 §2), with `code_switching=True` only in v3 and multilingual (AUDIT_01/03 §2 STT); habiba's Gladia path sets CS off with a measured CER rationale (AUDIT_04 §2). Deepgram appears as an alternate `en` STT provider in habiba's capability table (AUDIT_04 §2 STT); CS/LID behavior for Deepgram is **NOT VERIFIED** (AUDIT_04 §5). Building a custom acoustic LID model is explicitly **out of scope** for the initial roadmap (File 9) since no legacy repo attempted one and provider-native language tagging has evidenced production use in the Gladia-backed repos.

### 2.2 Text-layer language routing

This is where multilingual's `LanguageRouter` is the clear best-of-breed component (AUDIT_05 §2: "Language router debounce... neither v3 nor habiba has this"):

```python
class LanguageRouterConfig(BaseModel):
    debounce_short_utterance_word_threshold: int = 3   # multilingual constant,
                                                          # AUDIT_03 §3 language
    debounce_consecutive_detections_required: int = 2   # for utterances below
                                                          # the word threshold
    fallback_language: str = "en"                        # multilingual default
                                                          # when STT returns an
                                                          # unrecognized code,
                                                          # AUDIT_03 §5: "Fallback
                                                          # language 'en' if unknown"


class LanguageRouter:
    """Ported near-verbatim from multilingual's language_router.py
    (AUDIT_03 §3 language; file listed in AUDIT_03 §1 tree). Logic:
      - utterance >= 3 words with a detected language: switch immediately
      - utterance < 3 words: require 2 consecutive detections of the same
        language before switching (avoids single-word noise triggering a
        language flip)
      - unsupported/missing language code: KEEP current language rather
        than switching (AUDIT_03 §3: 'unsupported codes ignored... missing
        code keeps current')
    """

    def route(self, transcript: "Transcript", current_language: str) -> str: ...
```

### 2.3 Per-language directive injection

```python
class LanguageProfile(BaseModel):
    """Generalizes multilingual's YAML LanguageProfile
    (backend/app/core/config/languages/{en,ur,ar,ms}.yaml, AUDIT_03 §1)."""

    code: str                                    # ISO 639-1
    directive_prompt_path: str                    # short per-turn system directive
    vad_silence_override_ms: int | None = None    # ur/ar: 800ms override,
                                                    # AUDIT_03 §2 VAD
    tts_voice_id: str
    tts_first_chunk_word_count: int = 2           # multilingual's aggressive
                                                    # first-chunk split for fast
                                                    # TTFB, AUDIT_03 §5 — NOTE the
                                                    # tradeoff below
    script_direction: str = "ltr"                  # "rtl" for ur/ar
```

**Injection point** (both legacy repos independently converged on this being "right before the final user turn is sent to the LLM"):

- v3: no per-language directive system exists — it's a single hardcoded Urdu-only persona (AUDIT_01 §1: "persona-locked to a hardcoded 'Zara / Finova Computers' prompt").
- Multilingual: `prompt_builder.build_messages` inserts the `ephemeral_directive` immediately before the user turn (AUDIT_03 §6 RAG injection point note, reused here since it's the same injection site). This is the pattern UCVE adopts as the canonical directive-injection point, generalized beyond just RAG context to also carry the active `LanguageProfile.directive_prompt_path` content.

---

## 3. Phoneme & Lexicon Normalization

**Gap identified:** neither v3 nor multilingual implements a text pre-processing/normalization pass before handing text to TTS — both just chunk on punctuation and forbid Latin script in the LLM's own output via prompt instruction (AUDIT_01 §5: "System prompt forbids Latin script in LLM output... while STT may emit mixed-script Minglish — mismatch can push Gemini to 'correct' or hallucinate Urdu orthography"). This is a real, cited failure mode, not a theoretical concern.

### 3.1 Normalization pipeline `[NEW]`

```python
class TextNormalizer:
    """Runs between LLM output and the sentence chunker (File 1 §2.3
    component diagram: LLMAdapter -> Chunker). Not present in any legacy
    repo as a distinct stage — v3's mitigation is prompt-only instruction
    (AUDIT_01 §5: 'Unclear-speech instruction is prompt-only'), which the
    audit itself flags as insufficient since no confidence threshold from
    STT is actually consumed to gate it."""

    def normalize(self, text: str, language: str) -> str:
        """Steps, in order:
        1. Script consistency check: if output mixes Urdu/Arabic script
           with Latin script mid-word (not intentional code-switch), flag
           for regeneration rather than passing to TTS as-is — this
           directly closes the mismatch AUDIT_01 §5 identifies.
        2. Numeral normalization: convert digit sequences to the
           spoken-word form appropriate to the active language (dates,
           prices, phone numbers) BEFORE synthesis, not left to the TTS
           provider's own (often English-biased) number reader.
        3. Custom pronunciation lexicon lookup: brand names, product SKUs,
           and tenant-specific terms (e.g. 'Finova' in the v3 persona,
           AUDIT_01 §1) get an explicit phonetic override so TTS doesn't
           mispronounce them — none of the four repos have a lexicon
           mechanism; this is new tenant-configurable data (add a
           lexicon upload field to File 8 agent builder schema —
           not present in the initial schema draft; corrected during
           finalization pass).
        4. Asterisk/formatting-artifact strip: v3's prompt explicitly
           instructs against literal asterisks in TTS output
           (AUDIT_01 §4 Telephony: grep note on 'asterisks' in prompt
           TTS-format rules, retail_prompt.md:10) — UCVE enforces this
           as code, not prompt-only instruction,
           stripping markdown-style emphasis characters before synthesis
           regardless of whether the LLM followed instructions.
        """
```

### 3.2 Sentence/clause chunking — reconciling two different strategies

| Aspect | v3 | Multilingual | UCVE |
|---|---|---|---|
| Split characters | `.?!۔؟` sentence, `,،;؛:` clause (≥3 words) | Not fully detailed in audit beyond first-chunk override | Superset of v3's Urdu+English punctuation set, extended per-language via `LanguageProfile` |
| Conjunction-based split | Urdu/EN conjunctions, ≥4 words | — | Retained from v3 (AUDIT_01 §2 LLM) |
| Fallback word-count split | 10th word | 2nd word (first chunk only, for fast TTFB) | **Both**, contextually: 2-word aggressive split for the *first* chunk of a turn (fast perceived response), 10-word fallback for subsequent chunks (avoids the risk multilingual's own audit flags) |
| **Known risk with aggressive first-chunk split** | 10-word split "can cut mid-code-switch phrase" (AUDIT_01 §5) | 2-word split "can speak mid-code-switch fragment" (AUDIT_03 §5) — same risk, worse, because it triggers on EVERY turn's opening, not just long ones | UCVE's `TextNormalizer` (§3.1) step 1 runs **before** chunking specifically to reduce this risk — code-switch boundaries are identified and chunk breaks are biased to fall on them rather than mid-phrase |

---

## 4. Language Detection On-the-Fly

**Dual-pass detection**, combining what habiba does at the acoustic layer with what multilingual does at the text layer — neither legacy repo does both:

1. **Acoustic pass:** STT provider's native language tagging on partial/final transcripts (`Transcript.language` field, File 3 §2 — the field v3 collects but never reads, AUDIT_01 §5; multilingual does read it, AUDIT_03 §2: "Output type: `interfaces.Transcript` including `language`").
2. **Text pass:** `LanguageRouter` debounce logic (§2.2 above) as a secondary confirmation layer, since acoustic language tags on short utterances are the noisiest signal (this is exactly why multilingual's debounce threshold exists — AUDIT_03 §3: "short (<3 words) needs 2 consecutive detections").

Neither pass alone is treated as authoritative; the router's job (§2.2) is reconciling them, which is precisely multilingual's existing design — UCVE's contribution is making the acoustic-tag consumption mandatory (fixing v3's gap) rather than optional.

---

## 5. Localized Prosody

**Gap identified:** no legacy repo does anything with prosody beyond selecting a fixed `voice_id` per language (v3: `uplift_voice_id` single default; multilingual: per-language voice via `TTSManager`; habiba: `voices.provider_voice_id` resolved per tenant agent config, AUDIT_04 §2 TTS). None adjust rate, pitch, or emphasis dynamically based on conversational context (e.g., slowing down for a phone-number confirmation, raising pitch for a question).

**UCVE `[NEW]`:** extend File 3 §2 `TTSConfig` with optional SSML-style hints (`rate`, `pitch`, `emphasis_spans`) that the chunker/normalizer can set based on detected content type (e.g., digit sequences from §3.1 step 2 get a `rate: slow` hint). File 3 now declares these optional fields; they remain **deferred** — not in File 9 Phase 1–5 exit criteria; treat as post–Phase 5 hardening / optional polish, not a day-one requirement.

> Corrected during finalization pass: earlier text claimed File 3 already had these fields and pointed at "File 9 Phase 4"; Phase 4 is MCP/RAG, and the fields were absent until this pass.
