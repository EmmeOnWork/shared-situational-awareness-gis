from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service settings.

    Auth mirrors the monolith's env var names (``JWT_ALGORITHM``,
    ``JWT_VERIFICATION_KEY``) so the same deployment configuration works, but
    intentionally has **no signing key** — this service never issues tokens
    (ADR-0001: one identity system, the monolith's).

    ``DATABASE_URL`` points at the **same Supabase** the monolith reads
    (ADR-0001); the service connects with SQLAlchemy pooling and sets
    ``search_path`` per session.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_algorithm: str = "RS256"
    jwt_verification_key: str = ""
    database_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
