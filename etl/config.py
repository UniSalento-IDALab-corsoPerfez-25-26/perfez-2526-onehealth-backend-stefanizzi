from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    arpa_base_url: str = "https://cloud.arpa.puglia.it/QualitaAria"
    arpa_timeout_seconds: float = 120.0
    arpa_max_retries: int = 3
    arpa_raw_dir: Path = Path("data/raw")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
