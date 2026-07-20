from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service settings.

    This Widget owns no tables and exposes no data route, so it needs **no JWT
    config at all** (it verifies nothing) — only the shared-DB URL used by the
    best-effort catalog self-registration, and the switch that disables it.

    ``DATABASE_URL`` points at the **same Supabase** the monolith reads
    (ADR-0001); it is used solely to upsert this Widget's row into the shared
    ``dashboards_config.widget_types`` catalog on boot.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""

    # Best-effort self-registration into the monolith's shared widget catalog on
    # startup, so this Widget becomes available to hand-curated dashboards without
    # any monolith code change (the catalog is a shared-DB table — ADR-0001).
    # Turn off where the DB role may not write the monolith's schema; the SQL in
    # catalog/widget-type.sql can then be applied by an operator instead.
    register_in_catalog: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
