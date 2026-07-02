"""Read access to the curated Prezzario dei Lavori snapshot (``prezzario_voci``).

Lista B is **region-fixed**: the same curated slice everywhere in Campania, so these
reads take no comune. A deep module — the router sees ``list_capitoli()``,
``find_voci(capitolo, q)`` and ``current_publication()``; the shared-DB session and the
filtering live behind them.

The curated renovation slice is small and static (one published edition, a handful of
Capitoli), so ``find_voci`` fetches it once and applies the **capitolo** and
**case-insensitive description** filters in Python — cheaper to reason about and to test
than pushing an ILIKE into SQL, and the filter contract is exercised in isolation
(``test_prezzario_repository.py``). Reads only this service's own table (ADR-0001).
"""

from dataclasses import dataclass
from typing import List, Optional

from src.config.pgsql_config import get_session_context, text


@dataclass(frozen=True)
class Capitolo:
    """One curated chapter for the right column's nav: its codice and titolo."""

    codice: str
    titolo: str


@dataclass(frozen=True)
class Voce:
    """One priced line of the Prezzario dei Lavori: codice, descrizione, unità di
    misura, prezzo unitario, and its Capitolo."""

    codice: str
    descrizione: str
    um: str
    prezzo: float
    capitolo: str


# The distinct curated Capitoli present in the snapshot, ordered by codice — the
# chapters the widget offers as navigation. Reads only this service's table.
_CAPITOLI_QUERY = text(
    """
    SELECT DISTINCT capitolo AS codice, capitolo_titolo AS titolo
    FROM public.prezzario_voci
    ORDER BY codice
    """
)

# The full curated slice, ordered by codice. Filtering (capitolo + description
# search) is applied in Python by ``find_voci`` — see the module docstring.
_VOCI_QUERY = text(
    """
    SELECT codice, descrizione, um, prezzo, capitolo
    FROM public.prezzario_voci
    ORDER BY codice
    """
)

# The snapshot's publication label (latest-only ⇒ one distinct value). NULL/absent
# when nothing has been ingested yet.
_PUBLICATION_QUERY = text(
    """
    SELECT publication
    FROM public.prezzario_voci
    LIMIT 1
    """
)


def list_capitoli() -> List[Capitolo]:
    """Return the curated chapters (for the right column's Capitolo nav)."""
    with get_session_context() as session:
        rows = session.execute(_CAPITOLI_QUERY).mappings().all()
    return [Capitolo(codice=row["codice"], titolo=row["titolo"]) for row in rows]


def find_voci(capitolo: Optional[str], q: Optional[str]) -> List[Voce]:
    """Return the curated voci, narrowed by ``capitolo`` and/or ``q``.

    Args:
        capitolo: keep only this chapter's voci, or all chapters when ``None``.
        q: keep only voci whose descrizione contains this substring
            (case-insensitive), or all when ``None``/empty.

    Returns:
        The matching voci in codice order; an empty list when nothing matches.
    """
    with get_session_context() as session:
        rows = session.execute(_VOCI_QUERY).mappings().all()

    needle = q.lower() if q else None
    voci: List[Voce] = []
    for row in rows:
        if capitolo and row["capitolo"] != capitolo:
            continue
        if needle and needle not in row["descrizione"].lower():
            continue
        voci.append(
            Voce(
                codice=row["codice"],
                descrizione=row["descrizione"],
                um=row["um"],
                prezzo=row["prezzo"],
                capitolo=row["capitolo"],
            )
        )
    return voci


def current_publication() -> Optional[str]:
    """Return the snapshot's publication label (e.g. ``"2026"``), or ``None`` when no
    edition has been ingested yet."""
    with get_session_context() as session:
        row = session.execute(_PUBLICATION_QUERY).mappings().first()
    return row["publication"] if row else None
