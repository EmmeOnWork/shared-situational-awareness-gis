"""Read access to the OMI locazione snapshot (``omi_locazione``) — PRD "Lista A".

Lista A is **comune-scoped**: given the comune the click resolved to (a monolith
``region_id``), return every Zona OMI × tipologia × stato of that comune with its
min–max monthly canone. A deep module — the router sees ``find_locazione(region_id)``
and ``current_publication()``; the region-scoped SQL and the shared-DB session live
behind them. Reads only this service's own table (ADR-0001); the comune geography was
resolved elsewhere (``comune_resolver``) and is referenced here by id only.
"""

from dataclasses import dataclass
from typing import List, Optional

from src.config.pgsql_config import get_session_context, text


@dataclass(frozen=True)
class ZonaOmi:
    """One OMI locazione line of the comune's left column: the Zona OMI, the tipologia
    and stato, and the min–max monthly canone with its unit (€/m²/month)."""

    zona: str
    tipologia: str
    stato: str
    canone_min: float
    canone_max: float
    um: str


# The comune's OMI rows, scoped by the bound ``region_id`` (no interpolation) and
# ordered for a stable left-column render. Reads only this service's table.
_ZONE_QUERY = text(
    """
    SELECT zona, tipologia, stato, canone_min, canone_max, um
    FROM public.omi_locazione
    WHERE region_id = :region_id
    ORDER BY zona, tipologia, stato
    """
)

# The snapshot's publication label (latest-only ⇒ one distinct value). NULL/absent
# when nothing has been ingested yet.
_PUBLICATION_QUERY = text(
    """
    SELECT publication
    FROM public.omi_locazione
    LIMIT 1
    """
)


def find_locazione(region_id: int) -> List[ZonaOmi]:
    """Return the comune's OMI locazione rows, ordered for the left column; an empty
    list when the comune has no published OMI."""
    with get_session_context() as session:
        rows = (
            session.execute(_ZONE_QUERY, {"region_id": region_id}).mappings().all()
        )

    return [
        ZonaOmi(
            zona=row["zona"],
            tipologia=row["tipologia"],
            stato=row["stato"],
            canone_min=row["canone_min"],
            canone_max=row["canone_max"],
            um=row["um"],
        )
        for row in rows
    ]


def current_publication() -> Optional[str]:
    """Return the snapshot's OMI publication label (e.g. ``"2025 · II semestre"``), or
    ``None`` when no edition has been ingested yet."""
    with get_session_context() as session:
        row = session.execute(_PUBLICATION_QUERY).mappings().first()
    return row["publication"] if row else None
