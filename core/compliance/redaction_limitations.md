# UCVE Redaction Service Known Limitations & Checkpoints

## Regex-Only Limitation (Phase 11)
- **Scope:** Current Day-1 redaction uses pattern-matching regexes targeting Latin-script PII/PHI (phone numbers, email addresses, SSNs).
- **Non-Latin Script Gap:** Regex redaction **does not detect names, locations, or numeric identifiers in Arabic or Urdu script** (e.g. Urdu digits or Arabic text tokens).
- **Phase 15 Checkpoint Requirement:** The Phase 15 Multilingual Language Registry must explicitly reference this gap. Script-aware NER and multilingual token scrubbing are queued for post-Phase 15 enhancement.
