"""``competitor_repository`` returns a comune's competitor POIs for a Vocazione.

Unit-level: driven over a mocked session (no live DB), so we test the seam it
presents to the router — DB rows mapped to ``Competitor`` records, and an empty
result mapped to ``[]`` — not the SQL text (that join mirrors the Concorrenza
layer's and is exercised end-to-end against the shared DB).
"""

from unittest.mock import MagicMock, patch

from src.routers.likert.competitor_repository import Competitor, find_competitors

ROWS = [
    {"poi_id": 11, "name": "Terme di Esempio", "categoria": "Spa"},
    {"poi_id": 22, "name": "Palestra Borgo", "categoria": "Gym"},
]

PREFIXES = ["Business and Professional Services > Health and Beauty Service"]


def _session_returning(rows):
    patcher = patch(
        "src.routers.likert.competitor_repository.get_session_context"
    )
    mock_get_session = patcher.start()
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = rows
    mock_get_session.return_value.__enter__.return_value = mock_session
    return patcher


def test_returns_the_comunes_competitors_as_records():
    patcher = _session_returning(ROWS)
    try:
        competitors = find_competitors(region_id=42, prefixes=PREFIXES)
    finally:
        patcher.stop()

    assert competitors == [
        Competitor(poi_id=11, name="Terme di Esempio", categoria="Spa"),
        Competitor(poi_id=22, name="Palestra Borgo", categoria="Gym"),
    ]


def test_no_matching_poi_returns_empty_list():
    """A comune with no competitor of this kind yields no records (the route turns
    that into ``insufficient`` — competitors found, none to rate)."""
    patcher = _session_returning([])
    try:
        competitors = find_competitors(region_id=42, prefixes=PREFIXES)
    finally:
        patcher.stop()

    assert competitors == []
