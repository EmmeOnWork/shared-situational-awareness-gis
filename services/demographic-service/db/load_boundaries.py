#!/usr/bin/env python3
"""One-off loader for province boundary polygons → public.demographic_boundary.

The demographic data is geometry-free; this sidecar table holds ONE polygon per
province so /demographics/at-point can resolve a map click (a lat/lng) to the
province that contains it. See ../db/README.md and demographic-schema.sql.

Self-contained on purpose: stdlib + psycopg (already in the service image), no
import of the app, so it runs the same way in the container or a local venv. It
reconciles each polygon's name to the EXACT `territory_name` key already in
public.demographic (the boundary table FK-references it), applies a small
OVERRIDES map for the handful of ISTAT spellings that differ, and reports any
polygon it could not match so the operator can extend OVERRIDES and re-run.

Input: an ISTAT province boundary GeoJSON FeatureCollection (EPSG:4326), e.g. the
"Confini delle unità amministrative — Province/UTS" export. The province name is
read from a feature property (default `DEN_UTS`; override with --name-field).

Usage (inside the running stack — the service container has psycopg):

    docker compose cp services/demographic-service/db/load_boundaries.py \
        demographic-service:/tmp/load_boundaries.py
    docker compose cp provinces.geojson demographic-service:/tmp/provinces.geojson
    docker compose exec demographic-service \
        python /tmp/load_boundaries.py /tmp/provinces.geojson --name-field DEN_UTS

Idempotent: upserts by territory_name, so re-running refreshes geometries.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg

# Province name spellings that differ from the demographic table's territory_name.
# Verified against the openpolis provinces GeoJSON (prov_name): only Bolzano
# differs. "Valle d'Aosta/Vallée d'Aoste" has no province row (Aosta is region
# level in the demographic data) and is correctly left unmatched/reported.
# Extend this when a run reports an unmatched name for a different source file.
OVERRIDES: dict[str, str] = {
    "Bolzano/Bozen": "Bolzano-Bozen",
}


def _dsn() -> str:
    """psycopg3 DSN from DATABASE_URL, dropping SQLAlchemy's '+psycopg' driver tag.

    Falls back to the same local-dev value the compose uses, so a no-env run
    against the local stack already connects."""
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://janus:CHANGE_ME@ju-postgres:5432/janus",
    )
    return url.replace("+psycopg", "", 1)


def _resolve(name: str, valid: set[str]) -> str | None:
    """Map a polygon's raw name to an existing territory_name, or None if unknown."""
    candidate = OVERRIDES.get(name, name)
    return candidate if candidate in valid else None


def load(path: str, name_field: str) -> int:
    geojson_path = Path(path)
    if not geojson_path.is_file():
        sys.exit(f"GeoJSON path does not exist or is not a file: {path!r}.")
    with geojson_path.open(encoding="utf-8") as fh:
        collection = json.load(fh)

    features = collection.get("features", [])
    if not features:
        sys.exit(f"No features in {path!r}.")

    with psycopg.connect(_dsn()) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT territory_name FROM public.demographic WHERE level = 'province'"
        )
        valid = {row[0] for row in cur.fetchall()}
        if not valid:
            sys.exit(
                "public.demographic has no province rows; load the demographic "
                "data first (see db/README.md)."
            )

        loaded, unmatched = 0, []
        for feature in features:
            raw = (feature.get("properties") or {}).get(name_field)
            geometry = feature.get("geometry")
            if not raw or geometry is None:
                continue
            territory = _resolve(raw, valid)
            if territory is None:
                unmatched.append(raw)
                continue
            # ST_Multi coerces Polygon→MultiPolygon to match the column type; the
            # geometry is passed as a bound JSON string (no SQL injection surface).
            cur.execute(
                """
                INSERT INTO public.demographic_boundary (territory_name, level, geom)
                VALUES (
                    %(territory)s,
                    'province',
                    ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%(geom)s), 4326))
                )
                ON CONFLICT (territory_name) DO UPDATE SET geom = EXCLUDED.geom
                """,
                {"territory": territory, "geom": json.dumps(geometry)},
            )
            loaded += 1
        conn.commit()

    print(f"Loaded {loaded} province boundaries into public.demographic_boundary.")
    if unmatched:
        print(
            f"\n{len(unmatched)} polygon name(s) did not match a province in "
            f"public.demographic — add them to OVERRIDES and re-run:",
            file=sys.stderr,
        )
        for name in sorted(set(unmatched)):
            print(f"  - {name!r}", file=sys.stderr)
    return loaded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geojson", help="Path to the province boundary GeoJSON.")
    parser.add_argument(
        "--name-field",
        default="DEN_UTS",
        help="Feature property holding the province name (default: DEN_UTS).",
    )
    args = parser.parse_args()
    load(args.geojson, args.name_field)


if __name__ == "__main__":
    main()
