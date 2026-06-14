"""Boot-time ensure of the ``building_workshop`` registry this service owns.

``reuse-service`` is the **curator** of the Bene list: it owns
``public.building_workshop`` — the canonical set of reuse-POIs, keyed by
``poi_id`` (ADR-0001, CONTEXT). A Bene exists in this table even before it has a
Scheda or Blueprints; ``characteristics-service`` later reads/FKs to it.

Ensuring the table exists on boot is **best-effort**, the same pattern as the
catalog registration (``IF NOT EXISTS``, never fatal): the tiny Widget service
usually wins the boot race, and an operator can apply ``catalog/registry.sql``
instead. The Bene rows themselves are seeded separately (``catalog/seed-benes.sql``);
designating Bene via an admin UI is out of scope for v1.
"""

import logging

from src.config.pgsql_config import get_session_context, text

logger = logging.getLogger(__name__)

# The registry of reuse-POIs (Bene), keyed by the monolith's POI id. Referenced
# by ``poi_id`` value only — **no cross-domain FK** to ``pois`` (the monolith owns
# and re-syncs POIs; a FK would couple our migrations to theirs). ``master_user_id``
# (the Workshop Master) is anticipated but not modelled in v1.
_ENSURE_REGISTRY = text(
    """
    CREATE TABLE IF NOT EXISTS public.building_workshop (
        poi_id     bigint PRIMARY KEY,
        created_at timestamptz NOT NULL DEFAULT now()
    );
    """
)


def ensure_workshop_registry() -> bool:
    """Best-effort create of ``public.building_workshop``. Never raises.

    Returns True on success, False if it was skipped or failed (logged) — the
    service still serves ``/reuse/benes`` (which simply returns ``[]`` when the
    table is empty or, here, briefly absent).
    """
    try:
        with get_session_context() as session:
            session.execute(_ENSURE_REGISTRY)
            session.commit()
        logger.info("building_workshop registry ensured")
        return True
    except Exception as exc:  # noqa: BLE001 — ensure is best-effort
        logger.warning(
            "building_workshop ensure skipped (%s); apply catalog/registry.sql "
            "manually",
            exc,
        )
        return False
