#!/usr/bin/env python3
"""Offline ingest for the OMI locazione snapshot → public.omi_locazione.

Parses an Agenzia delle Entrate OMI export into the **Campania, locazione** slice and
**replaces** the prior snapshot (latest-only): the whole table is wiped and reloaded in
one transaction, so the widget shows exactly one current semestral edition with no stale
history (PRD Lista A; prezzari ADR-0001).

The load-bearing parse + Campania/locazione filtering is NOT here — it lives in the
tested pure module ``src/routers/prezzari/omi_parser.py`` (``parse_omi`` keeps only
``CAMPANIA_PROVINCE`` locazione rows and normalizes each canone). This CLI adds the one
step the pure parser cannot do: map each OMI comune's **ISTAT code** to its monolith
``region_id`` (the shared ``areas`` boundaries, ``area_type_id = 3``, carry it in
``metadata->>'ref:ISTAT'``). A row whose ISTAT does not resolve to a Campania region is
skipped. Thin orchestration (read file → parse → map → replace), manual-verify like the
prezzario ingest and the demographic widget's ``load_boundaries.py``.

Input: a CSV with a header row carrying at least ``mercato`` (locazione/compravendita),
``prov`` (province sigla), ``comune_istat``, ``zona``, ``tipologia``, ``stato`` and the
``canone_min``/``canone_max`` columns (each an Italian decimal like ``3,2``). Column
names are configurable via ``--*-col``.

Usage (inside the running stack — the service container has psycopg + src on path):

    docker compose cp services/prezzari-service/db/ingest_omi.py \
        prezzari-service:/tmp/ingest_omi.py
    docker compose cp omi-2025-s2.csv prezzari-service:/tmp/omi-2025-s2.csv
    docker compose exec prezzari-service \
        python /tmp/ingest_omi.py /tmp/omi-2025-s2.csv --publication "2025 · II semestre"
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

import psycopg

# Run from the service root so the tested parser is importable (the container's WORKDIR
# already puts `src` on the path; this makes a local venv run work too).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.routers.prezzari.omi_parser import parse_omi  # noqa: E402

# The comune boundaries (regions, area_type_id = 3) carry the ISTAT code in
# `metadata->>'ref:ISTAT'` — the same join the seismic layer uses. One query builds the
# whole ISTAT → region_id map; the parser already dropped non-Campania rows, so an
# unresolved ISTAT here just means the boundary set has no such comune (skipped).
_REGION_BY_ISTAT_QUERY = """
    SELECT r.id AS region_id, a.metadata->>'ref:ISTAT' AS istat
    FROM regions r
    JOIN region_areas ra ON ra.region_id = r.id
    JOIN areas a ON ra.area_id = a.id
    WHERE a.area_type_id = 3
      AND a.metadata->>'ref:ISTAT' IS NOT NULL
"""


def _dsn() -> str:
    """psycopg3 DSN from DATABASE_URL, dropping SQLAlchemy's '+psycopg' driver tag.
    Falls back to the local-dev compose value so a no-env run already connects."""
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://janus:CHANGE_ME@ju-postgres:5432/janus",
    )
    return url.replace("+psycopg", "", 1)


def _istat_key(raw: str) -> str:
    """Normalize an ISTAT code for matching — strip leading zeros so a zero-padded OMI
    code (``064001``) and an unpadded boundary code (``64001``) still meet."""
    return (raw or "").strip().lstrip("0")


def _read_records(path: str, columns: dict[str, str]) -> list[dict]:
    """Read the CSV into the raw record shape ``parse_omi`` expects, remapping the
    configured source column names."""
    csv_path = Path(path)
    if not csv_path.is_file():
        sys.exit(f"Source path does not exist or is not a file: {path!r}.")
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return [
            {field: (row.get(src) or "").strip() for field, src in columns.items()}
            for row in reader
        ]


def _region_by_istat(cur) -> dict[str, int]:
    """The ISTAT → region_id map for every comune boundary, keyed by normalized code."""
    cur.execute(_REGION_BY_ISTAT_QUERY)
    return {_istat_key(row[1]): row[0] for row in cur.fetchall()}


def ingest(path: str, publication: str, columns: dict[str, str]) -> int:
    """Parse ``path``, map each comune to its region_id, and replace the snapshot.
    Returns the number of rows loaded."""
    records = _read_records(path, columns)
    voci = parse_omi(records)
    if not voci:
        sys.exit(
            "No Campania locazione rows parsed — check the source columns and that the "
            "file carries locazione rows in a Campania province (nothing was written)."
        )

    with psycopg.connect(_dsn()) as conn, conn.cursor() as cur:
        region_by_istat = _region_by_istat(cur)
        rows = []
        skipped = 0
        for v in voci:
            region_id = region_by_istat.get(_istat_key(v.comune_istat))
            if region_id is None:
                skipped += 1
                continue
            rows.append(
                {
                    "region_id": region_id,
                    "zona": v.zona,
                    "tipologia": v.tipologia,
                    "stato": v.stato,
                    "canone_min": v.canone_min,
                    "canone_max": v.canone_max,
                    "um": v.um,
                    "publication": publication,
                }
            )
        if not rows:
            sys.exit(
                "No OMI row's comune ISTAT resolved to a Campania region — check that "
                "the boundary set carries metadata->>'ref:ISTAT' (nothing was written)."
            )

        # Latest-only: wipe the prior edition, then load the new one in the same
        # transaction so a failed ingest never leaves the table empty.
        cur.execute("DELETE FROM public.omi_locazione")
        cur.executemany(
            """
            INSERT INTO public.omi_locazione
                (region_id, zona, tipologia, stato, canone_min, canone_max, um, publication)
            VALUES
                (%(region_id)s, %(zona)s, %(tipologia)s, %(stato)s,
                 %(canone_min)s, %(canone_max)s, %(um)s, %(publication)s)
            """,
            rows,
        )
        conn.commit()

    print(
        f"Replaced snapshot: loaded {len(rows)} OMI locazione rows "
        f"(publication {publication!r}) across {len({r['region_id'] for r in rows})} comuni; "
        f"{skipped} row(s) skipped (comune ISTAT not in the Campania boundary set)."
    )
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Path to the OMI CSV export.")
    parser.add_argument(
        "--publication", required=True,
        help='Semestral edition label stamped on every row (e.g. "2025 · II semestre").',
    )
    parser.add_argument("--mercato-col", default="mercato")
    parser.add_argument("--prov-col", default="prov")
    parser.add_argument("--comune-istat-col", default="comune_istat")
    parser.add_argument("--zona-col", default="zona")
    parser.add_argument("--tipologia-col", default="tipologia")
    parser.add_argument("--stato-col", default="stato")
    parser.add_argument("--canone-min-col", default="canone_min")
    parser.add_argument("--canone-max-col", default="canone_max")
    args = parser.parse_args()

    columns = {
        "mercato": args.mercato_col,
        "prov": args.prov_col,
        "comune_istat": args.comune_istat_col,
        "zona": args.zona_col,
        "tipologia": args.tipologia_col,
        "stato": args.stato_col,
        "canone_min": args.canone_min_col,
        "canone_max": args.canone_max_col,
    }
    ingest(args.source, args.publication, columns)


if __name__ == "__main__":
    main()
