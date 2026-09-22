"""Configuración central. Lee el `.env` de la raíz del repo."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Claude ---
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-5"
    llm_fast_model: str = "claude-haiku-4-5"
    llm_effort: str = "high"

    # --- Embeddings ---
    embedding_provider: str = "local"  # local | voyage
    embedding_dim: int = 512
    voyage_api_key: str = ""
    voyage_model: str = "voyage-3"

    # --- Infra ---
    database_url: str = "postgresql+psycopg://copilot:copilot@localhost:5433/career_copilot"
    redis_url: str = "redis://localhost:6380/0"

    # --- API ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    # Lista separada por comas. pydantic-settings intentaría parsear un list[str]
    # del .env como JSON, así que se lee como texto y se divide aquí.
    cors_origins: str = "http://localhost:3000"
    storage_dir: Path = REPO_ROOT / "backend" / "storage"
    log_level: str = "INFO"

    # --- Usuario local ---
    default_user_email: str = "me@localhost"
    default_user_name: str = "Yo"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @field_validator("embedding_dim")
    @classmethod
    def _dim_positive(cls, v: int) -> int:
        if v < 32:
            raise ValueError("EMBEDDING_DIM debe ser >= 32")
        return v

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.storage_dir.mkdir(parents=True, exist_ok=True)
    return s


settings = get_settings()
