"""``prezzario_repository`` reads the curated Prezzario dei Lavori snapshot.

Unit-level, driven over a **mocked session** (prior art likert
``test_competitor_repository.py``): no live DB, so we test the seam the router reads —
DB rows mapped to ``Capitolo``/``Voce`` records and the **in-Python** capitolo + case-
insensitive description filtering of ``find_voci`` (the curated slice is small and
static, so it is fetched once and filtered in memory). An empty result maps to ``[]``.
"""

from unittest.mock import MagicMock, patch

from src.routers.prezzari.prezzario_repository import (
    Capitolo,
    Voce,
    current_publication,
    find_voci,
    list_capitoli,
)

CAPITOLO_ROWS = [
    {"codice": "E.01", "titolo": "Demolizioni e rimozioni"},
    {"codice": "E.21", "titolo": "Opere di recupero e consolidamento"},
]

VOCE_ROWS = [
    {"codice": "E.01.010.a", "descrizione": "Demolizione di tramezzatura in muratura",
     "um": "m²", "prezzo": 18.40, "capitolo": "E.01"},
    {"codice": "E.21.030.b", "descrizione": "Recupero di solaio in legno",
     "um": "m²", "prezzo": 92.50, "capitolo": "E.21"},
    {"codice": "E.21.040.a", "descrizione": "Consolidamento di muratura",
     "um": "m³", "prezzo": 210.00, "capitolo": "E.21"},
]


def _session_returning(rows, module_fn="find_voci"):
    """Patch the repository's session so ``.mappings().all()`` yields ``rows`` and
    ``.mappings().first()`` yields the first row (for the single-value reads)."""
    patcher = patch("src.routers.prezzari.prezzario_repository.get_session_context")
    mock_get_session = patcher.start()
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = rows
    mock_session.execute.return_value.mappings.return_value.first.return_value = (
        rows[0] if rows else None
    )
    mock_get_session.return_value.__enter__.return_value = mock_session
    return patcher


def test_list_capitoli_returns_the_curated_chapters_as_records():
    patcher = _session_returning(CAPITOLO_ROWS)
    try:
        capitoli = list_capitoli()
    finally:
        patcher.stop()

    assert capitoli == [
        Capitolo(codice="E.01", titolo="Demolizioni e rimozioni"),
        Capitolo(codice="E.21", titolo="Opere di recupero e consolidamento"),
    ]


def test_find_voci_with_no_filter_returns_the_full_curated_slice():
    """Empty capitolo/q ⇒ every curated Voce, mapped to records (the right column's
    initial render)."""
    patcher = _session_returning(VOCE_ROWS)
    try:
        voci = find_voci(None, None)
    finally:
        patcher.stop()

    assert voci == [
        Voce(codice="E.01.010.a", descrizione="Demolizione di tramezzatura in muratura",
             um="m²", prezzo=18.40, capitolo="E.01"),
        Voce(codice="E.21.030.b", descrizione="Recupero di solaio in legno",
             um="m²", prezzo=92.50, capitolo="E.21"),
        Voce(codice="E.21.040.a", descrizione="Consolidamento di muratura",
             um="m³", prezzo=210.00, capitolo="E.21"),
    ]


def test_find_voci_filters_by_capitolo():
    """Capitolo nav narrows the slice to one chapter's voci."""
    patcher = _session_returning(VOCE_ROWS)
    try:
        voci = find_voci("E.21", None)
    finally:
        patcher.stop()

    assert [v.codice for v in voci] == ["E.21.030.b", "E.21.040.a"]


def test_find_voci_filters_by_case_insensitive_description_substring():
    """The description search matches a substring regardless of case (``RECUPERO``
    finds "Recupero di solaio")."""
    patcher = _session_returning(VOCE_ROWS)
    try:
        voci = find_voci(None, "RECUPERO")
    finally:
        patcher.stop()

    assert [v.codice for v in voci] == ["E.21.030.b"]


def test_find_voci_combines_capitolo_and_query():
    """Capitolo and search compose — chapter E.21 AND "consolidamento"."""
    patcher = _session_returning(VOCE_ROWS)
    try:
        voci = find_voci("E.21", "consolidamento")
    finally:
        patcher.stop()

    assert [v.codice for v in voci] == ["E.21.040.a"]


def test_find_voci_no_match_returns_empty_list():
    patcher = _session_returning(VOCE_ROWS)
    try:
        voci = find_voci(None, "ascensore")
    finally:
        patcher.stop()

    assert voci == []


def test_current_publication_returns_the_snapshot_label():
    patcher = _session_returning([{"publication": "2026"}])
    try:
        publication = current_publication()
    finally:
        patcher.stop()

    assert publication == "2026"


def test_current_publication_is_none_when_no_snapshot_loaded():
    patcher = _session_returning([])
    try:
        publication = current_publication()
    finally:
        patcher.stop()

    assert publication is None
