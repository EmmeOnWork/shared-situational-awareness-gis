"""Resolve a clicked point to its **comune** by point-in-polygon on shared ``areas``.

The host forwards a map click as plain ``lat``/``lng``; the Prezziario di Locazione
(Lista A) is keyed per **comune** (a monolith **region**, ``area_type_id = 3``). This
module turns the point into that comune, mirroring the monolith's
``GET /areas/at-point`` — the SAME ``regions → region_areas → areas[type 3]`` join and
``ST_Contains`` test — but **copied, not imported** (ADR-0001 shared DB, referenced by
id/name only; the monolith is never modified to forward ``region_id``). Copied verbatim
from likert's ``comune_resolver``.

A deep module: the router sees one call, ``resolve_comune(lat, lng) -> Comune | None``;
the spatial query and the shared-DB session live entirely behind it.
"""

from dataclasses import dataclass
from typing import Optional

from src.config.pgsql_config import get_session_context, text


@dataclass(frozen=True)
class Comune:
    """The administrative comune the left list is keyed to: the monolith region id
    (referenced by id only) and its display name (shown in the left column header)."""

    region_id: int
    name: str


# Point-in-polygon against the shared ``areas`` table: the comune (region,
# ``area_type_id = 3``) whose Administrative Boundary contains the click. Bound
# params only (no interpolation); ``ST_Point`` takes (lng, lat) — x then y. Copy
# of the monolith's ``/areas/at-point`` query, kept read-only here.
COMUNE_AT_POINT_QUERY = text(
    """
    SELECT r.id AS region_id, r.name AS name
    FROM regions r
    JOIN region_areas ra ON ra.region_id = r.id
    JOIN areas a ON ra.area_id = a.id
    WHERE a.area_type_id = 3
      AND ST_Contains(a.geom, ST_SetSRID(ST_Point(:lng, :lat), 4326))
    LIMIT 1
    """
)


def resolve_comune(lat: float, lng: float) -> Optional[Comune]:
    """Resolve ``(lat, lng)`` to the comune that contains it, or ``None`` when the
    point falls outside every comune boundary (e.g. a click in the sea, or a click
    outside Campania)."""
    with get_session_context() as session:
        row = (
            session.execute(COMUNE_AT_POINT_QUERY, {"lat": lat, "lng": lng})
            .mappings()
            .first()
        )

    if row is None:
        return None
    return Comune(region_id=row["region_id"], name=row["name"])
