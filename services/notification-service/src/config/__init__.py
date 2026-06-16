from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service settings.

    The Notifier owns no tables and exposes no guarded *data* route, but its
    WebSocket handshake verifies the monolith JWT (ADR-0002). Auth mirrors the
    monolith's env var names (``JWT_ALGORITHM``, ``JWT_VERIFICATION_KEY``) so the
    same deployment configuration works, but intentionally has **no signing key** —
    this service never issues tokens (ADR-0001: one identity system, the
    monolith's).

    ``DATABASE_URL`` points at the **same Supabase** the monolith reads
    (ADR-0001); it is used solely to upsert this Widget's row into the shared
    ``dashboards_config.widget_types`` catalog on boot.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_algorithm: str = "RS256"
    jwt_verification_key: str = ""
    database_url: str = ""

    # Best-effort self-registration into the monolith's shared widget catalog on
    # startup, so this Widget appears to the dashboard without any monolith code
    # change (the catalog is a shared-DB table — ADR-0001). Turn off where the DB
    # role may not write the monolith's schema; catalog/widget-type.sql can then
    # be applied by an operator instead.
    register_in_catalog: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
