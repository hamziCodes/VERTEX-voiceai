from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Point exactly to the root folder of your project
BASE_DIR = Path(__file__).resolve().parents[4]
ENV_FILE = BASE_DIR / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE), 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    gladia_api_key: str
    gemini_api_key: str
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_max_history: int = 6
    uplift_api_key: str
    uplift_voice_id: str

    log_level: str = "INFO"
    #provide explicit local development URLs 
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:5500,http://localhost:8000"

    # ---- Silero VAD configuration (configurable via .env) ----
    vad_threshold: float = 0.55
    min_speech_duration_ms: int = 250
    min_silence_duration_ms: int = 250
    vad_sample_rate: int = 16000
    vad_window_size_samples: int = 512

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()