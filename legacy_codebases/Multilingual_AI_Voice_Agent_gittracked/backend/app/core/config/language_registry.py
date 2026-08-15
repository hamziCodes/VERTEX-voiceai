import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Optional
import yaml

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class LanguageProfile:
    """
    A strict, in-memory representation of a language configuration.
    Once loaded at startup, this object is immutable (frozen=True) to prevent
    runtime bugs from accidentally modifying the config.
    """
    code: str
    name: str
    script: str
    tts_provider: str
    tts_voice_id: Optional[str]
    llm_directive_file: str
    stt_hint: str
    
    # This is populated by the registry at startup so we don't hit the disk during a conversation
    llm_directive_text: str = ""
    tts_sample_rate: int = 22050

    # Chunking Configuration
    chunk_min_words: int = 5
    chunk_max_words: int = 12
    chunk_primary_delimiters: list[str] = field(default_factory=lambda: [".", "?", "!"])
    chunk_secondary_delimiters: list[str] = field(default_factory=lambda: [",", ";"])

    # VAD Overrides
    vad_silence_duration_ms: Optional[int] = None
    vad_speech_duration_ms: Optional[int] = None
    vad_threshold: Optional[float] = None


class LanguageRegistry:
    """
    Scans the languages/ directory at startup, parses the YAML files,
    reads the corresponding prompt directives, and caches everything.
    
    USAGE IN ORCHESTRATOR (Next Bricks):
        registry = LanguageRegistry()
        ur_profile = registry.get("ur")
        print(ur_profile.tts_provider) # "uplift"
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        # The internal dictionary holding our strategies: {"en": LanguageProfile, "ur": LanguageProfile}
        self._profiles: Dict[str, LanguageProfile] = {}
        self._load_all_languages()
        self._initialized = True

    def _load_all_languages(self) -> None:
        """Finds all .yaml files in the languages/ directory and loads them."""
        # Determine paths relative to THIS file's location
        config_dir = Path(__file__).parent
        languages_dir = config_dir / "languages"
        prompts_dir = config_dir.parent / "prompts"

        if not languages_dir.exists():
            logger.warning("Languages directory not found. No languages loaded.")
            return

        # Iterate through all yaml files in the folder
        for yaml_file in languages_dir.glob("*.yaml"):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                
                if not data or "code" not in data:
                    logger.warning(f"Skipping invalid language file: {yaml_file.name}")
                    continue

                # Read the actual text of the LLM directive from the markdown file
                directive_path = prompts_dir / data.get("llm_directive_file", "")
                directive_text = ""
                if directive_path.exists():
                    with open(directive_path, "r", encoding="utf-8") as df:
                        directive_text = df.read().strip()
                else:
                    logger.warning(f"Directive file not found for {data['code']}: {directive_path}")

                # Create the immutable profile object
                profile = LanguageProfile(
                    code=data["code"],
                    name=data.get("name", data["code"]),
                    script=data.get("script", "latin"),
                    tts_provider=data.get("tts_provider", "uplift"),
                    tts_voice_id=data.get("tts_voice_id"),
                    llm_directive_file=data.get("llm_directive_file", ""),
                    stt_hint=data.get("stt_hint", data["code"]),
                    llm_directive_text=directive_text,
                    tts_sample_rate=data.get("tts_sample_rate", 22050),
                    chunk_min_words=data.get("chunk_min_words", 5),
                    chunk_max_words=data.get("chunk_max_words", 12),
                    chunk_primary_delimiters=data.get("chunk_primary_delimiters", [".", "?", "!"]),
                    chunk_secondary_delimiters=data.get("chunk_secondary_delimiters", [",", ";"]),
                    vad_silence_duration_ms=data.get("vad_silence_duration_ms"),
                    vad_speech_duration_ms=data.get("vad_speech_duration_ms"),
                    vad_threshold=data.get("vad_threshold")
                )

                self._profiles[profile.code] = profile
                logger.info(f"Loaded language profile: {profile.name} ({profile.code}) -> TTS: {profile.tts_provider}")

            except Exception as e:
                logger.error(f"Failed to parse language file {yaml_file.name}: {e}")

        if not self._profiles:
            logger.error("CRITICAL: No languages were loaded! The agent will not function.")

    def get(self, language_code: str) -> LanguageProfile:
        """
        Fetches a language profile by its ISO code (e.g., 'ur', 'en').
        Includes a safe fallback to 'en' if an unsupported language is requested.
        """
        if language_code in self._profiles:
            return self._profiles[language_code]
        
        # Fallback logic: If they speak Arabic but we haven't added it yet, fall back to English
        # rather than crashing the whole pipeline.
        logger.warning(f"Language code '{language_code}' not found in registry. Falling back to 'en'.")
        return self._profiles.get("en", next(iter(self._profiles.values())))

    def has(self, language_code: str) -> bool:
        """Check if a language is supported without triggering the fallback."""
        return language_code in self._profiles

    @property
    def default_language(self) -> str:
        """Returns the primary fallback language code."""
        return "en"