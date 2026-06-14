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
    ``search_path`` per session. Unlike the read-only demographic service this one
    issues DML, so its DB role must hold INSERT/UPDATE/DELETE on the ``building_*``
    tables (granted by the ``characteristic-schema-init`` one-shot).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_algorithm: str = "RS256"
    jwt_verification_key: str = ""
    database_url: str = ""

    # Blueprint upload size cap (bytes). Oversized uploads are rejected before any
    # bytes are decoded (a cheap pre-decode DoS guard). Default 10 MiB; override via
    # env for tuning.
    max_blueprint_bytes: int = 10 * 1024 * 1024

    # FINALISED size cap for a *stored* Blueprint (slice 5). The image-processor
    # downscales until the re-encoded bytes fit under this, so storage stays bounded
    # below the input cap above regardless of the uploaded resolution. Default 5 MiB.
    finalised_blueprint_bytes: int = 5 * 1024 * 1024

    # Longest-edge pixel cap for a stored Blueprint (slice 5). Oversized plans are
    # downscaled to this with LANCZOS resampling, which preserves the thin black
    # lines of engineering drawings rather than blurring them away. Generous (2400px)
    # so dense plans stay legible while phone-photo resolution is trimmed.
    max_blueprint_dimension: int = 2400

    # Best-effort self-registration into the monolith's shared widget catalog on
    # startup, so this Widget appears in the dashboard "Add widget" menu without
    # any monolith code change (the catalog is a shared-DB table — ADR-0001).
    # Turn off where the DB role may not write the monolith's schema; the SQL in
    # catalog/widget-type.sql can then be applied by an operator instead.
    register_in_catalog: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
