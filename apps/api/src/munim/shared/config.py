"""Application configuration via Pydantic Settings.

Per docs/conventions.md §9: required env vars MUST have no default. Missing
required values must fail loudly at startup, not at first use.

`get_settings()` is cached so the rest of the app sees one canonical instance;
tests clear the cache after monkeypatching env.
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Phase 1 — sensible defaults.
    database_url: str = "sqlite:///./data/munim.sqlite"
    log_level: str = "info"
    app_env: str = "development"

    # Phase 4 — Shopify OAuth + Admin API. REQUIRED at startup (no defaults).
    shopify_client_id: str
    shopify_client_secret: str
    shopify_api_version: str = "2026-04"
    shopify_oauth_redirect_uri: str
    shopify_default_shop_domain: str  # convenience default for the modal

    # AES-GCM key for encrypting connector_credentials.auth_blob_encrypted.
    # URL-safe base64; must decode to 32 bytes for AES-256-GCM.
    credentials_encryption_key: str

    # Phase 5 — OpenAI. API key required; model/temperature have defaults.
    openai_api_key: str
    openai_chat_model: str = "gpt-4o-mini"
    openai_chat_temperature: float = 0.0

    # Frontend URL used by the OAuth callback redirect.
    frontend_base_url: str = "http://localhost:5173"

    # Phase 9 — anonymous session cookie.
    session_secret: SecretStr
    session_cookie_max_age_days: int = 30
    session_https_only: bool = False

    # Phase 9 — deployed-environment toggle: hide the real Shopify Connect
    # button in the SPA when False; the connector code stays.
    shopify_oauth_enabled: bool = True

    # Phase 9 — when set, FastAPI mounts the SPA dist as static files. None
    # in dev (Vite serves the SPA); set to /app/static in the prod image.
    frontend_dist_path: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
