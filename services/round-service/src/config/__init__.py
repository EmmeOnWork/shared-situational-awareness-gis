from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service settings.

    Auth mirrors the monolith's env var names (``JWT_ALGORITHM``,
    ``JWT_VERIFICATION_KEY``) so the same deployment configuration works, but
    intentionally has **no signing key** — this service never issues tokens
    (system ADR-0001: one identity system, the monolith's).

    ``DATABASE_URL`` points at the **same Supabase** the monolith reads
    (ADR-0001). This is the first Widget to own write state: participants,
    rounds and votes live in-memory per room, and each closed Round's outcome
    is persisted to ``public.round_outcomes`` (schema + grant via the
    ``round-schema-init`` one-shot — see ``db/round-schema.sql``). The DB is
    also used for best-effort catalog self-registration on boot.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_algorithm: str = "RS256"
    jwt_verification_key: str = ""
    database_url: str = ""

    # Best-effort self-registration into the monolith's shared widget catalog on
    # startup, so this Widget becomes available to hand-curated dashboards without
    # any monolith code change (the catalog is a shared-DB table — ADR-0001).
    # Turn off where the DB role may not write the monolith's schema; the SQL in
    # catalog/widget-type.sql can then be applied by an operator instead.
    register_in_catalog: bool = True

    # The Realtime Notifier's publish ingress: the Round Manager is the backend
    # producer that POSTs the shared lifecycle moments (round opened/closed,
    # consensus reached) here, each Bene-scoped (CONTEXT.md). Defaults to the
    # in-cluster service address (the gateway is not on the publish path — this is
    # server-to-server). Publishing is best-effort: a Notifier hiccup never breaks a
    # live Round.
    notifier_publish_url: str = "http://notification-service:28004/notifications/publish"


@lru_cache
def get_settings() -> Settings:
    return Settings()
