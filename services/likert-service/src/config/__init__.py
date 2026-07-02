from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service settings.

    Auth mirrors the monolith's env var names (``JWT_ALGORITHM``,
    ``JWT_VERIFICATION_KEY``) so the same deployment configuration works, but
    intentionally has **no signing key** — this service never issues tokens
    (system ADR-0001: one identity system, the monolith's). The copied JWT verify
    (src/security) guards the single data route ``/likert/gradimento``.

    ``DATABASE_URL`` points at the **same Supabase** the monolith reads (ADR-0001).
    The Scala Likert will own a small ratings cache (later slices); in this tracer
    slice the DB is touched only for best-effort catalog self-registration on boot.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_algorithm: str = "RS256"
    jwt_verification_key: str = ""
    database_url: str = ""

    # Best-effort self-registration into the monolith's shared widget catalog on
    # startup, so the Scala Likert appears in the dashboard "Add widget" menu
    # without any monolith code change (the catalog is a shared-DB table —
    # ADR-0001). Turn off where the DB role may not write the monolith's schema;
    # the SQL in catalog/widget-type.sql can then be applied by an operator.
    register_in_catalog: bool = True

    # --- Google identity matching (task 05) -------------------------------
    # The Place Search/Details API key. The refresh worker (and the resolve step
    # it seeds) call Google server-side; the widget never does. Empty in tests —
    # the matcher is pure and the client is mocked, so no live call is made.
    google_api_key: str = ""

    # The "exclude on no confident match" guardrail thresholds (ADR-0001): a
    # candidate must be within ``match_max_distance_m`` metres AND at least
    # ``match_min_name_similarity`` [0,1] similar by name to be accepted; otherwise
    # the POI is recorded ``no_match`` rather than mis-paired. Tunable per PRD.
    match_max_distance_m: float = 150.0
    match_min_name_similarity: float = 0.6

    # --- Background refresh worker (task 06) -------------------------------
    # The cache TTL (days): a place whose rating was fetched more than this ago is
    # refreshed; one fetched more recently is left alone. Capped at the ToS ceiling
    # of 30 (ADR-0001). The monthly call-budget is the most Place Details refreshes
    # the worker performs in one pass — the hard cost guardrail; a place left out
    # this period is picked up next. Both tunable per PRD.
    ttl_days: int = 30
    monthly_budget: int = 10000


@lru_cache
def get_settings() -> Settings:
    return Settings()
