"""Pericolosità da frana (ISPRA PAI) — polygon FeatureCollection, colour by class,
clipped to the clicked comune (:region_id).

The table holds many small Campania polygons. The route clips them to the selected
comune's boundary and **dissolves to one MultiPolygon per hazard class**
(`ST_Intersection` → `ST_SimplifyPreserveTopology` → `ST_Dump` → `ST_Collect` per
class): a few SVG paths, all inside the clicked zone. `classe` (AA, P1..P4 — the
trailing token of the ISPRA label) is the key the JuMap layer's `colorCases` matches.
`ST_CollectionExtract(…, 3)` keeps only the polygonal part of each clip (a boundary
touch can yield lines/points), so `ST_Collect` never mixes geometry types.
"""

from fastapi import APIRouter, Query

from src.core.db import COMUNE_BOUNDARY_CTE, get_session_context, text
from src.core.geojson import feature_collection

router = APIRouter(prefix="/geo-layers", tags=["geo-layers"])

_FEATURES = text(
    COMUNE_BOUNDARY_CTE
    + """
    SELECT classe, ST_AsGeoJSON(ST_Collect(poly), 5) AS geojson
    FROM (
        SELECT split_part(per_fr_ita, ' ', -1) AS classe,
               (ST_Dump(ST_SimplifyPreserveTopology(
                   ST_CollectionExtract(ST_Intersection(f.geom, comune.geom), 3), 0.0003))).geom AS poly
        FROM frana_pericolosita f
        JOIN comune ON ST_Intersects(f.geom, comune.geom)
    ) t
    GROUP BY classe
    """
)


@router.get("/frana")
def frana(
    region_id: int = Query(..., description="Comune (region) id of the clicked map area."),
):
    """Aree di pericolosità da frana nel comune cliccato, one feature per class."""
    with get_session_context() as session:
        rows = session.execute(_FEATURES, {"region_id": region_id}).mappings().all()
    return {"geojson": feature_collection(rows)}
