"""``comune_resolver`` maps a clicked point to its comune by point-in-polygon.

Unit-level: the resolver is driven over a mocked session (no live DB), so we test
the seam it presents to the router — a ``Comune`` for a containing polygon, ``None``
for a point no comune contains — not the SQL text.
"""

from unittest.mock import MagicMock, patch

from src.routers.likert.comune_resolver import Comune, resolve_comune

SANT_ANGELO_ROW = {"region_id": 42, "name": "Sant'Angelo dei Lombardi"}


def _session_returning(row):
    patcher = patch("src.routers.likert.comune_resolver.get_session_context")
    mock_get_session = patcher.start()
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.first.return_value = row
    mock_get_session.return_value.__enter__.return_value = mock_session
    return patcher


def test_point_in_a_comune_resolves_to_that_comune():
    patcher = _session_returning(SANT_ANGELO_ROW)
    try:
        comune = resolve_comune(40.9312, 15.1789)
    finally:
        patcher.stop()

    assert comune == Comune(region_id=42, name="Sant'Angelo dei Lombardi")


def test_point_in_no_comune_resolves_to_none():
    """A click outside every comune boundary (e.g. out at sea): no polygon
    contains it, so there is no comune to compute a Gradimento for."""
    patcher = _session_returning(None)
    try:
        comune = resolve_comune(40.0, 17.5)
    finally:
        patcher.stop()

    assert comune is None
