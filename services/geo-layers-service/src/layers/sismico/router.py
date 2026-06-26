"""Rischio sismico — the clicked comune coloured by its seismic zone (ZONA_SISMICA).

Geometry is the clicked comune's Administrative-Boundary polygon from public.areas
(the SAME boundary the POI/Confine layers use); the zone comes from seismic_zone
(the in-repo ISTAT CSV, one row per comune) joined on the area's ISTAT code,
`metadata->>'ref:ISTAT'`. So the layer needs no separate comuni-boundary import — it
renders for exactly the comuni you can click. `zona` (1/2/3/3S/4) is the key the
JuMap layer's `colorCases` matches.
"""

from fastapi import APIRouter, Query

from src.core.db import get_session_context, text
from src.core.geojson import feature_collection

router = APIRouter(prefix="/geo-layers", tags=["geo-layers"])

# seismic_zone.cod_istat is an int (leading zero dropped, e.g. 64015); the area's
# metadata->>'ref:ISTAT' is the 6-char string '064015'. lpad to match as text — no
# cast, so a missing/odd metadata value just fails to join rather than erroring.
_FEATURES = text(
    """
    SELECT a.name AS comune, z.zona, ST_AsGeoJSON(a.geom, 6) AS geojson
    FROM regions r
    JOIN region_areas ra ON ra.region_id = r.id
    JOIN areas a ON ra.area_id = a.id AND a.area_type_id = 3
    JOIN seismic_zone z ON lpad(z.cod_istat::text, 6, '0') = a.metadata->>'ref:ISTAT'
    WHERE r.id = :region_id
    """
)


@router.get("/sismico")
def sismico(
    region_id: int = Query(..., description="Comune (region) id of the clicked map area."),
):
    """Classificazione sismica del comune cliccato, as a GeoJSON FeatureCollection."""
    with get_session_context() as session:
        rows = session.execute(_FEATURES, {"region_id": region_id}).mappings().all()
    return {"geojson": feature_collection(rows)}
