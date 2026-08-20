# UCVE Workflow: Adding a New Language

To add support for a new language in the UCVE platform, complete the following 4 required steps:

1. **Step 1: Create YAML Language Profile**
   - Add `<code >.yaml` in `core/language/profiles/` specifying `code`, `script_direction`, `vad_silence_override_ms`, `tts_voice_id`, `code_switching_default`, and `redaction_script_coverage`.

2. **Step 2: Phase 06 Capability & Provider Registry Entry**
   - Register STT and TTS provider capability mappings in `core/providers/registry.py` for the target language code.

3. **Step 3: Add Router Test Fixture**
   - Add language router test cases in `tests/fixtures/language_router/` to verify code-switching and switch thresholds.

4. **Step 4: RTL Voice Validation Gate**
   - If `script_direction: rtl`, ensure the designated TTS voice ID passes `RTLVoiceValidator.validate_voice_for_publish()`.
