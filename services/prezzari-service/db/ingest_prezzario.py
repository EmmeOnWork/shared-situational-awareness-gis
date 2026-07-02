#!/usr/bin/env python3
"""Offline ingest for the Prezzario dei Lavori snapshot → public.prezzario_voci.

Parses a source export of the Regione Campania price list into the **curated**
renovation/recovery slice and **replaces** the prior snapshot (latest-only): the
whole table is wiped and reloaded in one transaction, so the widget shows exactly one
current edition with no stale history (PRD stories 28–29; prezzari ADR-0001).

The load-bearing parse + curation logic is NOT here — it lives in the tested pure
module ``src/routers/prezzari/prezzario_parser.py`` (``parse_voci`` keeps only the
``CURATED_CAPITOLI`` and normalizes each Voce). This CLI is thin orchestration
(read file → parse → replace) and is manual-verify, exactly like the demographic
widget's ``load_boundaries.py``.

Input: a CSV with a header row carrying at least ``codice``, ``descrizione``, ``um``
and ``prezzo`` columns (the prezzo an Italian decimal like ``18,40``). Column names
are configurable via ``--column``; the Capitolo is DERIVED from each codice, not read
from the file.

Usage (inside the running stack — the service container has psycopg + src on path):

    docker compose cp services/prezzari-service/db/ingest_prezzario.py \
        prezzari-service:/tmp/ingest_prezzario.py
    docker compose cp prezzario-2026.csv prezzari-service:/tmp/prezzario-2026.csv
    docker compose exec prezzari-service \
        python /tmp/ingest_prezzario.py /tmp/prezzario-2026.csv --publication 2026
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

import psycopg

# Run from the service root so the tested parser is importable (the container's
# WORKDIR already puts `src` on the path; this makes a local venv run work too).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.routers.prezzari.prezzario_parser import (  # noqa: E402
    CURATED_CAPITOLI,
    parse_voci,
)


def _dsn() -> str:
    """psycopg3 DSN from DATABASE_URL, dropping SQLAlchemy's '+psycopg' driver tag.
    Falls back to the local-dev compose value so a no-env run already connects."""
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://janus:CHANGE_ME@ju-postgres:5432/janus",
    )
    return url.replace("+psycopg", "", 1)


def _read_records(path: str, columns: dict[str, str]) -> list[dict]:
    """Read the CSV into the raw record shape ``parse_voci`` expects (codice /
    descrizione / um / prezzo), remapping the configured source column names."""
    csv_path = Path(path)
    if not csv_path.is_file():
        sys.exit(f"Source path does not exist or is not a file: {path!r}.")
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return [
            {field: (row.get(src) or "").strip() for field, src in columns.items()}
            for row in reader
        ]


def ingest(path: str, publication: str, columns: dict[str, str]) -> int:
    """Parse ``path``, curate it, and replace the snapshot. Returns rows loaded."""
    records = _read_records(path, columns)
    voci = parse_voci(records)
    if not voci:
        sys.exit(
            "No curated voci parsed — check the source columns and that the file "
            "carries Capitoli in CURATED_CAPITOLI (nothing was written)."
        )

    with psycopg.connect(_dsn()) as conn, conn.cursor() as cur:
        # Latest-only: wipe the prior edition, then load the new one in the same
        # transaction so a failed ingest never leaves the table empty.
        cur.execute("DELETE FROM public.prezzario_voci")
        cur.executemany(
            """
            INSERT INTO public.prezzario_voci
                (codice, descrizione, um, prezzo, capitolo, capitolo_titolo, publication)
            VALUES
                (%(codice)s, %(descrizione)s, %(um)s, %(prezzo)s,
                 %(capitolo)s, %(capitolo_titolo)s, %(publication)s)
            """,
            [
                {
                    "codice": v.codice,
                    "descrizione": v.descrizione,
                    "um": v.um,
                    "prezzo": v.prezzo,
                    "capitolo": v.capitolo,
                    "capitolo_titolo": CURATED_CAPITOLI[v.capitolo],
                    "publication": publication,
                }
                for v in voci
            ],
        )
        conn.commit()

    print(
        f"Replaced snapshot: loaded {len(voci)} curated voci "
        f"(publication {publication!r}) across {len({v.capitolo for v in voci})} Capitoli."
    )
    return len(voci)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Path to the prezzario CSV export.")
    parser.add_argument(
        "--publication", required=True,
        help="Edition label stamped on every row (e.g. 2026).",
    )
    parser.add_argument("--codice-col", default="codice")
    parser.add_argument("--descrizione-col", default="descrizione")
    parser.add_argument("--um-col", default="um")
    parser.add_argument("--prezzo-col", default="prezzo")
    args = parser.parse_args()

    columns = {
        "codice": args.codice_col,
        "descrizione": args.descrizione_col,
        "um": args.um_col,
        "prezzo": args.prezzo_col,
    }
    ingest(args.source, args.publication, columns)


if __name__ == "__main__":
    main()
