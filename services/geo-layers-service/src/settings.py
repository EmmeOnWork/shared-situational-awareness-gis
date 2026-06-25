from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service settings.

    Verifies the monolith's JWT (it never issues one — ADR-0001, one identity
    system) and reads the same local postgres the monolith uses. The defaults are
    the local-dev values the compose injects, so a no-env run already works.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_algorithm: str = "HS256"
    jwt_verification_key: str = "CHANGE_ME"
    database_url: str = "postgresql+psycopg://janus:CHANGE_ME@ju-postgres:5432/janus"


@lru_cache
def get_settings() -> Settings:
    return Settings()
