from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Point exactly to the root folder of your project
BASE_DIR = Path(__file__).resolve().parents[4]
ENV_FILE = BASE_DIR / ".env"
ENV_LOCAL_FILE = BASE_DIR / ".env.local"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ENV_FILE), str(ENV_LOCAL_FILE)), 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    gladia_api_key: str
    groq_api_key: str
    groq_model: str = "llama-3.1-8b-instant"
    groq_max_history: int = 6
    uplift_api_key: str
    uplift_voice_id: str
    elevenlabs_api_key: str = "" 
    google_tts_api_key: str = ""
    azure_api_key: str = ""
    azure_region: str = ""

    # VAD Configuration
    vad_threshold: float = 0.5
    vad_speech_duration_ms: int = 250  # 250ms voice onset check
    vad_silence_ui_ms: int = 200       # <=200ms silence for UI filler trigger
    vad_silence_commit_ms: int = 600   # >=600ms silence for turn commit
    vad_energy_threshold: float = 0.015
    vad_noise_gate_k: float = 3.0
    vad_noise_gate_window: int = 50

    clerk_publishable_key: str = ""
    clerk_secret_key: str = ""

    log_level: str = "INFO"
    cors_origins: str 

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()