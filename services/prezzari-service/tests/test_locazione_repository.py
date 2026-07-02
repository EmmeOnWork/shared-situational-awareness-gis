"""``locazione_repository`` reads a comune's OMI locazione rows from the shared DB.

Unit-level, driven over a **mocked session** (prior art likert
``test_ratings_repository.py`` / ``test_competitor_repository.py``): no live DB, so we
test the seam the route reads — DB rows mapped to ``ZonaOmi`` records, an empty result
mapped to ``[]``, and the snapshot's ``publication`` label read back (``None`` when
nothing is ingested). The region scoping itself lives in the SQL (``WHERE region_id``)
and is exercised end-to-end against the shared DB.
"""

from unittest.mock import MagicMock, patch

from src.routers.prezzari.locazione_repository import (
    ZonaOmi,
    current_publication,
    find_locazione,
)

ZONE_ROWS = [
    {"zona": "B1", "tipologia": "Abitazioni civili", "stato": "Normale",
     "canone_min": 3.2, "canone_max": 4.5, "um": "€/m²/mese"},
    {"zona": "C2", "tipologia": "Abitazioni civili", "stato": "Scadente",
     "canone_min": 2.1, "canone_max": 3.0, "um": "€/m²/mese"},
]


def _session_returning(rows):
    """Patch the repository's session so ``.mappings().all()`` yields ``rows`` and
    ``.mappings().first()`` yields the first row (for the single-value reads)."""
    patcher = patch("src.routers.prezzari.locazione_repository.get_session_context")
    mock_get_session = patcher.start()
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = rows
    mock_session.execute.return_value.mappings.return_value.first.return_value = (
        rows[0] if rows else None
    )
    mock_get_session.return_value.__enter__.return_value = mock_session
    return patcher


def test_find_locazione_returns_the_comunes_zone_as_records():
    patcher = _session_returning(ZONE_ROWS)
    try:
        zone = find_locazione(region_id=15)
    finally:
        patcher.stop()

    assert zone == [
        ZonaOmi(zona="B1", tipologia="Abitazioni civili", stato="Normale",
                canone_min=3.2, canone_max=4.5, um="€/m²/mese"),
        ZonaOmi(zona="C2", tipologia="Abitazioni civili", stato="Scadente",
                canone_min=2.1, canone_max=3.0, um="€/m²/mese"),
    ]


def test_find_locazione_scopes_the_query_to_the_region():
    """The comune scoping is a bound ``region_id`` param — the row set is fetched with
    the caller's region id (no interpolation; nothing from other comuni leaks in)."""
    with patch(
        "src.routers.prezzari.locazione_repository.get_session_context"
    ) as mock_get_session:
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.all.return_value = ZONE_ROWS
        mock_get_session.return_value.__enter__.return_value = mock_session

        find_locazione(region_id=15)

    _query, params = mock_session.execute.call_args.args
    assert params == {"region_id": 15}


def test_find_locazione_no_omi_returns_empty_list():
    """A comune with no published OMI yields no records — the route turns that into an
    empty ``zone`` (the widget's "quotazioni OMI non disponibili" empty state)."""
    patcher = _session_returning([])
    try:
        zone = find_locazione(region_id=99)
    finally:
        patcher.stop()

    assert zone == []


def test_current_publication_returns_the_snapshot_label():
    patcher = _session_returning([{"publication": "2025 · II semestre"}])
    try:
        publication = current_publication()
    finally:
        patcher.stop()

    assert publication == "2025 · II semestre"


def test_current_publication_is_none_when_no_snapshot_loaded():
    patcher = _session_returning([])
    try:
        publication = current_publication()
    finally:
        patcher.stop()

    assert publication is None
