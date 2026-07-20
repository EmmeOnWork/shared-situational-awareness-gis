from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service settings.

    Auth mirrors the monolith's env var names (``JWT_ALGORITHM``,
    ``JWT_VERIFICATION_KEY``) so the same deployment configuration works, but
    intentionally has **no signing key** — this service never issues tokens
    (system ADR-0001: one identity system, the monolith's). The copied JWT verify
    (src/security) guards the two data routes ``/prezzari/locazione`` and
    ``/prezzari/lavori`` (auth-only, no scope — any logged-in user may consult
    these public reference lists).

    ``DATABASE_URL`` points at the **same shared DB** the monolith reads (ADR-0001).
    I Prezziari owns two snapshot tables (`omi_locazione`, `prezzario_voci`),
    populated by offline ingest scripts (`db/`); the DB is also touched for
    best-effort catalog self-registration on boot. There is **no external
    provider, no refresh worker and no runtime egress** (prezzari ADR-0001).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_algorithm: str = "RS256"
    jwt_verification_key: str = ""
    database_url: str = ""

    # Best-effort self-registration into the monolith's shared widget catalog on
    # startup, so I Prezziari becomes available to hand-curated dashboards without any
    # monolith code change (the catalog is a shared-DB table — ADR-0001). Turn off
    # where the DB role may not write the monolith's schema; the SQL in
    # catalog/widget-type.sql can then be applied by an operator.
    register_in_catalog: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
