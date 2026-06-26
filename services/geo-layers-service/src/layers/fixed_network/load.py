#!/usr/bin/env python3
"""One-off loader: under-1Gb civic addresses CSV -> public.fixed_network_under_1gb.

Self-contained (stdlib + psycopg, already in the service image), so it is baked
into the image and runs as a module. Reads the "Allegato A" CSV (latin-1,
semicolon-separated, comma decimals), keeps one region, and upserts by id_egon so
re-running refreshes. The table comes up empty with the compose schema-init; this
loads its rows (the compose brings up the schema, not the data — ADR-0001).

Usage (inside the running stack — the CSV is the only thing to copy in):

    docker compose cp "data/Copertura_Digitale/Rete_Fissa_Sotto_1Gb/Allegato A_mapp707K.csv" \
        geo-layers-service:/tmp/civics.csv
    docker compose exec geo-layers-service \
        python -m src.layers.fixed_network.load /tmp/civics.csv --region CAMPANIA
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

import psycopg

INSERT = """
    INSERT INTO public.fixed_network_under_1gb
        (id_egon, regione, provincia, procom21, comune, frazione, strada, civico, geom)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
    ON CONFLICT (id_egon) DO UPDATE SET
        regione = EXCLUDED.regione, provincia = EXCLUDED.provincia,
        procom21 = EXCLUDED.procom21, comune = EXCLUDED.comune,
        frazione = EXCLUDED.frazione, strada = EXCLUDED.strada,
        civico = EXCLUDED.civico, geom = EXCLUDED.geom
"""


def _dsn() -> str:
    """psycopg3 DSN from DATABASE_URL, dropping SQLAlchemy's '+psycopg' driver tag."""
    url = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://janus:CHANGE_ME@ju-postgres:5432/janus"
    )
    return url.replace("+psycopg", "", 1)


def parse(path: str, region: str) -> list[tuple]:
    rows: list[tuple] = []
    with open(path, encoding="latin-1", newline="") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            if region and r["regione"].strip().upper() != region.upper():
                continue
            try:
                lon = float(r["long"].replace(",", "."))
                lat = float(r["lat"].replace(",", "."))
                idx = int(r["id_egon"])
            except (ValueError, KeyError):
                continue
            if lon == 0 or lat == 0:
                continue
            rows.append((idx, r["regione"], r["provincia"], r["procom21"], r["comune"],
                         r.get("frazione", ""), r.get("strada", ""), r.get("civico", ""), lon, lat))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="path to the Allegato A CSV")
    ap.add_argument("--region", default="CAMPANIA", help="ISTAT region to load (default CAMPANIA)")
    args = ap.parse_args()

    rows = parse(args.csv, args.region)
    print(f"parsed {len(rows)} civics for region {args.region}")
    if not rows:
        return 1

    with psycopg.connect(_dsn()) as conn, conn.cursor() as cur:
        cur.executemany(INSERT, rows)
        conn.commit()
        cur.execute(
            "SELECT count(*) FROM public.fixed_network_under_1gb WHERE regione = %s",
            (args.region,),
        )
        print(f"rows now in table for {args.region}: {cur.fetchone()[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
