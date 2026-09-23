"""Process configuration. Fails fast with an actionable message, never silently."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    llm_timeout_s: float = Field(default=60.0, alias="LLM_TIMEOUT_S")
    llm_max_tokens: int = Field(default=1024, alias="LLM_MAX_TOKENS")

    db_path: Path = Field(default=REPO_ROOT / "data" / "app.db", alias="DB_PATH")
    data_dir: Path = Field(default=REPO_ROOT / "data", alias="DATA_DIR")
    seeds_dir: Path = Field(default=REPO_ROOT / "seeds", alias="SEEDS_DIR")

    embed_model: str = Field(default="BAAI/bge-m3", alias="EMBED_MODEL")
    embed_dim: int = Field(default=1024, alias="EMBED_DIM")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    @property
    def llm_configured(self) -> bool:
        """False means the degraded, key-less path: the app must still start and explain itself."""
        return bool(self.llm_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


class ConfigError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        settings = Settings()
    except ValidationError as exc:  # pragma: no cover - only on malformed env
        raise ConfigError(
            "Invalid configuration. Copy .env.example to .env and fix these fields:\n"
            + "\n".join(f"  - {e['loc'][0]}: {e['msg']}" for e in exc.errors())
        ) from exc
    settings.ensure_dirs()
    return settings
