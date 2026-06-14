from collections.abc import Iterable, Mapping

from fastapi import APIRouter
from pydantic import BaseModel

from src.config.pgsql_config import get_session_context, text

benes_router = APIRouter(prefix="/reuse", tags=["reuse"])


class Bene(BaseModel):
    """One reuse-POI in the toggle-list: its POI id plus the POI's name and
    coordinates. The shape is the Active Workshop contract (ADR-0003): selecting
    a Bene publishes exactly this ``{poiId, lat, lng, name}`` on the bus.
    """

    poiId: int
    name: str
    lat: float
    lng: float


def build_bene_list(rows: Iterable[Mapping]) -> list[Bene]:
    """Map ``building_workshop`` ⋈ ``pois`` rows to the toggle-list shape.

    Pure: mappings in, ``Bene`` objects out — no HTTP, no DB. Order is preserved,
    so the caller's SQL ``ORDER BY`` defines the result order. A Bene whose POI
    row is missing (LEFT JOIN ⇒ null name/coords) is **omitted**: it cannot be
    named, panned to, or published as an Active Workshop, so it is noise here.
    """
    return [
        Bene(
            poiId=row["poi_id"],
            name=row["name"],
            lat=row["lat"],
            lng=row["lng"],
        )
        for row in rows
        if row["name"] is not None and row["lat"] is not None and row["lng"] is not None
    ]


# The Bene toggle-list: the registry we own (building_workshop) carried by each
# POI's name + coords. LEFT JOIN (not INNER) so the query still returns a Bene
# whose POI is momentarily un-joinable — the builder then omits it, keeping the
# decision to drop nameless entries in one pure, tested place. The POI is read
# **by poi_id only**, never written, no cross-domain FK (ADR-0001). Coordinates
# come from the POI geometry: ST_Y(geom) = lat, ST_X(geom) = lng. Name-ordered,
# nulls last, so unresolved Bene sort to the end before being dropped.
BENES_QUERY = text(
    """
    SELECT w.poi_id      AS poi_id,
           p.name        AS name,
           ST_Y(p.geom)  AS lat,
           ST_X(p.geom)  AS lng
    FROM building_workshop w
    LEFT JOIN pois p ON p.id = w.poi_id
    ORDER BY p.name NULLS LAST
    """
)


@benes_router.get("/benes", response_model=list[Bene])
def list_benes():
    """List every Bene for the toggle-list as ``{poiId, name, lat, lng}``.

    Returns ``[]`` cleanly when the registry is empty, and omits any Bene whose
    POI row is missing (handled in :func:`build_bene_list`). JWT-guarded at the
    router level by the ``reuse:read`` scope (see ``src/app.py``)."""
    with get_session_context() as session:
        rows = session.execute(BENES_QUERY).mappings().all()

    return build_bene_list(rows)
