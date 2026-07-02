"""The Prezzario dei Lavori parser + curation (pure core) — PRD "Lista B"; ADR-0001.

The Regione Campania public-works price list is a large document; I Prezziari shows
only a **curated slice** — the **building renovation / recovery Capitoli** (not roads,
aqueducts, etc.). This module turns raw source records into normalized
``prezzario_voci`` rows, **keeping only the curated Capitoli and dropping the rest**.

The curated Capitolo set (``CURATED_CAPITOLI``) is an **explicit, re-confirmable
editorial list** fixed at ingest: a new edition is re-curated deliberately, never
silently drifted. Each Voce is associated to its Capitolo by the **leading chapter
segment of its codice** (the real prezzario hierarchy, e.g. ``E.01.010.a`` → ``E.01``).

No IO, no DB, no HTTP — the load-bearing "source record → rows" logic in isolation,
table-driven like likert's ``gradimento_calculator``.
"""

from dataclasses import dataclass
from typing import Iterable, List, Mapping

# The curated renovation / recupero Capitoli: an explicit codice→titolo map, NOT
# inferred at runtime. Editorial — re-confirmed per edition (a new prezzario year is
# re-curated, not just re-imported). Tunable (PRD "Tunables recorded here").
CURATED_CAPITOLI: dict = {
    "E.01": "Demolizioni e rimozioni",
    "E.21": "Opere di recupero e consolidamento",
}


@dataclass(frozen=True)
class VoceRow:
    """One curated, normalized priced line ready for ``prezzario_voci``: its codice,
    descrizione, unità di misura, prezzo unitario, and the Capitolo it belongs to."""

    codice: str
    descrizione: str
    um: str
    prezzo: float
    capitolo: str


def _capitolo_of(codice: str) -> str:
    """The Capitolo is the leading chapter segment of the dotted codice
    (``E.01.010.a`` → ``E.01``) — the prezzario's own hierarchy."""
    parts = codice.split(".")
    return ".".join(parts[:2])


def parse_voci(records: Iterable[Mapping]) -> List[VoceRow]:
    """Normalize ``records`` into curated ``VoceRow``s, dropping non-curated Capitoli.

    Args:
        records: raw source rows, each with ``codice``, ``descrizione``, ``um`` and a
            ``prezzo`` (an Italian-decimal string, e.g. ``"18,40"``).

    Returns:
        One ``VoceRow`` per record whose derived Capitolo is in ``CURATED_CAPITOLI``,
        in source order; every other record is excluded.
    """
    rows: List[VoceRow] = []
    for record in records:
        codice = record.get("codice")
        if not codice:
            continue
        capitolo = _capitolo_of(codice)
        if capitolo not in CURATED_CAPITOLI:
            continue
        prezzo = _parse_prezzo(record.get("prezzo"))
        descrizione = record.get("descrizione")
        um = record.get("um")
        # A curated Voce with a missing/unparseable field is skipped, not fatal — the
        # curated rows around it still land (a single bad source cell can't void the
        # whole ingest).
        if prezzo is None or not descrizione or not um:
            continue
        rows.append(
            VoceRow(
                codice=codice,
                descrizione=descrizione,
                um=um,
                prezzo=prezzo,
                capitolo=capitolo,
            )
        )
    return rows


def _parse_prezzo(raw) -> float | None:
    """Parse an Italian-decimal prezzo (``"18,40"`` → ``18.40``); ``None`` when
    missing or unparseable so the caller can skip the row."""
    if raw is None:
        return None
    try:
        return float(str(raw).replace(",", "."))
    except ValueError:
        return None
