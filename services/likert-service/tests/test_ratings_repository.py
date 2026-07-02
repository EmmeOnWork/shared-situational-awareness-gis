"""``ratings_repository`` reads the cached rating for competitor POIs.

Unit-level: driven over a mocked session (no live DB), so we test the seam it
presents to the router — the identity-map → cache join mapped to ``PlaceRating``
records keyed by ``poi_id``, and an empty result mapped to ``{}`` — not the SQL
text (that join is exercised end-to-end against the shared DB once the worker
seeds the cache). Only matched + rated POIs come back; an unmatched or uncached
competitor is simply absent (never a fabricated 0★).
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.routers.likert.ratings_repository import PlaceRating, fetch_ratings

FETCHED = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

ROWS = [
    {"poi_id": 11, "rating": 4.6, "n_ratings": 120, "fetched_at": FETCHED},
    {"poi_id": 22, "rating": 3.1, "n_ratings": 8, "fetched_at": FETCHED},
]


def _session_returning(rows):
    patcher = patch("src.routers.likert.ratings_repository.get_session_context")
    mock_get_session = patcher.start()
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = rows
    mock_get_session.return_value.__enter__.return_value = mock_session
    return patcher


def test_returns_cached_ratings_keyed_by_poi_id():
    patcher = _session_returning(ROWS)
    try:
        ratings = fetch_ratings([11, 22, 33])
    finally:
        patcher.stop()

    assert ratings == {
        11: PlaceRating(poi_id=11, rating=4.6, n_ratings=120, fetched_at=FETCHED),
        22: PlaceRating(poi_id=22, rating=3.1, n_ratings=8, fetched_at=FETCHED),
    }


def test_no_cached_ratings_returns_empty_map():
    """Competitors with no confident match / no cached rating yield nothing — the
    route turns an empty map into ``insufficient`` (competitors found, none to
    rate), never a needle from thin air."""
    patcher = _session_returning([])
    try:
        ratings = fetch_ratings([11, 22])
    finally:
        patcher.stop()

    assert ratings == {}


def test_no_poi_ids_short_circuits_without_a_query():
    """An empty competitor set never hits the DB (the route already handles the
    no-competitor cases before asking for ratings)."""
    with patch(
        "src.routers.likert.ratings_repository.get_session_context"
    ) as get_session:
        ratings = fetch_ratings([])

    get_session.assert_not_called()
    assert ratings == {}
