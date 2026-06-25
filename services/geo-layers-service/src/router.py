"""Map-layer data routes.

`fixed-under-1gb` serves the authoritative EGON civic addresses NOT reached by a
>=1 Gbit fixed network, as a GeoJSON FeatureCollection of points. The JuMap layer
renders them as clustered markers; `getLayerWrapper` expects exactly
`{ "geojson": <FeatureCollection> }` (lowercase key).
"""

from fastapi import APIRouter, Query

from src.db import get_session_context, text

geo_layers_router = APIRouter(prefix="/geo-layers", tags=["geo-layers"])

# Name-filtered, bound param (no interpolation). lon/lat pulled from the geometry
# so the row carries no separate coordinate columns.
_FEATURES = text(
    """
    SELECT comune, strada, civico, ST_X(geom) AS lon, ST_Y(geom) AS lat
    FROM fixed_network_under_1gb
    WHERE regione = :region
    """
)


@geo_layers_router.get("/fixed-under-1gb")
def fixed_under_1gb(
    region: str = Query("CAMPANIA", description="ISTAT region name (upper-case), e.g. CAMPANIA."),
):
    """Under-1Gb civic addresses for a region, as a GeoJSON FeatureCollection."""
    with get_session_context() as session:
        rows = session.execute(_FEATURES, {"region": region.upper()}).mappings().all()

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
            "properties": {
                "comune": row["comune"],
                "strada": row["strada"],
                "civico": row["civico"],
            },
        }
        for row in rows
    ]
    return {"geojson": {"type": "FeatureCollection", "features": features}}


@geo_layers_router.get("/ping")
def ping():
    """Auth-and-reachability smoke behind the gateway (no DB)."""
    return {"status": "ok"}
