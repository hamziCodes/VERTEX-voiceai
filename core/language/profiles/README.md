# UCVE Language Profiles & Multilingual Registry

## Phase 11 Redaction Limitation Checkpoint
> [!WARNING]
> **Regex Redaction Limitation for Urdu & Arabic Script:**
> Day-1 regex redaction (from Phase 11) targets Latin-script PII/PHI patterns.
> Urdu (`ur`) and Arabic (`ar`) language profiles are marked with `redaction_script_coverage: regex_partial`.
> Multilingual NER scrubbing is queued for post-Phase 15 enhancement. See `core/compliance/redaction_limitations.md`.

## Language Profiles Supported
- `en` — English (LTR, full redaction, code-switching enabled)
- `ur` — Urdu (RTL, regex_partial redaction, code-switching disabled by default)
- `ar` — Arabic (RTL, regex_partial redaction, cs_measure_only enabled)
- `ms` — Malay (LTR, full redaction, cs_measure_only enabled)
