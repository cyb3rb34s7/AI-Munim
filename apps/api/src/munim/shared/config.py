"""Application configuration via Pydantic Settings.

Per docs/conventions.md §9: required env vars MUST have no default. Missing
required values must fail loudly at startup, not at first use.

`get_settings()` is cached so the rest of the app sees one canonical instance;
tests clear the cache after monkeypatching env.
"""

from functools import lru_cache

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

    # Frontend URL used by the OAuth callback redirect.
    frontend_base_url: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
