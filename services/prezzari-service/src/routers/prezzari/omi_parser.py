"""The OMI locazione parser + Campania scoping (pure core) — PRD "Lista A"; ADR-0001.

The Agenzia delle Entrate OMI publishes national rental/sale quotations; I Prezziari
keeps only a **Campania, locazione** slice. This module turns raw source records into
normalized ``OmiRow`` rows, applying three independent filters:

* **locazione only** — the OMI sale (compravendita) values are dropped on purpose; the
  reuse pan is market **rent**, not sale (CONTEXT.md).
* **Campania comuni only** — although the OMI is national, only the five Campania
  provinces are kept (``CAMPANIA_PROVINCE``), matching the region-bound Lista B and map.
* **malformed / empty rows skipped** — a row missing a required field or carrying an
  unparseable canone is dropped, not fatal, so the rows around it still land.

The comune is emitted by its **ISTAT code**: the parser is pure (no DB), so mapping the
comune to a monolith ``region_id`` is the offline ingest's job, not this module's. No
IO, no DB, no HTTP — the load-bearing "source record → rows" logic in isolation,
table-driven like likert's ``gradimento_calculator``.
"""

from dataclasses import dataclass
from typing import Iterable, List, Mapping

# The five Campania provinces, by their official sigla — an explicit, re-confirmable
# editorial set (a new OMI edition is re-scoped deliberately, never inferred at
# runtime). Everything outside it is dropped so the snapshot stays Campania-only.
CAMPANIA_PROVINCE: set = {"AV", "BN", "CE", "NA", "SA"}

# OMI locazione quotations are always €/m²/month; the unit is fixed for the market, so
# it is attached as a constant rather than read from a (absent) source column.
LOCAZIONE_UM = "€/m²/mese"


@dataclass(frozen=True)
class OmiRow:
    """One normalized OMI locazione line ready for ``omi_locazione``: the comune by its
    ISTAT code (mapped to a region_id at ingest), the Zona OMI × tipologia × stato, and
    the min–max monthly canone with its unit."""

    comune_istat: str
    zona: str
    tipologia: str
    stato: str
    canone_min: float
    canone_max: float
    um: str


def parse_omi(records: Iterable[Mapping]) -> List[OmiRow]:
    """Normalize ``records`` into Campania locazione ``OmiRow``s.

    Args:
        records: raw OMI source rows, each with ``mercato`` (locazione/compravendita),
            ``prov`` (province sigla), ``comune_istat``, ``zona``, ``tipologia``,
            ``stato`` and the ``canone_min``/``canone_max`` Italian-decimal strings.

    Returns:
        One ``OmiRow`` per locazione record in a Campania province with a parseable
        canone and the required fields, in source order; every other record is dropped.
    """
    rows: List[OmiRow] = []
    for record in records:
        # locazione only: OMI sale (compravendita) rows are dropped on purpose.
        if (record.get("mercato") or "").strip().lower() != "locazione":
            continue
        # Campania only: drop any comune outside the five Campania provinces.
        if (record.get("prov") or "").strip().upper() not in CAMPANIA_PROVINCE:
            continue
        canone_min = _parse_canone(record.get("canone_min"))
        canone_max = _parse_canone(record.get("canone_max"))
        comune_istat = record.get("comune_istat")
        zona = record.get("zona")
        tipologia = record.get("tipologia")
        stato = record.get("stato")
        # A row missing an identifying field or with an unparseable/empty canone is
        # skipped, not fatal — the valid rows around it still land.
        if not (comune_istat and zona and tipologia and stato):
            continue
        if canone_min is None or canone_max is None:
            continue
        rows.append(
            OmiRow(
                comune_istat=comune_istat,
                zona=zona,
                tipologia=tipologia,
                stato=stato,
                canone_min=canone_min,
                canone_max=canone_max,
                um=LOCAZIONE_UM,
            )
        )
    return rows


def _parse_canone(raw) -> float | None:
    """Parse an Italian-decimal canone (``"3,2"`` → ``3.2``); ``None`` when missing or
    unparseable so the caller can skip the row."""
    if raw is None or raw == "":
        return None
    try:
        return float(str(raw).replace(",", "."))
    except ValueError:
        return None
