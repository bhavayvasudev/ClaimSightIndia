"""
Centralized settings via pydantic-settings. Every service module should
read config through `get_settings()` rather than calling `os.environ`
directly — keeps all required env vars documented in one place and
testable (override via `Settings(**overrides)` in tests).
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="development")

    # Claude API
    anthropic_api_key: str = Field(default="")
    claude_model: str = Field(default="claude-opus-4-8")

    # Postgres / pgvector
    database_url: str = Field(
        default="postgresql+psycopg://claimsight:claimsight@localhost:5432/claimsight"
    )

    # Langfuse
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="https://cloud.langfuse.com")

    # Weather API (fraud cross-check)
    weather_api_key: str = Field(default="")

    # File storage
    upload_dir: str = Field(default="./data/uploads")


@lru_cache
def get_settings() -> Settings:
    return Settings()
