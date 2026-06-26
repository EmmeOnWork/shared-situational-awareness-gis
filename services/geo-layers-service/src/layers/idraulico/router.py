"""Pericolosità idraulica (ISPRA) — polygon FeatureCollection, colour by level,
clipped to the clicked comune (:region_id).

Three scenarios share one table. As with frana, the route clips to the selected
comune's boundary and **dissolves to one MultiPolygon per level** so the JuMap SVG
renderer draws a few paths, all inside the clicked zone. The raw ISPRA `scenario`
string is normalised to `livello` (bassa/media/elevata), the key `colorCases`
matches; `ST_CollectionExtract(…, 3)` keeps only the polygonal part of each clip.
"""

from fastapi import APIRouter, Query

from src.core.db import COMUNE_BOUNDARY_CTE, get_session_context, text
from src.core.geojson import feature_collection

router = APIRouter(prefix="/geo-layers", tags=["geo-layers"])

_FEATURES = text(
    COMUNE_BOUNDARY_CTE
    + """
    SELECT livello, ST_AsGeoJSON(ST_Collect(poly), 5) AS geojson
    FROM (
        SELECT CASE
                   WHEN scenario ILIKE '%elevata%' THEN 'elevata'
                   WHEN scenario ILIKE '%media%'   THEN 'media'
                   ELSE 'bassa'
               END AS livello,
               (ST_Dump(ST_SimplifyPreserveTopology(
                   ST_CollectionExtract(ST_Intersection(i.geom, comune.geom), 3), 0.0003))).geom AS poly
        FROM idraulico_pericolosita i
        JOIN comune ON ST_Intersects(i.geom, comune.geom)
    ) t
    GROUP BY livello
    """
)


@router.get("/idraulico")
def idraulico(
    region_id: int = Query(..., description="Comune (region) id of the clicked map area."),
):
    """Aree di pericolosità idraulica nel comune cliccato, one feature per level."""
    with get_session_context() as session:
        rows = session.execute(_FEATURES, {"region_id": region_id}).mappings().all()
    return {"geojson": feature_collection(rows)}
