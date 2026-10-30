from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

# appended after any configured chain, so a stale .env can't leave a role with no live model
DEFAULT_CHAT_MODELS = ("openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b")
DEFAULT_VISION_MODELS = ("qwen/qwen3.8-27b", "meta-llama/llama-4-scout-17b-16e-instruct")


def _chain(configured: str, defaults: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for m in [*configured.split(","), *defaults]:
        m = m.strip()
        if m and m not in out:
            out.append(m)
    return out


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / "backend" / ".env", extra="ignore")

    env: str = "local"
    data_dir: Path = ROOT / "data"
    # empty -> local SQLite files under backend/
    database_url: str = ""
    cors_origins: str = "http://localhost:5173"

    groq_api_key: str = ""
    groq_chat_models: str = ",".join(DEFAULT_CHAT_MODELS)
    groq_vision_models: str = ",".join(DEFAULT_VISION_MODELS)
    groq_guard_model: str = "meta-llama/llama-prompt-guard-2-86m"
    groq_stt_model: str = "whisper-large-v3-turbo"
    llm_timeout_s: float = 20.0

    # "today" for date checks, per the dataset README
    reference_date: str = "2026-07-15"
    address_proof_max_age_days: int = 90
    demo_mode: bool = True
    backoffice_key: str = "demo"
    # local RapidOCR fallback peaks near 500 MB; switch off on 512 MB instances
    local_ocr: bool = True

    @property
    def ocr_enabled(self) -> bool:
        """LOCAL_OCR is on and the optional OCR packages (requirements-ocr.txt) are installed."""
        import importlib.util

        return self.local_ocr and importlib.util.find_spec("rapidocr") is not None

    @property
    def chat_models(self) -> list[str]:
        return _chain(self.groq_chat_models, DEFAULT_CHAT_MODELS)

    @property
    def vision_models(self) -> list[str]:
        return _chain(self.groq_vision_models, DEFAULT_VISION_MODELS)

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
