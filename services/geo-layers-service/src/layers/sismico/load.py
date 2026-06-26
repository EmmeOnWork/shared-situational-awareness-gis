#!/usr/bin/env python3
"""One-off loader: seismic classification CSV -> public.seismic_zone.

Self-contained (stdlib + psycopg, already in the image). The CSV (ISTAT
classificazione sismica, ';'-separated, BOM) has one row per comune with
COD_ISTAT_COMUNE and ZONA_SISMICA (1/2/3/3S/4). All of Italy is loaded (tiny); the
sismico route joins this to the clicked comune's public.areas boundary on the ISTAT
code (areas.metadata->>'ref:ISTAT'), so only comuni present in public.areas render —
no separate comuni-boundary import. Upserts by cod_istat.

Usage (inside the running stack):

    docker compose cp data/Dati_Rischio/Sismico/classificazione_rischio_sismico_clean.csv \
        geo-layers-service:/tmp/sismico.csv
    docker compose exec geo-layers-service \
        python -m src.layers.sismico.load /tmp/sismico.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

import psycopg

INSERT = """
    INSERT INTO public.seismic_zone (cod_istat, zona)
    VALUES (%s, %s)
    ON CONFLICT (cod_istat) DO UPDATE SET zona = EXCLUDED.zona
"""


def _dsn() -> str:
    """psycopg3 DSN from DATABASE_URL, dropping SQLAlchemy's '+psycopg' driver tag."""
    url = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://janus:CHANGE_ME@ju-postgres:5432/janus"
    )
    return url.replace("+psycopg", "", 1)


def parse(path: str) -> list[tuple]:
    rows: list[tuple] = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            try:
                cod = int(r["COD_ISTAT_COMUNE"])
            except (ValueError, KeyError):
                continue
            zona = (r.get("ZONA_SISMICA") or "").strip()
            if zona:
                rows.append((cod, zona))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="path to classificazione_rischio_sismico_clean.csv")
    args = ap.parse_args()

    rows = parse(args.csv)
    print(f"parsed {len(rows)} comune seismic zones")
    if not rows:
        return 1

    with psycopg.connect(_dsn()) as conn, conn.cursor() as cur:
        cur.executemany(INSERT, rows)
        conn.commit()
        cur.execute("SELECT count(*) FROM public.seismic_zone")
        print(f"rows now in seismic_zone: {cur.fetchone()[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
