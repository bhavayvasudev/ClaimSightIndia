"""
Centralized settings via pydantic-settings. Every service module should
read config through `get_settings()` rather than calling `os.environ`
directly — keeps all required env vars documented in one place and
testable (override via `Settings(**overrides)` in tests).
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ — the directory containing app/. Used to anchor relative
# storage paths so persisted files (policy uploads, vehicle reference
# images) land in the same place regardless of the process's CWD.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent


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

    # Reference vehicle images resolved by
    # app/services/vehicle_reference.py: downloaded once, validated, and
    # stored here, then served from the backend's own /vehicle-images/
    # route — never hotlinked from a third-party host by the frontend.
    vehicle_image_dir: str = Field(default="./data/vehicle_images")

    # User-uploaded profile avatars (app/api/routes/users.py), stored with
    # server-generated content-addressed names and served from the public
    # /avatars/ route. Only avatar objects ever land here — claim damage
    # photos and policy documents live under upload_dir and stay private.
    avatar_dir: str = Field(default="./data/avatars")
    # Master switch for the Wikimedia lookup tier. Tests disable it so no
    # unit/integration test ever performs a live network call.
    vehicle_image_remote_lookup_enabled: bool = Field(default=True)

    # ai-service (YOLO car-parts + damage-segmentation pipeline). Never
    # hardcode this elsewhere — services/ai_client.py is the only caller.
    ai_service_url: str = Field(default="http://localhost:8500")
    ai_service_timeout_seconds: float = Field(default=30.0)

    # Browser origins allowed to call this API directly (comma-separated).
    # Default covers the Next.js dev server only — widen via env var for
    # other environments, never hardcode "*" here.
    cors_allowed_origins: str = Field(default="http://localhost:3000")

    # Must match the frontend's AUTH_GOOGLE_ID (the OAuth client id Google
    # issued the ID token's `aud` claim for) — see app/core/google_oidc.py.
    auth_google_client_id: str = Field(default="")
    google_jwks_url: str = Field(default="https://www.googleapis.com/oauth2/v3/certs")

    # Backend-issued access tokens (app/core/security.py). Signed with this
    # app's own secret, never Google's — the frontend only ever carries this
    # token, it never verifies or mints one itself.
    backend_jwt_secret: str = Field(default="")
    backend_jwt_issuer: str = Field(default="claimsight-backend")
    backend_jwt_audience: str = Field(default="claimsight-frontend")
    backend_jwt_ttl_seconds: int = Field(default=43200)  # 12h

    # slowapi/limits storage backend (app/core/rate_limit.py). "memory://"
    # is per-process — correct for local dev or a single instance only.
    # Point this at a Redis-compatible URI (e.g. "redis://redis:6379") for
    # any multi-instance deployment, or each instance enforces its own
    # independent limit and the effective limit multiplies by instance count.
    rate_limit_storage_uri: str = Field(default="memory://")

    # Optional shared secret attached as `X-Internal-Service-Token` on every
    # backend -> ai-service call (see app/services/ai_client.py). Leave unset
    # for local dev. In production, prefer keeping the ai-service on a
    # private network unreachable from outside; set this in addition if it
    # is ever reachable from a wider network than the backend.
    ai_service_shared_secret: str = Field(default="")

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _anchor_storage_paths(self) -> "Settings":
        """User-visible persistent assets must never depend on the CWD the
        server happened to start from — a restart from a different
        directory would otherwise silently 'lose' previously stored
        files. Absolute paths (e.g. from tests or deployment env) pass
        through untouched."""
        for field in ("upload_dir", "vehicle_image_dir", "avatar_dir"):
            value = Path(getattr(self, field))
            if not value.is_absolute():
                setattr(self, field, str((_BACKEND_ROOT / value).resolve()))
        return self

    @model_validator(mode="after")
    def _require_secrets_in_production(self) -> "Settings":
        if self.environment == "production":
            missing = [
                name
                for name, value in (
                    ("backend_jwt_secret", self.backend_jwt_secret),
                    ("auth_google_client_id", self.auth_google_client_id),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    f"Missing required production settings: {', '.join(missing)}"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
