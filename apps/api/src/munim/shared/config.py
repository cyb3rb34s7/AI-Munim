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

    # Phase 1 - all optional with sensible defaults.
    database_url: str = "sqlite:///./data/munim.sqlite"
    log_level: str = "info"
    app_env: str = "development"

    # Phase 2+ will add fields WITHOUT defaults for OPENAI_API_KEY, ANTHROPIC_API_KEY,
    # SHOPIFY_CLIENT_ID/SECRET, META_APP_ID/SECRET, SHIPROCKET_*, CREDENTIALS_ENCRYPTION_KEY.


@lru_cache
def get_settings() -> Settings:
    return Settings()
