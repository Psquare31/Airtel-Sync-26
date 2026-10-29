from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / "backend" / ".env", extra="ignore")

    env: str = "local"
    data_dir: Path = ROOT / "data"
    # empty -> local SQLite files under backend/
    database_url: str = ""
    cors_origins: str = "http://localhost:5173"

    groq_api_key: str = ""
    groq_chat_models: str = "openai/gpt-oss-120b,qwen/qwen3-32b,llama-3.3-70b-versatile,openai/gpt-oss-20b"
    groq_vision_models: str = "meta-llama/llama-4-scout-17b-16e-instruct,meta-llama/llama-4-maverick-17b-128e-instruct"
    groq_guard_model: str = "meta-llama/llama-prompt-guard-2-86m"
    groq_stt_model: str = "whisper-large-v3-turbo"
    llm_timeout_s: float = 20.0

    # "today" for date checks, per the dataset README
    reference_date: str = "2026-07-15"
    address_proof_max_age_days: int = 90
    demo_mode: bool = True
    backoffice_key: str = "demo"

    @property
    def chat_models(self) -> list[str]:
        return [m.strip() for m in self.groq_chat_models.split(",") if m.strip()]

    @property
    def vision_models(self) -> list[str]:
        return [m.strip() for m in self.groq_vision_models.split(",") if m.strip()]

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        if not self.database_url:
            return f"sqlite:///{ROOT / 'backend' / 'app.db'}"
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    @property
    def postgres_conninfo(self) -> str:
        return self.database_url.replace("postgresql+psycopg://", "postgresql://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
