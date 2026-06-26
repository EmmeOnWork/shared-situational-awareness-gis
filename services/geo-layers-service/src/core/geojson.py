"""Turn DB rows into a GeoJSON FeatureCollection — shared by every layer router.

Each row is a mapping with the feature geometry as a GeoJSON string under
``geom_key`` (produce it with ``ST_AsGeoJSON(geom) AS geojson``); every other
column becomes a feature property. The JuMap layer expects exactly
``{ "geojson": <FeatureCollection> }`` (lowercase key) — the routers wrap it.
"""

import json
from typing import Iterable, Mapping

__all__ = ["feature_collection"]


def feature_collection(rows: Iterable[Mapping], geom_key: str = "geojson") -> dict:
    features = [
        {
            "type": "Feature",
            "geometry": json.loads(row[geom_key]),
            "properties": {k: v for k, v in row.items() if k != geom_key},
        }
        for row in rows
    ]
    return {"type": "FeatureCollection", "features": features}
