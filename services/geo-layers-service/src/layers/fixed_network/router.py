"""Rete fissa < 1 Gb — EGON civic addresses NOT reached by a >=1 Gbit fixed
network, scoped to the clicked comune (:region_id) and returned as a GeoJSON
FeatureCollection of points (rendered as clustered markers).
"""

from fastapi import APIRouter, Query

from src.core.db import COMUNE_BOUNDARY_CTE, get_session_context, text
from src.core.geojson import feature_collection

router = APIRouter(prefix="/geo-layers", tags=["geo-layers"])

# Only civics inside the clicked comune's boundary (the SAME comune the POI layer
# follows, so one map click drives every layer alike). ST_Intersects on the point
# uses the gist index; bound param, no interpolation.
_FEATURES = text(
    COMUNE_BOUNDARY_CTE
    + """
    SELECT fn.comune, fn.strada, fn.civico, ST_AsGeoJSON(fn.geom) AS geojson
    FROM fixed_network_under_1gb fn
    JOIN comune ON ST_Intersects(fn.geom, comune.geom)
    """
)


@router.get("/fixed-under-1gb")
def fixed_under_1gb(
    region_id: int = Query(..., description="Comune (region) id of the clicked map area."),
):
    """Under-1Gb civic addresses for the clicked comune, as a GeoJSON FeatureCollection."""
    with get_session_context() as session:
        rows = session.execute(_FEATURES, {"region_id": region_id}).mappings().all()
    return {"geojson": feature_collection(rows)}
