import logging
from backend.app.core.config.language_registry import LanguageRegistry, LanguageProfile

logger = logging.getLogger(__name__)

class LanguageRouter:
    """
    Tracks the active language per conversation turn.
    Acts as a "shock absorber" to prevent chaotic TTS switching on short blips.
    """
    def __init__(self, registry: LanguageRegistry, default_lang: str = "en"):
        self._registry = registry
        self.current: LanguageProfile = registry.get(default_lang)
        self._default_lang = default_lang
        
        # Debounce tracking
        self._last_detected_lang: str | None = None
        self._consecutive_count: int = 0

    def update(self, detected_code: str | None, word_count: int) -> LanguageProfile:
        """
        Determines the language for the current turn.
        Call this ONLY when transcript.is_final is True.
        """
        # 1. Safety check: If Gladia didn't return a language, keep current state
        if not detected_code:
            return self.current

        # 2. NORMALIZATION (Gemini's great idea): Handle 'en-US' -> 'en'
        base_lang = detected_code.split('-')[0].lower()

        # 3. SUPPORTED CHECK (Gemini's great idea): Ignore unsupported languages entirely
        if not self._registry.has(base_lang):
            return self.current

        is_short_utterance = word_count < 3

        if is_short_utterance:
            # If it's short, require 2 identical detections in a row to switch
            if base_lang == self._last_detected_lang:
                self._consecutive_count += 1
            else:
                self._last_detected_lang = base_lang
                self._consecutive_count = 1
            
            if self._consecutive_count >= 2:
                self.current = self._registry.get(base_lang)
                self._reset_debounce()
                logger.info(f"[Router] Language switched (debounced short utterance) to: {self.current.code}")
        else:
            # If it's a full sentence (3+ words), switch immediately
            if base_lang != self.current.code:
                self.current = self._registry.get(base_lang)
                logger.info(f"[Router] Language switched (long utterance) to: {self.current.code}")
            self._reset_debounce()

        return self.current

    def _reset_debounce(self) -> None:
        self._last_detected_lang = None
        self._consecutive_count = 0